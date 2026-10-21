"""Pruebas Unitarias del Motor de Entrega y Transportes de Notificaciones (CON-37).

Valida sobre el código real (`transportes.py`, `entrega.py`, `templates.py`):
1. Renderizado dinámico de plantillas.
2. Clasificación entre errores temporales (429, 500, 502, 503, 504, timeout/conexión)
   y definitivos (550, 131026, destinatario inválido, 4xx != 429).
3. Cálculo de backoff exponencial (+2m con jitter ±15s, +10m, +30m).
4. Adaptadores `TransporteSimulado` (`es_simulado=True`) y `TransporteSMTP` (`es_simulado=False`).
5. Sanitización de detalles de error y validación sintáctica de destinatarios.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.modules.notificaciones.entrega import calcular_proximo_intento, sanitizar_detalle_error
from src.modules.notificaciones.templates import PLANTILLAS_CONFIG, PlantillasService
from src.modules.notificaciones.transportes import (
    ResultadoTransporte,
    TransporteSimulado,
    TransporteSMTP,
    clasificar_fallo,
    es_error_definitivo,
    es_error_temporal,
    validar_destinatario,
)


def _contexto_completo(dpto: str = "502", nombre: str = "Carlos Sánchez") -> dict:
    return {
        "nombre": nombre,
        "dpto": dpto,
        "edificio": "Torre A",
        "periodo": "2026-10",
        "monto": str(Decimal("150.00")),
        "monto_total_exigible": str(Decimal("150.00")),
        "monto_pendiente": str(Decimal("150.00")),
        "vencimiento": "2026-10-20",
        "cci_banco": "002-191-000000000000-54",
        "medios_pago": "BCP CCI 002-191-000000000000-54",
        "fecha_corte": "2026-10-20",
        "banco": "BCP",
        "numero_operacion": "992812",
        "monto_abonado": str(Decimal("150.00")),
        "monto_aplicado": str(Decimal("150.00")),
        "saldo_restante": str(Decimal("0.00")),
        "saldo_resultante": str(Decimal("0.00")),
        "recibo_url": "https://app.condomanager.pe/recibos/rec-01.pdf",
        "motivo_rechazo": "Comprobante no visible",
        "motivo": "Comprobante no visible",
        "instrucciones": "Adjunte una imagen legible del voucher.",
        "enlace_subir_nuevo": "https://app.condomanager.pe/pagos/reportar",
        "monto_mora": str(Decimal("20.00")),
        "nuevo_saldo": str(Decimal("170.00")),
        "aviso_bloqueo_reservas": "Inhabilitado para reservar",
        "area": "Zona de Parrilla 1",
        "fecha": "2026-10-25",
        "horario": "19:00 - 22:00",
        "costo": str(Decimal("50.00")),
        "ajuste_economico": str(Decimal("0.00")),
        "normas_convivencia": "Limpieza requerida",
        "titulo": "Corte de Agua Programado",
        "mensaje": "Se suspenderá el servicio de agua de 09:00 a 13:00 por mantenimiento.",
        "remitente": "Junta Directiva Villa Bonita 3",
    }


def test_renderizado_todas_las_plantillas():
    """Valida que todas las plantillas del catálogo se rendericen sin placeholders pendientes."""
    contexto_prueba = _contexto_completo()

    for tipo_evento in PLANTILLAS_CONFIG:
        asunto, cuerpo = PlantillasService.renderizar(tipo_evento, contexto_prueba)
        assert asunto is not None and len(asunto) > 0
        assert cuerpo is not None and len(cuerpo) > 0
        assert "{" not in asunto
        assert "{" not in cuerpo


@pytest.mark.parametrize(
    "codigo,detalle",
    [
        ("429", "Too Many Requests"),
        ("500", "Internal Server Error"),
        ("502", "Bad Gateway"),
        ("503", "Service Unavailable"),
        ("504", "Gateway Timeout"),
        ("TIMEOUT", "Connection timed out"),
        ("CONNECTION_ERROR", "Connection reset by peer"),
    ],
)
def test_clasificacion_errores_temporales(codigo: str, detalle: str):
    """Verifica que 429, 500, 502, 503, 504 y timeout/conexión sean FALLO_TEMPORAL."""
    assert clasificar_fallo(codigo, detalle) == "FALLO_TEMPORAL"
    assert es_error_temporal(codigo, detalle) is True
    assert es_error_definitivo(codigo, detalle) is False


@pytest.mark.parametrize(
    "codigo,detalle",
    [
        ("550", "550 User unknown"),
        ("131026", "Message undeliverable"),
        ("DESTINATARIO_INVALIDO", "Correo mal formado"),
        ("400", "Bad Request"),
        ("401", "Unauthorized"),
        ("403", "Forbidden"),
        ("404", "Not Found"),
        ("422", "Unprocessable Entity"),
    ],
)
def test_clasificacion_errores_definitivos(codigo: str, detalle: str):
    """Verifica que 550, 131026, destinatario inválido y 4xx != 429 sean FALLO_DEFINITIVO."""
    assert clasificar_fallo(codigo, detalle) == "FALLO_DEFINITIVO"
    assert es_error_definitivo(codigo, detalle) is True
    assert es_error_temporal(codigo, detalle) is False


def test_calculo_backoff_y_jitter_primer_reintento():
    """Verifica esperas de 2m (±15s jitter), 10m y 30m según delivery-policy.md."""
    base = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

    # Primer reintento (tras intento 1 fallido): +120s + jitter inyectado (+12s)
    prox_1 = calcular_proximo_intento(1, base, jitter_fn=lambda: 12.0)
    assert prox_1 == base + timedelta(seconds=132)

    # Jitter acotado a ±15s aunque la función devuelva un valor mayor
    prox_acotado = calcular_proximo_intento(1, base, jitter_fn=lambda: -40.0)
    assert prox_acotado == base + timedelta(seconds=105)

    # Segundo reintento (tras intento 2 fallido): +10 minutos exactos
    prox_2 = calcular_proximo_intento(2, base, jitter_fn=lambda: 10.0)
    assert prox_2 == base + timedelta(minutes=10)

    # Tercer reintento (tras intento 3 fallido): +30 minutos exactos
    prox_3 = calcular_proximo_intento(3, base, jitter_fn=lambda: 10.0)
    assert prox_3 == base + timedelta(minutes=30)

    # Tras el 4to intento no hay más reintentos
    assert calcular_proximo_intento(4, base) is None


@pytest.mark.asyncio
async def test_transporte_simulado_configurable_y_validacion():
    """Verifica que TransporteSimulado se identifique como simulado y respete su configuración."""
    transporte = TransporteSimulado(
        por_destinatario={
            "rebote@condo.pe": ResultadoTransporte.fallo("550", "Mailbox not found"),
        }
    )
    assert transporte.es_simulado is True
    assert transporte.nombre == "SIMULADO"

    notif_ok = SimpleNamespace(
        id=uuid.uuid4(),
        destinatario="vecino@condo.pe",
        canal="EMAIL",
        asunto="Prueba",
        cuerpo="Contenido",
    )
    res_ok = await transporte.enviar(notif_ok)
    assert res_ok.aceptado is True
    assert res_ok.proveedor_message_id is not None

    notif_rebote = SimpleNamespace(
        id=uuid.uuid4(),
        destinatario="rebote@condo.pe",
        canal="EMAIL",
        asunto="Prueba",
        cuerpo="Contenido",
    )
    res_rebote = await transporte.enviar(notif_rebote)
    assert res_rebote.aceptado is False
    assert res_rebote.codigo == "550"
    assert res_rebote.es_definitivo is True

    notif_invalida = SimpleNamespace(
        id=uuid.uuid4(),
        destinatario="correo-sin-arroba",
        canal="EMAIL",
        asunto="Prueba",
        cuerpo="Contenido",
    )
    res_inv = await transporte.enviar(notif_invalida)
    assert res_inv.aceptado is False
    assert res_inv.codigo == "DESTINATARIO_INVALIDO"
    assert res_inv.es_definitivo is True
    assert transporte.total_llamadas == 3


@pytest.mark.asyncio
async def test_transporte_smtp_en_hilo():
    """Verifica que TransporteSMTP se identifique como no simulado y use smtplib."""
    smtp_transporte = TransporteSMTP(host="smtp.local", port=1025)
    assert smtp_transporte.es_simulado is False
    assert smtp_transporte.nombre == "SMTP"

    notif = SimpleNamespace(
        id=uuid.uuid4(),
        destinatario="residente@condo.pe",
        canal="EMAIL",
        asunto="Aviso",
        cuerpo="Detalle",
    )
    with patch("src.modules.notificaciones.transportes.smtplib.SMTP") as mock_smtp:
        servidor = MagicMock()
        mock_smtp.return_value.__enter__.return_value = servidor
        res = await smtp_transporte.enviar(notif)
        assert res.aceptado is True
        assert res.proveedor_message_id is not None
        servidor.send_message.assert_called_once()


def test_sanitizar_detalle_error_oculta_secretos():
    texto = "Error autenticando SMTP password=mi_clave_secreta token:abc123xyz"
    limpio = sanitizar_detalle_error(texto)
    assert "mi_clave_secreta" not in limpio
    assert "abc123xyz" not in limpio
    assert "[REDACTED]" in limpio


def test_validar_destinatario():
    assert validar_destinatario("vecino@condominio.pe", "EMAIL") is True
    assert validar_destinatario("invalido@", "EMAIL") is False
    assert validar_destinatario("sin-arroba.pe", "EMAIL") is False
    assert validar_destinatario("+51999888777", "WHATSAPP") is True
