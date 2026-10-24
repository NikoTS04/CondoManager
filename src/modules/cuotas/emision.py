"""Emisión ACID de CON-11; comparte los contratos persistentes CON-9/10/13."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.distribucion.exceptions import DistribucionError
from src.modules.cuotas.distribucion.repository import SQLAlchemyDistribucionRepository
from src.modules.cuotas.distribucion.service import DistribucionService, calcular_distribucion
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox, LoteCuotas
from src.modules.cuotas.presupuestos.repository import SQLAlchemyPresupuestoRepository
from src.modules.cuotas.saldos.repository import SQLAlchemySaldoFavorRepository
from src.modules.cuotas.saldos.service import ActorSaldoFavor, SaldosFavorService
from src.modules.cuotas.schemas import EmitirLoteCuotasResponse, EmitirLoteRequest


def cerrar_centavos(montos: dict[UUID, Decimal], total: Decimal) -> dict[UUID, Decimal]:
    """Cierre determinista sin convertir importes a float ni generar negativos."""
    resultado = dict(montos)
    diferencia = total - sum(resultado.values(), Decimal("0.00"))
    orden = sorted(resultado, key=lambda id: (-resultado[id], id.int))
    paso = Decimal("0.01") if diferencia > 0 else Decimal("-0.01")
    while diferencia:
        for id in orden:
            if paso < 0 and resultado[id] == 0:
                continue
            resultado[id] += paso
            diferencia -= paso
            if not diferencia:
                break
    return resultado


class EmisionCuotasService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def emitir(
        self, request: EmitirLoteRequest, actor: ActorSaldoFavor
    ) -> EmitirLoteCuotasResponse:
        if (
            not actor.id
            or actor.rol not in {"SUPERADMIN", "ADMIN_JUNTA", "SISTEMA_AUTOMATICO"}
            or (actor.rol != "SUPERADMIN" and actor.condominio_id != request.condominio_id)
        ):
            raise APIError(403, "EMISION_ACCESO_DENEGADO", "No puede emitir en este condominio.")
        # El servicio es dueño del límite transaccional, también en ejecuciones del worker.
        async with self.session.begin():
            return await self._emitir(request, actor)

    async def _emitir(
        self, request: EmitirLoteRequest, actor: ActorSaldoFavor
    ) -> EmitirLoteCuotasResponse:
        cid = request.condominio_id
        condominio = await self.session.scalar(
            select(Condominio).where(Condominio.id == cid).with_for_update()
        )
        if condominio is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        if not condominio.activo:
            raise APIError(422, "CONDOMINIO_INACTIVO", "El condominio está inactivo.")
        if condominio.regla_mora_tipo == "MONTO_DIARIO":
            raise APIError(
                409, "MOTOR_DIARIO_PENDIENTE",
                "La política diaria está configurada, pero su motor persistente aún no está habilitado.",
            )
        existente = await self.session.scalar(
            select(LoteCuotas.id).where(
                LoteCuotas.condominio_id == cid, LoteCuotas.periodo == request.periodo
            )
        )
        if existente is not None:
            raise APIError(409, "LOTE_YA_EMITIDO", "El periodo ya tiene un lote persistido.")
        presupuesto = await SQLAlchemyPresupuestoRepository(
            self.session
        ).obtener_aprobado_por_periodo(cid, request.periodo)
        if presupuesto is None:
            raise APIError(
                409, "PRESUPUESTO_NO_APROBADO", "Debe aprobar el presupuesto del periodo."
            )
        # Bloqueos en UUID ascendente, compartidos con CON-13.
        departamentos = list(
            (
                await self.session.scalars(
                    select(Departamento)
                    .join(Edificio)
                    .where(Edificio.condominio_id == cid, Departamento.activo.is_(True))
                    .order_by(Departamento.id)
                    .with_for_update(of=Departamento)
                )
            ).all()
        )
        try:
            distribucion = await DistribucionService(
                SQLAlchemyDistribucionRepository(self.session)
            ).obtener_para_emision(cid)
            montos = cerrar_centavos(
                calcular_distribucion(
                    presupuesto.monto_total, distribucion.departamentos, distribucion.metodo
                ),
                presupuesto.monto_total,
            )
        except DistribucionError as exc:
            raise APIError(422, exc.error_code, exc.mensaje, exc.detalles) from exc
        ahora = datetime.now(UTC)
        cubiertas = 0
        saldos = SaldosFavorService(SQLAlchemySaldoFavorRepository(self.session))
        for departamento in departamentos:
            cuota = CuotaMantenimiento(
                id=uuid4(),
                departamento_id=departamento.id,
                periodo=request.periodo,
                monto_ordinario=montos[departamento.id],
                monto_total_exigible=montos[departamento.id],
                monto_extraordinario=Decimal("0.00"),
                monto_mora=Decimal("0.00"),
                monto_pagado=Decimal("0.00"),
                monto_descuento=Decimal("0.00"),
                fecha_emision=ahora.date(),
                fecha_vencimiento=presupuesto.fecha_vencimiento,
                estado="EMITIDA",
                dias_gracia_aplicados=condominio.dias_gracia,
            )
            self.session.add(cuota)
            await self.session.flush()
            aplicacion = await saldos.aplicar_a_cuota_emitida(cuota, actor)
            cubiertas += int(
                aplicacion.estado_posterior == "PAGADA" and aplicacion.monto_aplicado > 0
            )
        lote = LoteCuotas(
            id=uuid4(),
            condominio_id=cid,
            presupuesto_id=presupuesto.id,
            periodo=request.periodo,
            metodo=distribucion.metodo.value,
            actor_id=actor.id,
            total_cuotas_emitidas=len(departamentos),
            monto_total_facturado=presupuesto.monto_total,
            cuotas_cubiertas_saldo_favor=cubiertas,
            fecha_emision=ahora,
            fecha_vencimiento=presupuesto.fecha_vencimiento,
        )
        self.session.add(lote)
        await self.session.flush()
        respuesta = EmitirLoteCuotasResponse(
            lote_id=lote.id,
            periodo=lote.periodo,
            total_cuotas_emitidas=len(departamentos),
            monto_total_facturado=lote.monto_total_facturado,
            cuotas_cubiertas_saldo_favor=cubiertas,
            fecha_emision=ahora,
            fecha_vencimiento=lote.fecha_vencimiento,
        )
        previo = await SQLAlchemySaldoFavorRepository(self.session).obtener_ultimo_hash_auditoria(
            cid
        )
        payload = AuditoriaPayload(
            condominio_id=str(cid),
            departamento_id=None,
            accion_ejecutada="LOTE_CUOTAS_EMITIDO",
            motivo="EMISION_MENSUAL_CON11",
            resultado="EXITOSO",
            actor_tipo=actor.rol,
            actor_id=actor.id,
            estado_anterior={},
            estado_posterior=respuesta.model_dump(mode="json"),
            hash_previo=previo,
        )
        self.session.add(
            AuditoriaLogORM(
                condominio_id=cid,
                departamento_id=None,
                timestamp=payload.timestamp,
                accion_ejecutada=payload.accion_ejecutada,
                motivo=payload.motivo,
                resultado=payload.resultado,
                actor_tipo=actor.rol,
                actor_id=actor.id,
                estado_anterior=payload.estado_anterior,
                estado_posterior=payload.estado_posterior,
                hash_previo=previo,
                hash_actual=payload.calcular_hash(),
            )
        )
        event_id = uuid4()
        self.session.add(
            EventoLoteOutbox(
                id=event_id,
                lote_id=lote.id,
                payload={
                    "event_id": str(event_id),
                    "event_type": "CuotasEmitidasEvent",
                    "producer": "service.cuotas",
                    "occurred_at": ahora.isoformat(),
                    "data": {
                        "condominio_id": str(cid),
                        "presupuesto_id": str(presupuesto.id),
                        "metodo": lote.metodo,
                        **respuesta.model_dump(mode="json"),
                    },
                },
            )
        )
        await self.session.flush()
        return respuesta
