"""Proyección transaccional del ledger diario bajo locks condominio/unidad/cuotas."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from src.core.errors import APIError
from src.modules.pagos.calculo_diario import CuotaCalculo, es_diaria, reconstruir
from src.modules.pagos.contabilidad import CERO, MAX_MONEDA, saldo_en_mora
from src.modules.pagos.fondos import FondosMorasService
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_mora import (
    AjusteDevengoMora,
    ConciliacionDiaria,
    DevengoMora,
    EventoMoraOutbox,
    MovimientoImputacionDiaria,
)
from src.modules.pagos.repository import SQLAlchemyPagosRepository


class MoraDiariaService:
    def __init__(self, session):
        self.session = session

    async def reconstruir(
        self,
        departamento,
        condominio,
        cuotas,
        actor,
        hoy,
        *,
        nuevo=None,
        pausar_revision=True,
        ahora=None,
    ):
        """El llamador posee locks y transacción; cualquier fallo revierte también el pago."""
        ahora = ahora or datetime.now(UTC)
        comprobantes = list(
            await self.session.scalars(
                select(ComprobantePago)
                .where(ComprobantePago.departamento_id == departamento.id)
                .order_by(ComprobantePago.id)
            )
        )
        ids = [p.id for p in comprobantes]
        anteriores = defaultdict(lambda: CERO)
        for m in await self.session.scalars(
            select(MovimientoImputacionDiaria).where(
                MovimientoImputacionDiaria.comprobante_id.in_(ids)
            )
        ):
            anteriores[m.comprobante_id, m.cuota_id, m.componente] += m.importe
        if not any(es_diaria(c) for c in cuotas) and not anteriores:
            return None
        alcances = {
            p.comprobante_id: {UUID(id) for id in p.cuotas_evaluadas}
            for p in await self.session.scalars(
                select(ConciliacionDiaria).where(ConciliacionDiaria.comprobante_id.in_(ids))
            )
        }
        gestionados = set(alcances)
        if not {pid for pid, _, _ in anteriores}.issubset(gestionados):
            raise APIError(
                409, "LEDGER_DIARIO_INVALIDO", "Falta el alcance histórico de la conciliación."
            )
        pagos = [p for p in comprobantes if p.id in gestionados]
        if any(p.estado != "APROBADO" for p in pagos):
            raise APIError(
                409, "LEDGER_DIARIO_INVALIDO", "Revise los comprobantes de la reconstrucción."
            )
        if nuevo is not None:
            pagos.append(nuevo)
            alcances[nuevo.id] = {c.id for c in cuotas}
        devengos = list(
            await self.session.scalars(
                select(DevengoMora).where(DevengoMora.cuota_id.in_([c.id for c in cuotas]))
            )
        )
        por_fecha = {(d.cuota_id, d.fecha_local): d for d in devengos}
        netos = {d.id: d.importe for d in devengos}
        for a in await self.session.scalars(
            select(AjusteDevengoMora).where(AjusteDevengoMora.devengo_id.in_(netos))
        ):
            netos[a.devengo_id] += a.importe
        mora_previa, pagos_previos = defaultdict(lambda: CERO), defaultdict(lambda: CERO)
        for d in devengos:
            mora_previa[d.cuota_id] += netos[d.id]
        for (_, cid, componente), importe in anteriores.items():
            if componente != "CREDITO":
                pagos_previos[cid] += importe
        bases = [
            CuotaCalculo(
                id=c.id,
                periodo=c.periodo,
                fecha_emision=c.fecha_emision,
                fecha_vencimiento=c.fecha_vencimiento,
                monto_total_exigible=c.monto_total_exigible - mora_previa[c.id],
                monto_extraordinario=c.monto_extraordinario,
                monto_mora=c.monto_mora - mora_previa[c.id],
                monto_pagado=c.monto_pagado - pagos_previos[c.id],
                politica_mora_aplicada=c.politica_mora_aplicada,
            )
            for c in cuotas
        ]
        if any(c.monto_pagado < CERO or c.monto_mora < CERO for c in bases):
            raise APIError(
                409, "BASE_FINANCIERA_INVALIDA", "El ledger no coincide con las amortizaciones."
            )
        reportes_pendientes = [p.creado_en for p in comprobantes if p.estado == "EN_REVISION"]
        pausado = (
            pausar_revision
            and bool(reportes_pendientes)
            and min(reportes_pendientes) > ahora - timedelta(hours=24)
        )
        # Nunca retirar cargos por reejecutar con un reloj anterior al último corte.
        hasta = max([hoy] + [d.fecha_local for d in devengos])
        limites = (
            {
                c.id: max(
                    [c.fecha_emision - timedelta(days=1)]
                    + [d.fecha_local for d in devengos if d.cuota_id == c.id]
                )
                for c in cuotas
            }
            if pausado
            else None
        )
        calculo = reconstruir(bases, pagos, hasta, limites, alcances)
        movimientos = calculo["movimientos"]
        credito_previo = sum((v for k, v in anteriores.items() if k[2] == "CREDITO"), CERO)
        credito_actual = sum((v for k, v in movimientos.items() if k[2] == "CREDITO"), CERO)
        saldo = departamento.saldo_a_favor + credito_actual - credito_previo
        if saldo < CERO:
            raise APIError(
                409,
                "CREDITO_RETROACTIVO_CONSUMIDO",
                "El retroactivo necesita crédito ya utilizado. Concilie su financiación.",
            )
        if saldo > MAX_MONEDA:
            raise APIError(
                422, "SALDO_FUERA_DE_RANGO", "El saldo a favor excede el límite contable."
            )
        anterior = {
            "saldo_a_favor": f"{departamento.saldo_a_favor:.2f}",
            "estado_financiero": departamento.estado_financiero,
            "cuotas": {
                str(c.id): {
                    "mora": f"{c.monto_mora:.2f}",
                    "pagado": f"{c.monto_pagado:.2f}",
                    "total": f"{c.monto_total_exigible:.2f}",
                    "estado": c.estado,
                }
                for c in cuotas
            },
        }
        cambios = []
        causa = nuevo.id if nuevo else None
        if nuevo is not None:
            self.session.add(
                ConciliacionDiaria(
                    comprobante_id=nuevo.id,
                    cuotas_evaluadas=sorted(str(id) for id in alcances[nuevo.id]),
                    creado_en=ahora,
                )
            )
        for clave in sorted(set(por_fecha) | set(calculo["devengos"])):
            deseado = calculo["devengos"].get(clave, CERO)
            d = por_fecha.get(clave)
            diferencia = deseado - (netos[d.id] if d else CERO)
            if not diferencia:
                continue
            if d is None:
                eid = uuid5(NAMESPACE_URL, f"condomanager:mora:{clave[0]}:{clave[1]}")
                cuota = next(c for c in cuotas if c.id == clave[0])
                d = DevengoMora(
                    id=eid,
                    cuota_id=clave[0],
                    fecha_local=clave[1],
                    importe=deseado,
                    politica=cuota.politica_mora_aplicada,
                    creado_en=ahora,
                )
                self.session.add(d)
                tipo = "MoraAplicadaEvent"
            else:
                eid = uuid4()
                self.session.add(
                    AjusteDevengoMora(
                        id=eid,
                        devengo_id=d.id,
                        importe=diferencia,
                        comprobante_causante_id=causa,
                        creado_en=ahora,
                    )
                )
                tipo = "MoraAjustadaEvent"
            cambios.append((eid, tipo, d, diferencia))
        deltas = []
        fuentes = {}
        for clave in set(anteriores) | set(movimientos):
            diferencia = movimientos.get(clave, CERO) - anteriores.get(clave, CERO)
            if diferencia:
                movimiento = MovimientoImputacionDiaria(
                    id=uuid4(),
                    comprobante_id=clave[0],
                    cuota_id=clave[1],
                    componente=clave[2],
                    importe=diferencia,
                    comprobante_causante_id=causa,
                    creado_en=ahora,
                )
                self.session.add(movimiento)
                fuentes[clave] = movimiento
                deltas.append(
                    {
                        "comprobante_id": str(clave[0]),
                        "cuota_id": str(clave[1]) if clave[1] else None,
                        "componente": clave[2],
                        "importe": f"{diferencia:.2f}",
                    }
                )
        departamento.saldo_a_favor = saldo
        aplicaciones = defaultdict(lambda: CERO)
        for (pid, cid, componente), importe in movimientos.items():
            if nuevo is not None and pid == nuevo.id and componente != "CREDITO":
                aplicaciones[cid] += importe
        for cid, importe in aplicaciones.items():
            self.session.add(
                ImputacionPago(comprobante_id=nuevo.id, cuota_id=cid, monto_aplicado=importe)
            )
        for c in cuotas:
            r = calculo["cuotas"][c.id]
            c.monto_mora, c.monto_total_exigible, c.monto_pagado = (
                r["mora"],
                r["total"],
                r["pagado"],
            )
            if es_diaria(c) or deltas:
                c.estado = (
                    "PAGADA"
                    if c.monto_pagado == c.monto_total_exigible
                    else "EN_MORA"
                    if saldo_en_mora([c], condominio.dias_gracia, hoy) > CERO
                    else "PAGO_PARCIAL"
                    if c.monto_pagado
                    else "PENDIENTE"
                )
        await FondosMorasService(self.session).registrar_cobros(
            departamento, condominio, anteriores, movimientos, fuentes, actor
        )
        departamento.estado_financiero = (
            "EN_MORA" if saldo_en_mora(cuotas, condominio.dias_gracia, hoy) > CERO else "AL_DIA"
        )
        posterior = {
            "saldo_a_favor": f"{saldo:.2f}",
            "estado_financiero": departamento.estado_financiero,
            "cuotas": {
                str(c.id): {
                    "mora": f"{c.monto_mora:.2f}",
                    "pagado": f"{c.monto_pagado:.2f}",
                    "total": f"{c.monto_total_exigible:.2f}",
                    "estado": c.estado,
                }
                for c in cuotas
            },
        }
        if anterior != posterior or cambios or deltas:
            await SQLAlchemyPagosRepository(self.session).auditar(
                actor,
                condominio.id,
                departamento.id,
                "RECONSTRUCCION_MORA_DIARIA",
                "FECHA_BANCARIA_VALIDADA" if nuevo else "RECUPERACION_DEVENGOS_DIARIOS",
                anterior,
                {**posterior, "movimientos": deltas, "devengos_modificados": len(cambios)},
            )
        total_pendiente = sum((c.monto_total_exigible - c.monto_pagado for c in cuotas), CERO)
        for eid, tipo, d, diferencia in cambios:
            self.session.add(
                EventoMoraOutbox(
                    id=eid,
                    cuota_id=d.cuota_id,
                    creado_en=ahora,
                    payload={
                        "event_id": str(eid),
                        "event_type": tipo,
                        "schema_version": 2,
                        "producer": "service.pagos",
                        "occurred_at": ahora.isoformat(),
                        "data": {
                            "condominio_id": str(condominio.id),
                            "departamento_id": str(departamento.id),
                            "cuota_id": str(d.cuota_id),
                            "devengo_id": str(d.id),
                            "fecha_local": d.fecha_local.isoformat(),
                            "importe": f"{diferencia:.2f}",
                            "saldo_pendiente": f"{total_pendiente:.2f}",
                            "moneda": condominio.moneda,
                            "comprobante_causante_id": str(causa) if causa else None,
                        },
                    },
                )
            )
        await self.session.flush()
        return {
            "monto_imputado": sum(aplicaciones.values(), CERO),
            "credito": movimientos.get((causa, None, "CREDITO"), CERO),
            "devengos_modificados": len(cambios),
            "pausado": bool(pausado),
        }
