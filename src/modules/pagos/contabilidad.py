"""Cálculos puros de CON-70/42: importes exactos, sin permisos cacheados."""

from datetime import date, timedelta
from decimal import Decimal

from src.core.errors import APIError
from src.modules.cuotas.models import CuotaMantenimiento
from src.shared.decimal_types import redondear_moneda

CERO = Decimal("0.00")
MAX_MONEDA = Decimal("9999999999.99")


def validar_conservacion_pago(monto: Decimal, aplicado: Decimal, credito: Decimal) -> None:
    """Rechazar un plan inconsistente antes del commit, sin inventar ajustes."""
    if (
        any(not v.is_finite() or v < CERO for v in (monto, aplicado, credito))
        or monto <= CERO
        or aplicado + credito != monto
    ):
        raise APIError(
            409,
            "IMPUTACION_PAGO_INCONSISTENTE",
            "Las aplicaciones y el crédito no explican el importe del comprobante.",
        )


def saldo_en_mora(cuotas: list[CuotaMantenimiento], dias_gracia: int, hoy: date) -> Decimal:
    return redondear_moneda(
        sum(
            (
                max(c.monto_total_exigible - c.monto_pagado, CERO)
                for c in cuotas
                if c.estado == "EN_MORA"
                or hoy
                > c.fecha_vencimiento
                + timedelta(
                    days=c.dias_gracia_aplicados
                    if c.dias_gracia_aplicados is not None
                    else dias_gracia
                )
            ),
            CERO,
        )
    )


def plan_imputacion(
    cuotas: list[CuotaMantenimiento],
    monto: Decimal,
    hoy: date,
    pagados_por_componente: dict | None = None,
) -> dict:
    """Agrupa la prelación por componente y consolida la imputación por cuota.

    monto_pagado ya amortizado (incluido CON-13) se descuenta primero de mora,
    extraordinaria y ordinaria. El total SQL es la obligación autorizada.
    """
    componentes = []
    for c in cuotas:
        # También para nuevas aprobaciones legacy. Los recibos ya aprobados no se recalculan.
        if c.fecha_emision > hoy:
            continue
        mora = min(c.monto_mora, c.monto_total_exigible)
        extraordinaria = min(c.monto_extraordinario, c.monto_total_exigible - mora)
        ordinaria = c.monto_total_exigible - mora - extraordinaria
        pagado = c.monto_pagado
        for tipo, bruto in enumerate((mora, extraordinaria, ordinaria)):
            if pagados_por_componente is None:
                cubierto = min(pagado, bruto)
                pagado -= cubierto
            else:
                cubierto = pagados_por_componente[c.id][tipo]
            pendiente = bruto - cubierto
            vencida = c.fecha_vencimiento < hoy
            vigente = c.periodo <= hoy.strftime("%Y-%m")
            if pendiente <= CERO or (tipo == 1 and not vencida):
                continue
            if tipo == 2 and not (vencida or vigente):
                continue
            prioridad = tipo if tipo != 2 or vencida else 3
            componentes.append((prioridad, c.fecha_vencimiento, c.id.int, tipo, c.id, pendiente))
    disponible = redondear_moneda(monto)
    aplicaciones = {}
    detalle = {}
    for _, _, _, tipo, cuota_id, pendiente in sorted(componentes):
        aplicado = min(disponible, pendiente)
        if aplicado > CERO:
            aplicaciones[cuota_id] = aplicaciones.get(cuota_id, CERO) + aplicado
            detalle.setdefault(cuota_id, [CERO, CERO, CERO])[tipo] += aplicado
            disponible -= aplicado
    return {"aplicaciones": aplicaciones, "remanente": disponible, "componentes": detalle}
