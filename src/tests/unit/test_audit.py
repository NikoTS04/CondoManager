from src.core.audit import AuditoriaPayload


def test_auditoria_7_campos_y_hash():
    payload = AuditoriaPayload(
        condominio_id="vb3-condo",
        departamento_id="dpto-501",
        accion_ejecutada="APLICAR_MORA",
        motivo="Vencimiento tras 2 días de gracia",
        resultado="EXITOSO",
        estado_anterior={"saldo": 150.00, "estado": "VENCIDO"},
        estado_posterior={"saldo": 170.00, "estado": "EN_MORA"},
    )

    hash_generado = payload.calcular_hash()
    assert len(hash_generado) == 64
    assert hash_generado != ""
