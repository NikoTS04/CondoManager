from datetime import date
from decimal import Decimal
import uuid

from src.modules.pagos.moras_service import MotorMorasService


def test_aplicacion_mora_tras_gracia_sin_comprobante():
    """Valida la aplicación de mora fija de S/ 20.00 cuando expiró la gracia."""
    depto_id = uuid.uuid4()
    departamentos = {depto_id: {"id": depto_id, "estado_financiero": "AL_DIA"}}

    cuotas = [
        {
            "id": uuid.uuid4(),
            "departamento_id": depto_id,
            "periodo": "2026-09",
            "monto_total_exigible": Decimal("150.00"),
            "monto_pagado": Decimal("0.00"),
            "monto_mora": Decimal("0.00"),
            "fecha_vencimiento": date(2026, 9, 20),
            "estado": "PENDIENTE",
        }
    ]

    # Evaluación el día 23 (2 días de gracia vencieron el día 22)
    response = MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=cuotas,
        departamentos=departamentos,
        comprobantes_en_revision_por_depto={},
        fecha_evaluacion=date(2026, 9, 23),
        dias_gracia=2,
        monto_mora_fijo=Decimal("20.00"),
    )

    assert response.moras_aplicadas == 1
    assert response.cuotas_postergadas_por_revision == 0
    assert response.monto_total_moras == Decimal("20.00")
    assert cuotas[0]["estado"] == "EN_MORA"
    assert cuotas[0]["monto_mora"] == Decimal("20.00")
    assert cuotas[0]["monto_total_exigible"] == Decimal("170.00")
    assert departamentos[depto_id]["estado_financiero"] == "EN_MORA"


def test_postergacion_protectora_mora_con_comprobante_en_revision():
    """Valida que si el departamento tiene un comprobante en revisión, no se le aplique mora aún."""
    depto_id = uuid.uuid4()
    departamentos = {depto_id: {"id": depto_id, "estado_financiero": "OBSERVADO"}}

    cuotas = [
        {
            "id": uuid.uuid4(),
            "departamento_id": depto_id,
            "periodo": "2026-09",
            "monto_total_exigible": Decimal("150.00"),
            "monto_pagado": Decimal("0.00"),
            "monto_mora": Decimal("0.00"),
            "fecha_vencimiento": date(2026, 9, 20),
            "estado": "PENDIENTE",
        }
    ]

    response = MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=cuotas,
        departamentos=departamentos,
        comprobantes_en_revision_por_depto={depto_id: True},  # Tiene voucher en revisión
        fecha_evaluacion=date(2026, 9, 23),
        dias_gracia=2,
    )

    assert response.moras_aplicadas == 0
    assert response.cuotas_postergadas_por_revision == 1
    assert cuotas[0]["estado"] == "PENDIENTE"
    assert cuotas[0]["monto_total_exigible"] == Decimal("150.00")
    assert departamentos[depto_id]["estado_financiero"] == "OBSERVADO"
