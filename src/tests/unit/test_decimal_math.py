from decimal import Decimal
import pytest
from src.shared.decimal_types import (
    calcular_cuota_alicuota,
    calcular_cuota_fija,
    redondear_moneda,
)


def test_redondear_moneda():
    assert redondear_moneda("150.855") == Decimal("150.86")
    assert redondear_moneda("150.854") == Decimal("150.85")
    assert redondear_moneda("150.850") == Decimal("150.85")


def test_calcular_cuota_alicuota():
    # Presupuesto S/ 20,000.00 con alícuota 0.8500% = S/ 170.00
    presupuesto = Decimal("20000.00")
    alicuota = Decimal("0.8500")
    cuota = calcular_cuota_alicuota(presupuesto, alicuota)
    assert cuota == Decimal("170.00")


def test_calcular_cuota_fija():
    # Presupuesto S/ 20,850.00 entre 139 departamentos = S/ 150.00
    presupuesto = Decimal("20850.00")
    cuota = calcular_cuota_fija(presupuesto, 139)
    assert cuota == Decimal("150.00")
