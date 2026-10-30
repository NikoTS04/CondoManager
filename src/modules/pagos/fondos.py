"""Fondos por edificio; todos los llamadores conservan el lock del condominio."""

from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from src.core.errors import APIError
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.pagos.calculo_diario import es_diaria
from src.modules.pagos.contabilidad import CERO
from src.modules.pagos.fondos_models import (
    AplicacionMoras,
    CobroMoraFondo,
    EventoFondoMorasOutbox,
    MovimientoFondoMoras,
)
from src.modules.pagos.models_mora import MovimientoImputacionDiaria
from src.modules.pagos.repository import SQLAlchemyPagosRepository

LIMA = ZoneInfo("America/Lima")


def datos_aplicacion(a):
    return {
        "id": str(a.id),
        "presupuesto_id": str(a.presupuesto_id),
        "item_id": str(a.item_id),
        "edificio_id": str(a.edificio_id),
        "monto": f"{a.monto:.2f}",
        "motivo": a.motivo,
        "estado": a.estado,
        "creado_en": a.creado_en.isoformat(),
    }


class FondosMorasService:
    def __init__(self, session):
        self.session = session

    async def saldo(self, cid, eid, moneda):
        return await self.session.scalar(
            select(func.coalesce(func.sum(MovimientoFondoMoras.importe), 0)).where(
                MovimientoFondoMoras.condominio_id == cid,
                MovimientoFondoMoras.edificio_id == eid,
                MovimientoFondoMoras.moneda == moneda,
            )
        )

    def evento(self, id, cid, eid, moneda, tipo, importe, *, aplicacion=None):
        self.session.add(
            EventoFondoMorasOutbox(
                id=id,
                edificio_id=eid,
                payload={
                    "event_id": str(id),
                    "event_type": "FondosMorasActualizadosEvent",
                    "schema_version": 1,
                    "producer": "service.pagos",
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "data": {
                        "condominio_id": str(cid),
                        "edificio_id": str(eid),
                        "moneda": moneda,
                        "tipo": tipo,
                        "importe": f"{importe:.2f}",
                        "aplicacion_id": str(aplicacion.id) if aplicacion else None,
                        "presupuesto_id": str(aplicacion.presupuesto_id) if aplicacion else None,
                    },
                },
            )
        )

    async def registrar_cobros(
        self, depto, condominio, anteriores, actuales, fuentes, actor, *, legacy=None
    ):
        pares = {
            (pid, cid)
            for pid, cid, componente in set(anteriores) | set(actuales)
            if componente == "MORA"
        }
        existentes = {
            (c.comprobante_id, c.cuota_id): c
            for c in await self.session.scalars(
                select(CobroMoraFondo).where(
                    CobroMoraFondo.comprobante_id.in_([p for p, _ in pares])
                )
            )
        }
        registrados = dict(
            (
                await self.session.execute(
                    select(MovimientoFondoMoras.cobro_id, func.sum(MovimientoFondoMoras.importe))
                    .where(MovimientoFondoMoras.cobro_id.in_([c.id for c in existentes.values()]))
                    .group_by(MovimientoFondoMoras.cobro_id)
                )
            ).all()
        )
        nuevos, cambios = [], []
        por_fondo = defaultdict(lambda: CERO)
        for pid, cuota_id in sorted(pares):
            clave = (pid, cuota_id, "MORA")
            c = existentes.get((pid, cuota_id))
            if c is None:
                # El cobro anterior a esta adopción no acredita caja histórica disponible.
                c = CobroMoraFondo(
                    id=uuid4(),
                    comprobante_id=pid,
                    cuota_id=cuota_id,
                    condominio_id=condominio.id,
                    edificio_id=depto.edificio_id,
                    moneda=condominio.moneda,
                    base_no_adoptada=anteriores.get(clave, CERO),
                )
                nuevos.append(c)
            if c.condominio_id != condominio.id:
                raise APIError(
                    409,
                    "COBRO_MORA_OTRO_CONTEXTO",
                    "Concilie el fondo de origen antes de mover sus cobros.",
                )
            deseado = max(actuales.get(clave, CERO) - c.base_no_adoptada, CERO)
            diferencia = deseado - registrados.get(c.id, CERO)
            if diferencia:
                cambios.append((c, diferencia, fuentes.get(clave)))
                por_fondo[c.edificio_id, c.moneda] += diferencia
        saldos_previos = {}
        for (eid, moneda), diferencia in por_fondo.items():
            saldos_previos[eid, moneda] = await self.saldo(condominio.id, eid, moneda)
            if saldos_previos[eid, moneda] + diferencia < CERO:
                raise APIError(
                    409,
                    "FONDOS_MORAS_COMPROMETIDOS",
                    "La corrección afecta moras reservadas o aplicadas. Libere reservas o concilie financiación real.",
                )
        self.session.add_all(nuevos)
        # Las fuentes de la conciliación y los cobros son padres del movimiento.
        # Persistirlos en esta transacción evita depender del orden de los mappers.
        await self.session.flush()
        for c, diferencia, fuente in cambios:
            id = uuid4()
            self.session.add(
                MovimientoFondoMoras(
                    id=id,
                    condominio_id=c.condominio_id,
                    edificio_id=c.edificio_id,
                    moneda=c.moneda,
                    tipo="COBRO",
                    importe=diferencia,
                    cobro_id=c.id,
                    movimiento_diario_id=fuente.id if fuente else None,
                    imputacion_legacy_id=legacy.get((c.comprobante_id, c.cuota_id))
                    if legacy
                    else None,
                )
            )
            self.evento(id, c.condominio_id, c.edificio_id, c.moneda, "COBRO", diferencia)
        if nuevos or cambios:
            await SQLAlchemyPagosRepository(self.session).auditar(
                actor,
                condominio.id,
                depto.id,
                "FONDO_MORAS_COBROS_REGISTRADOS",
                "COMPONENTE_MORA_CONCILIADO",
                {
                    "disponible": {
                        f"{eid}:{moneda}": f"{saldo:.2f}"
                        for (eid, moneda), saldo in saldos_previos.items()
                    }
                },
                {
                    "disponible": {
                        f"{eid}:{moneda}": f"{saldo + por_fondo[eid, moneda]:.2f}"
                        for (eid, moneda), saldo in saldos_previos.items()
                    },
                    "bases_no_adoptadas": {str(c.id): f"{c.base_no_adoptada:.2f}" for c in nuevos},
                    "cobros": [
                        {"cobro_id": str(c.id), "importe": f"{importe:.2f}"}
                        for c, importe, _ in cambios
                    ],
                },
            )

    async def aplicaciones(self, presupuesto_id):
        return list(
            await self.session.scalars(
                select(AplicacionMoras)
                .where(AplicacionMoras.presupuesto_id == presupuesto_id)
                .order_by(AplicacionMoras.creado_en, AplicacionMoras.id)
            )
        )

    async def coberturas(self, presupuesto_id):
        return (
            [a for a in await self.aplicaciones(presupuesto_id) if a.estado != "LIBERADA"]
            if presupuesto_id
            else []
        )

    async def resumen(self, cid, eid, moneda, periodo):
        inicio = datetime.fromisoformat(periodo + "-01").replace(tzinfo=LIMA)
        fin = (
            None
            if periodo == "9999-12"
            else inicio.replace(year=inicio.year + 1, month=1)
            if inicio.month == 12
            else inicio.replace(month=inicio.month + 1)
        )
        filtro = (
            MovimientoFondoMoras.condominio_id == cid,
            MovimientoFondoMoras.edificio_id == eid,
            MovimientoFondoMoras.moneda == moneda,
        )
        saldo_inicial = await self.session.scalar(
            select(func.coalesce(func.sum(MovimientoFondoMoras.importe), 0)).where(
                *filtro, MovimientoFondoMoras.creado_en < inicio
            )
        )
        movimientos = list(
            await self.session.scalars(
                select(MovimientoFondoMoras)
                .where(
                    *filtro,
                    MovimientoFondoMoras.creado_en >= inicio,
                    *([MovimientoFondoMoras.creado_en < fin] if fin else []),
                )
                .order_by(MovimientoFondoMoras.creado_en, MovimientoFondoMoras.id)
            )
        )
        estados = dict(
            (
                await self.session.execute(
                    select(AplicacionMoras.estado, func.sum(AplicacionMoras.monto))
                    .join(PresupuestoMensual)
                    .where(
                        PresupuestoMensual.condominio_id == cid,
                        PresupuestoMensual.moneda == moneda,
                        AplicacionMoras.edificio_id == eid,
                    )
                    .group_by(AplicacionMoras.estado)
                )
            ).all()
        )
        confirmadas_periodo = await self.session.scalar(
            select(func.coalesce(func.sum(AplicacionMoras.monto), 0))
            .join(PresupuestoMensual)
            .where(
                PresupuestoMensual.condominio_id == cid,
                PresupuestoMensual.moneda == moneda,
                AplicacionMoras.edificio_id == eid,
                AplicacionMoras.estado == "CONFIRMADA",
                AplicacionMoras.actualizado_en >= inicio,
                *([AplicacionMoras.actualizado_en < fin] if fin else []),
            )
        )
        cuotas = list(
            await self.session.scalars(
                select(CuotaMantenimiento).join(Departamento).where(Departamento.edificio_id == eid)
            )
        )
        cobrada = dict(
            (
                await self.session.execute(
                    select(
                        MovimientoImputacionDiaria.cuota_id,
                        func.sum(MovimientoImputacionDiaria.importe),
                    )
                    .where(
                        MovimientoImputacionDiaria.cuota_id.in_([c.id for c in cuotas]),
                        MovimientoImputacionDiaria.componente == "MORA",
                    )
                    .group_by(MovimientoImputacionDiaria.cuota_id)
                )
            ).all()
        )
        pendiente = sum(
            (
                max(
                    c.monto_mora - (cobrada.get(c.id, CERO) if es_diaria(c) else c.monto_pagado),
                    CERO,
                )
                for c in cuotas
            ),
            CERO,
        )
        sumas = {
            t: sum((m.importe for m in movimientos if m.tipo == t), CERO)
            for t in ("COBRO", "RESERVA", "LIBERACION")
        }
        return {
            "edificio_id": str(eid),
            "periodo": periodo,
            "moneda": moneda,
            "saldo_disponible": f"{await self.saldo(cid, eid, moneda):.2f}",
            "saldo_reservado": f"{estados.get('RESERVADA', CERO):.2f}",
            "total_aplicado": f"{estados.get('CONFIRMADA', CERO):.2f}",
            "saldo_disponible_inicial": f"{saldo_inicial:.2f}",
            "cobros_netos_periodo": f"{sumas['COBRO']:.2f}",
            "cobros_confirmados_periodo": f"{sum((m.importe for m in movimientos if m.tipo == 'COBRO' and m.importe > 0), CERO):.2f}",
            "reversos_cobro_periodo": f"{-sum((m.importe for m in movimientos if m.tipo == 'COBRO' and m.importe < 0), CERO):.2f}",
            "aplicaciones_confirmadas_periodo": f"{confirmadas_periodo:.2f}",
            "reservas_periodo": f"{-sumas['RESERVA']:.2f}",
            "liberaciones_periodo": f"{sumas['LIBERACION']:.2f}",
            "saldo_disponible_final": f"{saldo_inicial + sum(sumas.values(), CERO):.2f}",
            "mora_pendiente_cobro": f"{pendiente:.2f}",
            "capturado_en": datetime.now(UTC).isoformat(),
            "movimientos": [
                {
                    "id": str(m.id),
                    "tipo": m.tipo,
                    "importe": f"{m.importe:.2f}",
                    "fecha_local": m.creado_en.astimezone(LIMA).date().isoformat(),
                    "aplicacion_id": str(m.aplicacion_id) if m.aplicacion_id else None,
                    "cobro_id": str(m.cobro_id) if m.cobro_id else None,
                }
                for m in movimientos
            ],
        }

    async def recalcular_borrador(self, p):
        from src.modules.cuotas.presupuestos.repository import SQLAlchemyPresupuestoRepository

        aplicaciones = await self.coberturas(p.id)
        items = deepcopy(p.items)
        for item in items:
            item["monto_cubierto_moras"] = (
                f"{sum((a.monto for a in aplicaciones if str(a.item_id) == item['id']), CERO):.2f}"
            )
        detalle = await SQLAlchemyPresupuestoRepository(self.session).preparar_detalle(
            p.condominio_id, items, p.id
        )
        p.items, p.monto_total = items, Decimal(detalle["monto_total"])
        p.version += 1
        p.actualizado_en = datetime.now(UTC)

    async def reservar(self, p, request, clave, actor):
        from src.modules.cuotas.presupuestos.repository import SQLAlchemyPresupuestoRepository

        previo = await self.session.scalar(
            select(AplicacionMoras).where(
                AplicacionMoras.presupuesto_id == p.id, AplicacionMoras.clave_idempotencia == clave
            )
        )
        if previo:
            if (
                previo.item_id,
                previo.edificio_id,
                previo.monto,
                previo.motivo,
                previo.version_solicitada,
            ) != (
                request.item_id,
                request.edificio_id,
                request.monto,
                request.motivo,
                request.version_esperada,
            ):
                raise APIError(
                    409, "IDEMPOTENCIA_CONFLICTO", "La clave ya identifica otra solicitud."
                )
            return previo
        self.validar_borrador(p, request.version_esperada)
        if not p.items or not any(i["id"] == str(request.item_id) for i in p.items):
            raise APIError(
                422, "ITEM_NO_ENCONTRADO", "Seleccione un ítem del presupuesto detallado."
            )
        saldo = await self.saldo(p.condominio_id, request.edificio_id, p.moneda)
        if request.monto > saldo:
            raise APIError(
                409,
                "FONDOS_MORAS_INSUFICIENTES",
                "El fondo disponible del edificio es insuficiente.",
            )
        detalle = await SQLAlchemyPresupuestoRepository(self.session).preparar_detalle(
            p.condominio_id, p.items, p.id
        )
        gasto = next((i for i in detalle["items"] if i["id"] == str(request.item_id)), None)
        asignacion = next(
            (a for a in gasto["asignaciones"] if a["edificio_id"] == str(request.edificio_id)), None
        )
        if (
            gasto["tipo_movimiento"] != "CARGO"
            or asignacion is None
            or request.monto > Decimal(asignacion["monto"])
        ):
            raise APIError(
                422,
                "COBERTURA_EXCEDE_GASTO",
                "La cobertura debe financiar un cargo pendiente de ese edificio.",
            )
        a = AplicacionMoras(
            id=uuid4(),
            presupuesto_id=p.id,
            item_id=request.item_id,
            edificio_id=request.edificio_id,
            monto=request.monto,
            motivo=request.motivo,
            clave_idempotencia=clave,
            version_solicitada=request.version_esperada,
            estado="RESERVADA",
        )
        self.session.add(a)
        await self.session.flush()
        self.movimiento_aplicacion(p, a, "RESERVA", -a.monto)
        await self.recalcular_borrador(p)
        await self.auditar_aplicacion(p, a, actor, None)
        return a

    async def liberar(self, p, a, version, actor):
        if a.estado == "LIBERADA":
            return
        self.validar_borrador(p, version)
        if a.estado != "RESERVADA":
            raise APIError(409, "APLICACION_CONFIRMADA", "No se elimina una cobertura confirmada.")
        a.estado, a.actualizado_en = "LIBERADA", datetime.now(UTC)
        self.movimiento_aplicacion(p, a, "LIBERACION", a.monto)
        await self.recalcular_borrador(p)
        await self.auditar_aplicacion(p, a, actor, "RESERVADA")

    def movimiento_aplicacion(self, p, a, tipo, importe):
        id = uuid4()
        self.session.add(
            MovimientoFondoMoras(
                id=id,
                condominio_id=p.condominio_id,
                edificio_id=a.edificio_id,
                moneda=p.moneda,
                tipo=tipo,
                importe=importe,
                aplicacion_id=a.id,
            )
        )
        self.evento(id, p.condominio_id, a.edificio_id, p.moneda, tipo, importe, aplicacion=a)

    async def confirmar(self, p, actor):
        for a in await self.coberturas(p.id):
            if await self.saldo(p.condominio_id, a.edificio_id, p.moneda) < CERO:
                raise APIError(
                    409, "FONDOS_MORAS_INSUFICIENTES", "El fondo no respalda la cobertura."
                )
            if a.estado == "RESERVADA":
                a.estado, a.actualizado_en = "CONFIRMADA", datetime.now(UTC)
                self.evento(
                    uuid4(),
                    p.condominio_id,
                    a.edificio_id,
                    p.moneda,
                    "CONFIRMACION",
                    CERO,
                    aplicacion=a,
                )
                await self.auditar_aplicacion(p, a, actor, "RESERVADA")

    async def auditar_aplicacion(self, p, a, actor, anterior):
        disponible = await self.saldo(p.condominio_id, a.edificio_id, p.moneda)
        delta = -a.monto if a.estado == "RESERVADA" else a.monto if a.estado == "LIBERADA" else CERO
        await SQLAlchemyPagosRepository(self.session).auditar(
            actor,
            p.condominio_id,
            None,
            f"FONDO_MORAS_{a.estado}",
            a.motivo,
            {
                "estado": anterior,
                "saldo_disponible": f"{disponible - delta:.2f}",
                "monto_total": f"{p.monto_total - delta:.2f}",
            },
            {
                **datos_aplicacion(a),
                "presupuesto_version": p.version,
                "saldo_disponible": f"{disponible:.2f}",
                "monto_total": f"{p.monto_total:.2f}",
            },
        )

    @staticmethod
    def validar_borrador(p, version):
        if p.estado != "BORRADOR":
            raise APIError(409, "PRESUPUESTO_NO_EDITABLE", "El presupuesto aprobado es inmutable.")
        if p.version != version:
            raise APIError(
                409,
                "PRESUPUESTO_VERSION_OBSOLETA",
                "Recargue el presupuesto antes de cambiar coberturas.",
            )
