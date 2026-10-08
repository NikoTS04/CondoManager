"""Pruebas de ejecución de reintentos programados de PROC-03."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from src.modules.notificaciones.schemas import (
    EstadoNotificacionEnum,
    NotificacionLogDTO,
)
from src.modules.notificaciones.service import NotificacionesService


@pytest.fixture
def log_programado():
    return NotificacionLogDTO(
        condominio_id="vb3-condo",
        departamento_id="601",
        tipo_evento="NOTIF_MORA_APLICADA",
        destinatario="residente601@example.com",
        asunto="Aviso de mora",
        cuerpo="Tiene una cuota pendiente.",
        estado=EstadoNotificacionEnum.REINTENTANDO,
        intentos=2,
        error_mensaje="[503] Service Unavailable",
        proximo_reintento=datetime(2026, 10, 23, 8, 2, tzinfo=UTC),
    )


def test_reintento_vencido_entrega_y_no_vuelve_a_enviar(log_programado):
    ahora = log_programado.proximo_reintento
    transporte = Mock(return_value={"status": 200, "message_id": "msg-reintento"})

    resultado = NotificacionesService.reintentar_notificacion_programada(
        log_programado, transporte, ahora
    )
    NotificacionesService.reintentar_notificacion_programada(
        log_programado, transporte, ahora + timedelta(minutes=1)
    )

    transporte.assert_called_once_with(
        log_programado.destinatario,
        log_programado.canal,
        log_programado.asunto,
        log_programado.cuerpo,
    )
    assert resultado is log_programado
    assert resultado.estado == EstadoNotificacionEnum.ENTREGADO
    assert resultado.intentos == 2
    assert resultado.proveedor_message_id == "msg-reintento"
    assert resultado.error_mensaje is None
    assert resultado.proximo_reintento is None
    assert resultado.fecha_actualizacion == ahora


@pytest.mark.parametrize("caso", ["futuro", "sin_fecha", "entregado", "permanente", "en_cola"])
def test_no_despacha_registros_no_elegibles(log_programado, caso):
    ahora = log_programado.proximo_reintento
    if caso == "futuro":
        ahora -= timedelta(seconds=1)
    elif caso == "sin_fecha":
        log_programado.proximo_reintento = None
    else:
        log_programado.estado = {
            "entregado": EstadoNotificacionEnum.ENTREGADO,
            "permanente": EstadoNotificacionEnum.FALLIDO_PERMANENTE,
            "en_cola": EstadoNotificacionEnum.EN_COLA,
        }[caso]
    original = log_programado.model_copy(deep=True)
    transporte = Mock()

    NotificacionesService.reintentar_notificacion_programada(log_programado, transporte, ahora)

    transporte.assert_not_called()
    assert log_programado == original


@pytest.mark.parametrize("intento,espera", [(2, 10), (3, 30), (4, None)])
def test_fallo_temporal_respeta_limite_y_espera(log_programado, intento, espera):
    ahora = log_programado.proximo_reintento
    log_programado.intentos = intento
    transporte = Mock(return_value={"status": 503, "error": "Service Unavailable"})

    NotificacionesService.reintentar_notificacion_programada(log_programado, transporte, ahora)

    transporte.assert_called_once()
    if espera is None:
        assert log_programado.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE
        assert log_programado.intentos == 4
        assert log_programado.proximo_reintento is None
    else:
        assert log_programado.estado == EstadoNotificacionEnum.REINTENTANDO
        assert log_programado.intentos == intento + 1
        assert log_programado.proximo_reintento == ahora + timedelta(minutes=espera)


def test_error_definitivo_aborta_reintento(log_programado):
    transporte = Mock(return_value={"status": 550, "error": "User unknown"})

    NotificacionesService.reintentar_notificacion_programada(
        log_programado, transporte, log_programado.proximo_reintento
    )

    assert log_programado.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE
    assert log_programado.intentos == 2
    assert log_programado.proximo_reintento is None


def test_excepcion_transporte_programa_siguiente_intento(log_programado):
    ahora = log_programado.proximo_reintento
    transporte = Mock(side_effect=TimeoutError("SMTP timeout"))

    NotificacionesService.reintentar_notificacion_programada(log_programado, transporte, ahora)

    assert log_programado.estado == EstadoNotificacionEnum.REINTENTANDO
    assert log_programado.intentos == 3
    assert log_programado.proximo_reintento == ahora + timedelta(minutes=10)
    assert "SMTP timeout" in log_programado.error_mensaje
