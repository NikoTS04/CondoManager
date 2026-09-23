from datetime import date
from decimal import Decimal
import uuid
import pytest

from scripts.seed_condominio_piloto import generar_datos_departamentos
from src.modules.cuotas.schemas import EmitirLoteCuotasRequest
from src.modules.cuotas.service import CuotasService, LoteYaEmitidoException


def test_emision_cuota_departamento_regular():
    """Valida el cálculo de cuota para una unidad regular según PROC-01."""
    resultado = CuotasService.calcular_emision_departamento(
        departamento_id=uuid.uuid4(),
        departamento_numero="101",
        coeficiente=Decimal("0.8500"),
        saldo_a_favor=Decimal("0.00"),
        presupuesto_total=Decimal("20000.00"),
        periodo="2026-10",
        fecha_emision=date(2026, 10, 1),
        fecha_vencimiento=date(2026, 10, 20),
    )

    assert resultado["monto_ordinario"] == Decimal("170.00")
    assert resultado["monto_descuento"] == Decimal("0.00")
    assert resultado["monto_total_exigible"] == Decimal("170.00")
    assert resultado["monto_pagado"] == Decimal("0.00")
    assert resultado["estado"] == "PENDIENTE"
    assert resultado["cubierta_saldo_favor"] is False


def test_amortizacion_cuota_con_saldo_a_favor_total():
    """Valida que si el saldo a favor es mayor o igual a la cuota, pasa a PAGADA."""
    resultado = CuotasService.calcular_emision_departamento(
        departamento_id=uuid.uuid4(),
        departamento_numero="302",
        coeficiente=Decimal("0.7500"),
        saldo_a_favor=Decimal("200.00"),
        presupuesto_total=Decimal("20000.00"),
        periodo="2026-10",
        fecha_emision=date(2026, 10, 1),
        fecha_vencimiento=date(2026, 10, 20),
    )

    # Cuota = 20,000 * 0.75% = S/ 150.00. Saldo previo: 200.00
    assert resultado["monto_ordinario"] == Decimal("150.00")
    assert resultado["monto_descuento"] == Decimal("150.00")
    assert resultado["monto_total_exigible"] == Decimal("0.00")
    assert resultado["monto_pagado"] == Decimal("150.00")
    assert resultado["estado"] == "PAGADA"
    assert resultado["nuevo_saldo_a_favor"] == Decimal("50.00")
    assert resultado["cubierta_saldo_favor"] is True


def test_emision_masiva_139_departamentos_suma_exacta():
    """Valida la emisión masiva para los 139 departamentos de Villa Bonita 3."""
    deptos = generar_datos_departamentos()
    presupuesto = Decimal("20850.00")

    request = EmitirLoteCuotasRequest(
        condominio_id=uuid.uuid4(),
        periodo="2026-10",
        presupuesto_total=presupuesto,
        fecha_vencimiento=date(2026, 10, 20),
    )

    response = CuotasService.emitir_lote_en_memoria(
        request=request,
        departamentos=deptos,
    )

    assert response.total_cuotas_emitidas == 139
    assert response.monto_total_facturado == presupuesto
    assert response.cuotas_cubiertas_saldo_favor >= 1  # Dpto 302 tiene saldo a favor


def test_prevencion_duplicidad_lote():
    """Valida que no se pueda emitir dos veces el mismo periodo."""
    request = EmitirLoteCuotasRequest(
        condominio_id=uuid.uuid4(),
        periodo="2026-10",
        presupuesto_total=Decimal("20000.00"),
        fecha_vencimiento=date(2026, 10, 20),
    )

    with pytest.raises(LoteYaEmitidoException):
        CuotasService.emitir_lote_en_memoria(
            request=request,
            departamentos=[],
            lotes_existentes=["2026-10"],
        )
