"""CON-14: proyección de lectura del historial financiero persistido por unidad."""

from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor
from src.modules.pagos.contabilidad import CERO, saldo_en_mora
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_mora import (
    AjusteDevengoMora,
    ConciliacionDiaria,
    DevengoMora,
    MovimientoImputacionDiaria,
)
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.shared.fechas import fecha_lima

LIMA = ZoneInfo("America/Lima")
router = APIRouter(prefix="/cuotas", tags=["Cuotas de Mantenimiento"])
DineroCuenta = Annotated[str, Field(pattern=r"^-?\d+\.\d{2}$")]


class MovimientoCuenta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    fecha: date
    registrado_en: datetime
    fecha_operacion: date | None
    tipo: Literal[
        "EMISION_CUOTA",
        "DEVENGO_MORA",
        "AJUSTE_MORA",
        "PAGO_APROBADO",
        "APLICACION_CREDITO",
        "DISTRIBUCION_PAGO",
    ]
    descripcion: str
    importe: DineroCuenta
    cargo: DineroCuenta
    abono: DineroCuenta
    saldo: DineroCuenta
    cuota_id: UUID | None
    comprobante_id: UUID | None
    origen_id: UUID
    periodo_cuota: str | None


class PagoEnRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    fecha_reporte: date
    fecha_operacion: date
    banco: str
    numero_operacion: str
    monto: DineroCuenta


class EstadoCuentaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    departamento_id: UUID
    condominio_id: UUID
    moneda: Literal["PEN", "USD"]
    desde: date
    hasta: date
    generado_en: datetime
    historial_desde: date | None
    base_historica_sin_fecha: bool
    credito_inicial_sin_desglose: DineroCuenta
    abonos_historicos_sin_desglose: DineroCuenta
    saldo_base_historico: DineroCuenta
    saldo_inicial: DineroCuenta
    cargos_periodo: DineroCuenta
    abonos_periodo: DineroCuenta
    saldo_final: DineroCuenta
    deuda_actual: DineroCuenta
    deuda_vencida_actual: DineroCuenta
    saldo_a_favor_actual: DineroCuenta
    saldo_neto_actual: DineroCuenta
    total_movimientos: int
    limite: int
    offset: int
    movimientos: list[MovimientoCuenta]
    pagos_en_revision: list[PagoEnRevision]


def rango_consulta(desde, hasta, hoy):
    if desde is None and hasta is None:
        desde = hoy.replace(day=1)
        hasta = hoy
        # La consulta predeterminada abarca el mes entero, incluido su último día.
        siguiente = date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1)
        hasta = date.fromordinal(siguiente.toordinal() - 1)
    if desde is None or hasta is None or hasta < desde or (hasta - desde).days >= 366:
        raise APIError(
            422, "RANGO_CUENTA_INVALIDO", "Indique un rango de 1 a 366 días con ambas fechas."
        )
    return desde, hasta


def inconsistente():
    raise APIError(
        409,
        "ESTADO_CUENTA_INCONSISTENTE",
        "El historial no concilia con los saldos registrados. Solicite una revisión a administración.",
    )


def instante(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return datetime.combine(value, time.min, tzinfo=LIMA).astimezone(UTC)


def dinero(value):
    return f"{value if value else CERO:.2f}"


def proyectar_cuenta(
    *,
    depto,
    condominio,
    cuotas,
    pagos,
    imputaciones,
    gestionados,
    devengos,
    ajustes,
    distribuciones,
    aplicaciones,
    desde,
    hasta,
    hoy,
    limite=50,
    offset=0,
):
    """No escribe ni reconstruye el motor. Una diferencia real no se tapa con un ajuste."""
    cuotas_por_id = {c.id: c for c in cuotas}
    aprobados = {p.id: p for p in pagos if p.estado == "APROBADO"}
    mora_neta, pagos_diarios, pagos_legacy, credito_aplicado = (
        defaultdict(lambda: CERO) for _ in range(4)
    )
    legacy_por_pago = defaultdict(lambda: CERO)
    credito_generado = CERO
    componentes_vigentes = defaultdict(lambda: CERO)
    total_diario_por_pago = defaultdict(lambda: CERO)
    por_devengo = {d.id: d for d in devengos}
    movimientos = []

    def agregar(
        tipo,
        origen,
        registrado,
        descripcion,
        importe,
        *,
        cuota=None,
        pago=None,
        financiero=True,
        fecha_operacion=None,
    ):
        registro = instante(registrado)
        cargo = max(importe, CERO) if financiero else CERO
        abono = max(-importe, CERO) if financiero else CERO
        movimientos.append(
            {
                "id": f"{tipo}:{origen}",
                "fecha": registro.astimezone(LIMA).date(),
                "registrado_en": registro,
                "fecha_operacion": fecha_operacion,
                "tipo": tipo,
                "descripcion": descripcion,
                "importe": dinero(importe),
                "cargo": dinero(cargo),
                "abono": dinero(abono),
                "saldo": "0.00",
                "cuota_id": cuota,
                "comprobante_id": pago,
                "origen_id": origen,
                "periodo_cuota": cuotas_por_id[cuota].periodo if cuota in cuotas_por_id else None,
            }
        )

    for d in devengos:
        mora_neta[d.cuota_id] += d.importe
        agregar(
            "DEVENGO_MORA",
            d.id,
            d.creado_en,
            "Mora devengada",
            d.importe,
            cuota=d.cuota_id,
            fecha_operacion=d.fecha_local,
        )
    for a in ajustes:
        d = por_devengo[a.devengo_id]
        mora_neta[d.cuota_id] += a.importe
        agregar(
            "AJUSTE_MORA",
            a.id,
            a.creado_en,
            "Corrección de mora",
            a.importe,
            cuota=d.cuota_id,
            pago=a.comprobante_causante_id,
            fecha_operacion=d.fecha_local,
        )
    for m in distribuciones:
        if m.comprobante_id not in aprobados or m.comprobante_id not in gestionados:
            inconsistente()
        if m.cuota_id is not None and m.cuota_id not in cuotas_por_id:
            inconsistente()
        componentes_vigentes[m.comprobante_id, m.cuota_id, m.componente] += m.importe
        total_diario_por_pago[m.comprobante_id] += m.importe
        if m.componente == "CREDITO":
            credito_generado += m.importe
        else:
            pagos_diarios[m.cuota_id] += m.importe
        descripcion = (
            "Compensación de aplicación de pago"
            if m.importe < CERO
            else "Crédito generado por pago"
            if m.componente == "CREDITO"
            else "Aplicación de pago a cuota"
        )
        agregar(
            "DISTRIBUCION_PAGO",
            m.id,
            m.creado_en,
            descripcion,
            m.importe,
            cuota=m.cuota_id,
            pago=m.comprobante_id,
            financiero=False,
        )
    for i in imputaciones:
        if i.comprobante_id in aprobados and i.comprobante_id not in gestionados:
            if i.cuota_id not in cuotas_por_id:
                inconsistente()
            pagos_legacy[i.cuota_id] += i.monto_aplicado
            legacy_por_pago[i.comprobante_id] += i.monto_aplicado
    for a in aplicaciones:
        credito_aplicado[a.cuota_id] += a.monto_aplicado
        if a.monto_aplicado:
            agregar(
                "APLICACION_CREDITO",
                a.id,
                a.creado_en,
                "Saldo a favor aplicado a cuota",
                a.monto_aplicado,
                cuota=a.cuota_id,
                financiero=False,
            )
    for p in aprobados.values():
        if p.conciliado_en is None:
            inconsistente()
        if p.id not in gestionados:
            credito = p.monto - legacy_por_pago[p.id]
            if credito < CERO:
                inconsistente()
            credito_generado += credito
        elif total_diario_por_pago[p.id] != p.monto:
            inconsistente()
        agregar(
            "PAGO_APROBADO",
            p.id,
            p.conciliado_en,
            "Pago aprobado",
            -p.monto,
            pago=p.id,
            fecha_operacion=p.fecha_operacion,
        )
    abonos_historicos = CERO
    for c in cuotas:
        base = c.monto_total_exigible - mora_neta[c.id]
        anterior = (
            c.monto_pagado - pagos_diarios[c.id] - pagos_legacy[c.id] - credito_aplicado[c.id]
        )
        if base < CERO or anterior < CERO or mora_neta[c.id] < CERO:
            inconsistente()
        abonos_historicos += anterior
        agregar("EMISION_CUOTA", c.id, c.fecha_emision, f"Cuota {c.periodo}", base, cuota=c.id)
    credito_inicial = depto.saldo_a_favor + sum(credito_aplicado.values(), CERO) - credito_generado
    if any(v < CERO for v in componentes_vigentes.values()):
        inconsistente()
    if credito_inicial < CERO:
        inconsistente()
    base_historica = -credito_inicial - abonos_historicos
    movimientos.sort(key=lambda m: (m["registrado_en"], m["tipo"], m["id"]))
    saldo = base_historica
    saldo_inicial, cargos, abonos = base_historica, CERO, CERO
    seleccionados = []
    for m in movimientos:
        delta = Decimal(m["cargo"]) - Decimal(m["abono"])
        saldo += delta
        m["saldo"] = dinero(saldo)
        if m["fecha"] < desde:
            saldo_inicial += delta
        elif m["fecha"] <= hasta:
            cargos += Decimal(m["cargo"])
            abonos += Decimal(m["abono"])
            seleccionados.append(m)
    deuda = sum((c.monto_total_exigible - c.monto_pagado for c in cuotas), CERO)
    if saldo != deuda - depto.saldo_a_favor:
        inconsistente()
    pendientes = [
        {
            "id": p.id,
            "fecha_reporte": instante(p.creado_en).astimezone(LIMA).date(),
            "fecha_operacion": p.fecha_operacion,
            "banco": p.banco_origen,
            "numero_operacion": p.numero_operacion,
            "monto": dinero(p.monto),
        }
        for p in sorted(pagos, key=lambda p: (instante(p.creado_en), str(p.id)))
        if p.estado == "EN_REVISION"
        and desde <= instante(p.creado_en).astimezone(LIMA).date() <= hasta
    ]
    return {
        "departamento_id": depto.id,
        "condominio_id": condominio.id,
        "moneda": condominio.moneda,
        "desde": desde,
        "hasta": hasta,
        "generado_en": datetime.now(UTC),
        "historial_desde": min((m["fecha"] for m in movimientos), default=None),
        "base_historica_sin_fecha": bool(credito_inicial or abonos_historicos),
        "credito_inicial_sin_desglose": dinero(credito_inicial),
        "abonos_historicos_sin_desglose": dinero(abonos_historicos),
        "saldo_base_historico": dinero(base_historica),
        "saldo_inicial": dinero(saldo_inicial),
        "cargos_periodo": dinero(cargos),
        "abonos_periodo": dinero(abonos),
        "saldo_final": dinero(saldo_inicial + cargos - abonos),
        "deuda_actual": dinero(deuda),
        "deuda_vencida_actual": dinero(saldo_en_mora(cuotas, condominio.dias_gracia, hoy)),
        "saldo_a_favor_actual": dinero(depto.saldo_a_favor),
        "saldo_neto_actual": dinero(saldo),
        "total_movimientos": len(seleccionados),
        "limite": limite,
        "offset": offset,
        "movimientos": seleccionados[offset : offset + limite],
        "pagos_en_revision": pendientes,
    }


class EstadoCuentaService:
    def __init__(self, session):
        self.session = session

    async def consultar(self, did, actor, desde=None, hasta=None, limite=50, offset=0):
        hoy = fecha_lima()
        desde, hasta = rango_consulta(desde, hasta, hoy)
        async with self.session.begin():
            await self.session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            repo = SQLAlchemyPagosRepository(self.session)
            depto, condominio = await repo.departamento(did, actor)
            cuotas = await repo.cuotas(did)
            cids = [c.id for c in cuotas]

            async def filas(modelo, filtro):
                return list(await self.session.scalars(select(modelo).where(filtro)))

            pagos = await filas(ComprobantePago, ComprobantePago.departamento_id == did)
            pids = [p.id for p in pagos]
            devengos = await filas(DevengoMora, DevengoMora.cuota_id.in_(cids))
            return proyectar_cuenta(
                depto=depto,
                condominio=condominio,
                cuotas=cuotas,
                pagos=pagos,
                imputaciones=await filas(ImputacionPago, ImputacionPago.comprobante_id.in_(pids)),
                gestionados=set(
                    await self.session.scalars(
                        select(ConciliacionDiaria.comprobante_id).where(
                            ConciliacionDiaria.comprobante_id.in_(pids)
                        )
                    )
                ),
                devengos=devengos,
                ajustes=await filas(
                    AjusteDevengoMora, AjusteDevengoMora.devengo_id.in_([d.id for d in devengos])
                ),
                distribuciones=await filas(
                    MovimientoImputacionDiaria, MovimientoImputacionDiaria.comprobante_id.in_(pids)
                ),
                aplicaciones=await filas(
                    AplicacionSaldoFavor, AplicacionSaldoFavor.cuota_id.in_(cids)
                ),
                desde=desde,
                hasta=hasta,
                hoy=hoy,
                limite=limite,
                offset=offset,
            )


@router.get("/departamentos/{departamento_id}/estado-cuenta", response_model=EstadoCuentaResponse)
async def consultar_estado_cuenta(
    departamento_id: UUID,
    response: Response,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    data = await EstadoCuentaService(session).consultar(
        departamento_id, actor, desde, hasta, limite, offset
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    return data
