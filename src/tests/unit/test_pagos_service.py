from datetime import date
from decimal import Decimal
import uuid
import pytest

from src.modules.pagos.schemas import ReportarPagoRequest
from src.modules.pagos.service import PagosService, VoucherDuplicadoException


def test_hash_idempotencia_determinista():
    """Valida que el cálculo de hash sea consistente e insensible a mayúsculas/espacios."""
    h1 = PagosService.calcular_hash_idempotencia(
        condominio_id="vb3",
        banco="yape",
        numero_operacion="0089214",
        fecha_operacion=date(2026, 10, 15),
        monto=Decimal("150.00"),
    )
    h2 = PagosService.calcular_hash_idempotencia(
        condominio_id="vb3",
        banco="YAPE",
        numero_operacion="89214",
        fecha_operacion=date(2026, 10, 15),
        monto=Decimal("150.00"),
    )
    assert h1 == h2
    assert len(h1) == 64


def test_prevencion_voucher_duplicado_conciliado():
    """Valida que un voucher ya conciliado retorne error 409 VoucherDuplicadoException."""
    comprobantes = {}
    request = ReportarPagoRequest(
        departamento_id=uuid.uuid4(),
        banco="BCP",
        numero_operacion="123456",
        fecha_operacion=date(2026, 10, 10),
        monto=Decimal("180.00"),
        url_voucher="https://s3/v1.jpg",
    )

    # 1. Primer registro
    res1 = PagosService.procesar_reporte_pago(request, "vb3", comprobantes)
    assert res1.estado == "EN_REVISION"

    # Simulamos que la junta lo aprobó
    comprobantes[res1.idempotency_hash]["estado"] = "APROBADO"

    # 2. Segundo intento de subir el mismo voucher ya aprobado
    with pytest.raises(VoucherDuplicadoException) as exc_info:
        PagosService.procesar_reporte_pago(request, "vb3", comprobantes)

    assert exc_info.value.error_code == "VOUCHER_YA_CONCILIADO"


def test_conciliacion_con_imputacion_en_prelacion_y_excedente():
    """Valida la imputación contable: cancela cuota antigua y el excedente va a saldo a favor."""
    depto_id = uuid.uuid4()
    departamento = {"id": depto_id, "saldo_a_favor": Decimal("0.00"), "estado_financiero": "EN_MORA"}

    cuota_vencida = {
        "id": uuid.uuid4(),
        "fecha_vencimiento": date(2026, 9, 20),
        "monto_total_exigible": Decimal("120.00"),
        "monto_pagado": Decimal("0.00"),
        "estado": "EN_MORA",
    }

    comprobante = {
        "id": uuid.uuid4(),
        "departamento_id": depto_id,
        "banco_origen": "BCP",
        "monto": Decimal("150.00"),  # Paga S/ 150 para una deuda de S/ 120
    }

    resultado = PagosService.conciliar_comprobante(
        comprobante=comprobante,
        decision="APROBADO",
        cuotas_pendientes=[cuota_vencida],
        departamento=departamento,
    )

    assert resultado.estado_final == "APROBADO"
    assert resultado.monto_imputado == Decimal("120.00")
    assert resultado.nuevo_saldo_departamento == Decimal("0.00")
    assert resultado.saldo_a_favor_generado == Decimal("30.00")
    assert departamento["saldo_a_favor"] == Decimal("30.00")
    assert departamento["estado_financiero"] == "AL_DIA"
    assert resultado.departamento_habilitado_reservas is True
    assert cuota_vencida["estado"] == "PAGADA"
