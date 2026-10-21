"""Pruebas unitarias del motor de plantillas de notificaciones (CON-32/34/36).

Verifica:
- Renderizado de todas las plantillas del catálogo con datos completos.
- Prohibición de valores financieros o motivos por defecto (`0.00` inventado).
- Rechazo explícito cuando faltan variables requeridas por plantilla.
- Prohibición de `float` en campos monetarios (regla Zero-Float).
- Normalización de sinónimos de contrato (`monto_aplicado`/`saldo_resultante`, etc.).
"""

from decimal import Decimal

import pytest

from src.modules.notificaciones.templates import (
    PLANTILLAS_CONFIG,
    PlantillaError,
    PlantillaNoEncontradaError,
    PlantillasService,
    PlantillaVariableFaltanteError,
)


def test_renderizado_catalogo_completo_con_variables_requeridas():
    contexto_completo = {
        "nombre": "Carlos Sánchez",
        "dpto": "502 (Torre Norte)",
        "periodo": "2026-10",
        "monto": Decimal("150.00"),
        "monto_pendiente": Decimal("110.00"),
        "vencimiento": "2026-10-20",
        "cci_banco": "002-191-000000000000-54",
        "fecha_corte": "2026-10-20",
        "banco": "BCP",
        "numero_operacion": "992812",
        "monto_abonado": Decimal("150.00"),
        "saldo_restante": Decimal("0.00"),
        "recibo_url": "https://app.condomanager.pe/recibos/rec-01.pdf",
        "motivo": "Imagen borrosa en fecha de operación",
        "instrucciones": "Adjunte una fotografía nítida donde se aprecie el número de operación.",
        "motivo_rechazo": "Operación inexistente en estado de cuenta bancario",
        "enlace_subir_nuevo": "https://app.condomanager.pe/pagos/reportar",
        "monto_mora": Decimal("20.00"),
        "nuevo_saldo": Decimal("170.00"),
        "aviso_bloqueo_reservas": "Inhabilitado para reservar",
        "area": "Zona de Parrilla 1",
        "fecha": "2026-10-25",
        "horario": "19:00 - 22:00",
        "costo": Decimal("45.00"),
        "normas_convivencia": "Aforo máximo 12 personas y limpieza obligatoria",
        "ajuste_economico": "Reembolso aplicable: S/ 45.00",
        "titulo": "Corte de Agua Programado",
        "mensaje": "Se suspenderá el servicio de agua de 09:00 a 13:00 por mantenimiento.",
        "remitente": "Junta Directiva Villa Bonita 3",
    }

    assert "NOTIF_PAGO_OBSERVADO" in PLANTILLAS_CONFIG
    for nombre_plantilla in PLANTILLAS_CONFIG:
        asunto, cuerpo = PlantillasService.renderizar(nombre_plantilla, contexto_completo)
        assert asunto and "{" not in asunto
        assert cuerpo and "{" not in cuerpo


@pytest.mark.parametrize(
    ("plantilla", "contexto_incompleto", "variable_esperada"),
    [
        (
            "NOTIF_EMISION_CUOTA",
            {"dpto": "101", "periodo": "2026-10", "vencimiento": "2026-10-20"},
            "monto",
        ),
        (
            "NOTIF_EMISION_CUOTA",
            {"dpto": "101", "monto": "120.00", "vencimiento": "2026-10-20"},
            "periodo",
        ),
        (
            "NOTIF_PAGO_RECIBIDO",
            {"dpto": "101", "banco": "BCP", "numero_operacion": "123456"},
            "monto",
        ),
        (
            "NOTIF_PAGO_RECIBIDO",
            {"dpto": "101", "monto": "120.00", "numero_operacion": "123456"},
            "banco",
        ),
        (
            "NOTIF_PAGO_CONCILIADO",
            {"dpto": "101", "monto_aplicado": "120.00"},
            "saldo_restante",
        ),
        (
            "NOTIF_PAGO_CONCILIADO",
            {"dpto": "101", "saldo_resultante": "0.00"},
            "monto_abonado",
        ),
        (
            "NOTIF_PAGO_OBSERVADO",
            {"dpto": "101", "motivo": "Voucher incompleto"},
            "instrucciones",
        ),
        (
            "NOTIF_PAGO_OBSERVADO",
            {"dpto": "101", "instrucciones": "Subir voucher completo"},
            "motivo",
        ),
        (
            "NOTIF_PAGO_RECHAZADO",
            {"dpto": "101"},
            "motivo_rechazo",
        ),
        (
            "NOTIF_RESERVA_CONFIRMADA",
            {
                "dpto": "101",
                "area": "Parrilla",
                "fecha": "2026-10-28",
                "horario": "18:00 - 21:00",
                "normas_convivencia": "Sin ruidos molestos",
            },
            "costo",
        ),
        (
            "NOTIF_RESERVA_CANCELADA",
            {
                "dpto": "101",
                "area": "Parrilla",
                "fecha": "2026-10-28",
                "horario": "18:00 - 21:00",
            },
            "motivo",
        ),
    ],
)
def test_plantilla_falla_si_falta_variable_requerida(
    plantilla, contexto_incompleto, variable_esperada
):
    with pytest.raises(PlantillaVariableFaltanteError) as exc_info:
        PlantillasService.renderizar(plantilla, contexto_incompleto)
    assert variable_esperada in str(exc_info.value)


def test_pago_conciliado_nunca_inventa_saldo_por_defecto():
    with pytest.raises(PlantillaVariableFaltanteError):
        PlantillasService.renderizar(
            "NOTIF_PAGO_CONCILIADO",
            {"nombre": "Ana", "dpto": "302", "monto_aplicado": Decimal("180.00"), "saldo_resultante": None},
        )


def test_pago_conciliado_acepta_sinonimos_de_contrato():
    asunto, cuerpo = PlantillasService.renderizar(
        "NOTIF_PAGO_CONCILIADO",
        {
            "nombre": "Ana Torres",
            "dpto": "302 (Torre A)",
            "monto_aplicado": Decimal("180.50"),
            "saldo_resultante": Decimal("45.25"),
        },
    )
    assert "Su pago ha sido validado con éxito" in asunto
    assert "S/ 180.50" in cuerpo
    assert "S/ 45.25" in cuerpo


def test_reserva_cancelada_formatea_reembolso_decimal():
    _, cuerpo = PlantillasService.renderizar(
        "NOTIF_RESERVA_CANCELADA",
        {
            "nombre": "Luis Vega",
            "dpto": "401",
            "area": "SUM",
            "fecha_reserva": "2026-11-02",
            "horario": "14:00 - 18:00",
            "motivo": "Solicitud voluntaria con más de 24h",
            "monto_reembolso": Decimal("60.00"),
        },
    )
    assert "S/ 60.00" in cuerpo
    assert "liberado" in cuerpo


def test_rechaza_float_en_campos_monetarios():
    with pytest.raises(PlantillaError, match="no permite float"):
        PlantillasService.renderizar(
            "NOTIF_EMISION_CUOTA",
            {
                "dpto": "101",
                "periodo": "2026-10",
                "monto": 150.00,
                "vencimiento": "2026-10-20",
            },
        )


def test_plantilla_inexistente_lanza_error():
    with pytest.raises(PlantillaNoEncontradaError):
        PlantillasService.renderizar("PLANTILLA_DESCONOCIDA", {"dpto": "101"})
