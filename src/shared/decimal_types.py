"""Utilidades de precisión decimal estricta para cálculos contables.
Prohíbe el uso de floats para evitar pérdidas de centavos por redondeo.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")


def redondear_moneda(valor: Decimal | str | int) -> Decimal:
    """Redondea de forma estándar contable (ROUND_HALF_UP) a 2 decimales."""
    if isinstance(valor, (float, bool)):
        raise TypeError("El importe debe ser Decimal, cadena o entero; nunca float ni bool.")
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_cuota_alicuota(presupuesto_total: Decimal, coeficiente_porcentaje: Decimal) -> Decimal:
    """Calcula la cuota a partir de la alícuota porcentual: Cuota = Presupuesto * (Coef / 100)."""
    exigir_decimal_finito(presupuesto_total)
    exigir_decimal_finito(coeficiente_porcentaje)
    cuota_bruta = presupuesto_total * (coeficiente_porcentaje / Decimal("100.0000"))
    return redondear_moneda(cuota_bruta)


def calcular_cuota_fija(presupuesto_total: Decimal, total_unidades: int) -> Decimal:
    """Calcula cuota uniforme equitativa dividiendo presupuesto entre número de departamentos."""
    exigir_decimal_finito(presupuesto_total)
    if not isinstance(total_unidades, int) or isinstance(total_unidades, bool):
        raise TypeError("El total de unidades debe ser entero.")
    if total_unidades <= 0:
        raise ValueError("El total de unidades activas debe ser mayor a cero.")
    return redondear_moneda(presupuesto_total / Decimal(total_unidades))


def exigir_decimal_finito(valor: Decimal) -> None:
    """Impide conversiones implícitas desde float y valores contables no finitos."""
    if not isinstance(valor, Decimal):
        raise TypeError("El valor debe ser Decimal; no se permiten conversiones desde float.")
    if not valor.is_finite():
        raise ValueError("El valor decimal debe ser finito.")
