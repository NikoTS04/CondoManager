"""CON-22/70: operaciones financieras reales; nunca usa el almacén piloto."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import contexto_consulta, puede_ver_departamento
from src.core.database import get_db_session
from src.core.errors import APIError
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.pagos.contabilidad import CERO, MAX_MONEDA, plan_imputacion, saldo_en_mora
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox, RevisionPago
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.schemas import (
    ComprobantePagoDTO,
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ConciliarPagoRequest,
    ReportarPagoRequest,
    VoucherSubidoResponse,
)
from src.modules.pagos.service import PagosService
from src.modules.pagos.storage import MAX_BYTES, VoucherStorage
from src.shared.decimal_types import redondear_moneda


class PagosPersistentesService:
    def __init__(self, session: AsyncSession, storage: VoucherStorage | None = None):
        self.session = session
        self.repo = SQLAlchemyPagosRepository(session)
        self.storage = storage or VoucherStorage()

    @staticmethod
    def dto(c: ComprobantePago) -> ComprobantePagoDTO:
        return ComprobantePagoDTO(
            id=c.id,
            departamento_id=c.departamento_id,
            banco=c.banco_origen,
            numero_operacion=c.numero_operacion,
            fecha_operacion=c.fecha_operacion,
            monto=c.monto,
            estado="CONCILIADO" if c.estado == "APROBADO" else c.estado,
            idempotency_hash=c.idempotency_hash,
            url_voucher=c.url_voucher,
            motivo_rechazo=c.motivo_rechazo,
        )

    async def listar(self, usuario, condominio_id=None):
        cid = contexto_consulta(usuario, condominio_id)
        async with self.session.begin():
            query = (
                select(ComprobantePago)
                .join(Departamento, ComprobantePago.departamento_id == Departamento.id)
                .join(Edificio, Departamento.edificio_id == Edificio.id)
                .where(Edificio.condominio_id == cid)
                .order_by(ComprobantePago.creado_en.desc(), ComprobantePago.id)
            )
            return [
                self.dto(c)
                for c in await self.session.scalars(query)
                if puede_ver_departamento(usuario, c.departamento_id)
            ]

    async def departamentos_portal(self, usuario, condominio_id=None):
        cid = contexto_consulta(usuario, condominio_id)
        async with self.session.begin():
            condominio = await self.session.get(Condominio, cid)
            if condominio is None or not condominio.activo:
                raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo.")
            departamentos = await self.session.scalars(
                select(Departamento)
                .join(Edificio)
                .where(Edificio.condominio_id == cid, Departamento.activo.is_(True))
                .order_by(Departamento.numero, Departamento.id)
            )
            resultado = []
            for depto in departamentos:
                if not puede_ver_departamento(usuario, depto.id):
                    continue
                cuotas = await self.repo.cuotas(depto.id)
                saldo = saldo_en_mora(cuotas, condominio.dias_gracia, datetime.now(UTC).date())
                resultado.append(
                    {
                        "id": depto.id,
                        "condominio_id": cid,
                        "numero": depto.numero,
                        "piso": depto.piso,
                        "coeficiente": depto.coeficiente_participacion,
                        "saldo_a_favor": depto.saldo_a_favor,
                        "estado_financiero": "EN_MORA" if saldo > CERO else "AL_DIA",
                        "deuda_vencida": saldo,
                        "activo": depto.activo,
                    }
                )
            return resultado

    async def subir(self, did: UUID, archivo: UploadFile, usuario: dict):
        async with self.session.begin():
            await self.repo.departamento(did, usuario, escritura=True, bloquear=True)
            datos = await archivo.read(MAX_BYTES + 1)
            nombre, content_type = await asyncio.to_thread(self.storage.guardar, datos)
            try:
                self.session.add(
                    ArchivoVoucher(
                        nombre=nombre,
                        departamento_id=did,
                        usuario_id=UUID(usuario["sub"]),
                        content_type=content_type,
                        size_bytes=len(datos),
                    )
                )
                await self.session.flush()
            except Exception:
                await asyncio.to_thread(self.storage.eliminar, nombre)
                raise
            resultado = VoucherSubidoResponse(
                url_voucher=nombre, content_type=content_type, size_bytes=len(datos)
            )
        # Si el commit pierde la conexión, el archivo se conserva para recuperación:
        # no se puede distinguir un commit confirmado de uno con respuesta perdida.
        return resultado

    async def reportar(self, request: ReportarPagoRequest, usuario: dict):
        async with self.session.begin():
            depto, condominio = await self.repo.departamento(
                request.departamento_id, usuario, escritura=True, bloquear=True
            )
            hash_id = PagosService.calcular_hash_idempotencia(
                str(condominio.id),
                request.banco,
                request.numero_operacion,
                request.fecha_operacion,
                request.monto,
            )
            previo = await self.session.scalar(
                select(ComprobantePago).where(ComprobantePago.idempotency_hash == hash_id)
            )
            if previo is not None:
                if previo.departamento_id != depto.id:
                    raise APIError(
                        409,
                        "VOUCHER_UNIDAD_DISTINTA",
                        "El comprobante no puede reutilizarse en otra unidad.",
                    )
                if previo.estado == "APROBADO":
                    raise APIError(
                        409, "VOUCHER_YA_CONCILIADO", "El comprobante ya fue conciliado."
                    )
                if previo.estado != "EN_REVISION":
                    raise APIError(
                        409,
                        "VOUCHER_REQUIERE_REVISION",
                        "El comprobante existente requiere revisión administrativa.",
                    )
                return ComprobanteRecibidoResponse(
                    comprobante_id=previo.id,
                    estado=previo.estado,
                    mensaje="El comprobante ya fue recibido y se encuentra en revisión.",
                    idempotency_hash=hash_id,
                    error_code="VOUCHER_EN_EVALUACION",
                ), False
            subida = await self.session.scalar(
                select(ArchivoVoucher)
                .where(ArchivoVoucher.nombre == request.url_voucher)
                .with_for_update()
            )
            if (
                subida is None
                or subida.departamento_id != depto.id
                or str(subida.usuario_id) != usuario["sub"]
                or subida.comprobante_id is not None
            ):
                raise APIError(
                    422, "VOUCHER_NO_AUTORIZADO", "Suba un voucher propio para este departamento."
                )
            await asyncio.to_thread(self.storage.ruta, subida.nombre)
            nuevo = ComprobantePago(
                id=uuid4(),
                departamento_id=depto.id,
                banco_origen=request.banco,
                numero_operacion=request.numero_operacion.strip(),
                fecha_operacion=request.fecha_operacion,
                monto=redondear_moneda(request.monto),
                url_voucher=subida.nombre,
                idempotency_hash=hash_id,
                estado="EN_REVISION",
            )
            self.session.add(nuevo)
            await self.session.flush()
            subida.comprobante_id = nuevo.id
            await self.repo.auditar(
                usuario,
                condominio.id,
                depto.id,
                "COMPROBANTE_REPORTADO",
                "REPORTE_PAGO_CON22",
                {},
                {
                    "comprobante_id": str(nuevo.id),
                    "estado": nuevo.estado,
                    "monto": str(nuevo.monto),
                },
            )
            self._evento(nuevo, condominio.id, "PagoReportadoEvent")
            await self.session.flush()
            resultado = ComprobanteRecibidoResponse(
                comprobante_id=nuevo.id,
                estado=nuevo.estado,
                mensaje="Comprobante recibido. Pendiente de revisión por la junta.",
                idempotency_hash=hash_id,
            )
        return resultado, True

    async def revisar(self, id: UUID, request: ConciliarPagoRequest, usuario: dict):
        if usuario.get("rol") not in {"SUPERADMIN", "ADMIN_JUNTA"}:
            raise APIError(403, "ACCESO_DENEGADO", "Solo la administración puede revisar pagos.")
        motivo = (request.motivo_rechazo or request.notas_internas or "").strip()
        if request.decision != "APROBADO" and not motivo:
            raise APIError(422, "MOTIVO_REQUERIDO", "Indique el motivo de observación o rechazo.")
        async with self.session.begin():
            comprobante, depto, condominio = await self.repo.comprobante(
                id, usuario, escritura=True, bloquear=True
            )
            cuotas = await self.repo.cuotas(depto.id, bloquear=True)
            comprobante = await self.session.scalar(
                select(ComprobantePago)
                .where(ComprobantePago.id == id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if comprobante.estado not in {"EN_REVISION", "OBSERVADO"}:
                raise APIError(
                    409,
                    "COMPROBANTE_YA_REVISADO",
                    "La decisión ya es definitiva; no se vuelve a aplicar.",
                )
            ahora = datetime.now(UTC)
            anterior = {"estado": comprobante.estado, "saldo_a_favor": str(depto.saldo_a_favor)}
            total_aplicado, credito = CERO, CERO
            if request.decision == "APROBADO":
                plan = plan_imputacion(cuotas, comprobante.monto, ahora.date())
                credito = plan["remanente"]
                if depto.saldo_a_favor + credito > MAX_MONEDA:
                    raise APIError(
                        422, "SALDO_FUERA_DE_RANGO", "El saldo a favor excede el límite contable."
                    )
                for cuota in cuotas:
                    aplicado = plan["aplicaciones"].get(cuota.id, CERO)
                    if aplicado <= CERO:
                        continue
                    cuota.monto_pagado += aplicado
                    if cuota.monto_pagado == cuota.monto_total_exigible:
                        cuota.estado = "PAGADA"
                    elif saldo_en_mora([cuota], condominio.dias_gracia, ahora.date()) > CERO:
                        cuota.estado = "EN_MORA"
                    else:
                        cuota.estado = "PAGO_PARCIAL"
                    self.session.add(
                        ImputacionPago(
                            comprobante_id=id,
                            cuota_id=cuota.id,
                            monto_aplicado=aplicado,
                        )
                    )
                    total_aplicado += aplicado
                depto.saldo_a_favor += credito
                depto.estado_financiero = (
                    "EN_MORA"
                    if saldo_en_mora(cuotas, condominio.dias_gracia, ahora.date()) > CERO
                    else "AL_DIA"
                )
            comprobante.estado = request.decision
            comprobante.motivo_rechazo = motivo if request.decision != "APROBADO" else None
            comprobante.conciliado_por = UUID(usuario["sub"])
            comprobante.conciliado_en = ahora
            resultado = ConciliacionResultResponse(
                comprobante_id=id,
                estado_final=request.decision,
                monto_imputado=total_aplicado,
                nuevo_saldo_departamento=sum(
                    (c.monto_total_exigible - c.monto_pagado for c in cuotas), CERO
                ),
                saldo_a_favor_generado=credito,
                departamento_habilitado_reservas=saldo_en_mora(
                    cuotas, condominio.dias_gracia, ahora.date()
                )
                == CERO,
            )
            revision = RevisionPago(
                id=uuid4(),
                comprobante_id=id,
                decision=request.decision,
                motivo=motivo or None,
                actor_id=UUID(usuario["sub"]),
                creado_en=ahora,
                resultado=resultado.model_dump(mode="json"),
            )
            self.session.add(revision)
            await self.repo.auditar(
                usuario,
                condominio.id,
                depto.id,
                f"REVISION_PAGO_{request.decision}",
                motivo or "APROBACION_PAGO_CON70",
                anterior,
                {**resultado.model_dump(mode="json"), "saldo_a_favor": str(depto.saldo_a_favor)},
            )
            evento = {
                "APROBADO": "PagoConciliadoEvent",
                "OBSERVADO": "PagoObservadoEvent",
                "RECHAZADO": "PagoRechazadoEvent",
            }[request.decision]
            self._evento(
                comprobante,
                condominio.id,
                evento,
                {
                    "revision_id": str(revision.id),
                    "motivo": motivo or None,
                    "resultado": revision.resultado,
                },
            )
            await self.session.flush()
        return resultado

    async def resultado(self, id, usuario):
        async with self.session.begin():
            await self.repo.comprobante(id, usuario)
            revision = await self.session.scalar(
                select(RevisionPago)
                .where(RevisionPago.comprobante_id == id)
                .order_by(RevisionPago.creado_en.desc(), RevisionPago.id.desc())
                .limit(1)
            )
            if revision is None:
                raise APIError(
                    404, "RESULTADO_NO_DISPONIBLE", "El comprobante aún no tiene revisión."
                )
            return ConciliacionResultResponse.model_validate(revision.resultado)

    async def voucher(self, id, usuario):
        async with self.session.begin():
            comprobante, _, _ = await self.repo.comprobante(id, usuario)
            ruta = await asyncio.to_thread(self.storage.ruta, comprobante.url_voucher)
            return ruta, comprobante.url_voucher

    def _evento(self, comprobante, cid, tipo, extra=None):
        id = uuid4()
        ahora = datetime.now(UTC)
        compatibilidad = {}
        if tipo == "PagoConciliadoEvent":
            resultado = extra["resultado"]
            compatibilidad = {
                "comprobante_id": str(comprobante.id),
                "departamento_id": str(comprobante.departamento_id),
                "monto_conciliado": resultado["monto_imputado"],
                "saldo_restante_departamento": resultado["nuevo_saldo_departamento"],
                "desbloqueo_reservas_habilitado": resultado["departamento_habilitado_reservas"],
            }
        self.session.add(
            EventoPagoOutbox(
                id=id,
                comprobante_id=comprobante.id,
                creado_en=ahora,
                payload={
                    "event_id": str(id),
                    "event_type": tipo,
                    "version": 1,
                    "producer": "service.pagos",
                    "occurred_at": ahora.isoformat(),
                    **compatibilidad,
                    "data": {
                        "comprobante_id": str(comprobante.id),
                        "departamento_id": str(comprobante.departamento_id),
                        "condominio_id": str(cid),
                        "estado": comprobante.estado,
                        "monto": str(comprobante.monto),
                        "motivo": None,
                        **(extra or {}),
                        **compatibilidad,
                    },
                },
            )
        )


def get_pagos_service(session: AsyncSession = Depends(get_db_session, use_cache=False)):
    # La sesión financiera es distinta de la consulta de autenticación.
    return PagosPersistentesService(session)
