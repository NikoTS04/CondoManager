from datetime import UTC, datetime

from src.modules.excepciones.service import acciones_permitidas, estado_excepcion
from src.modules.notificaciones.models import AlertaNotificacion, Notificacion


def test_aceptacion_incierta_no_habilita_acciones_de_fallo_definitivo():
    alerta = AlertaNotificacion(ciclo=1, tipo="ACEPTACION_INCIERTA")
    aviso = Notificacion(ciclo=1, estado="FALLIDO_PERMANENTE")
    assert acciones_permitidas(alerta, aviso) == []


def test_reenvio_en_cola_sigue_en_proceso_hasta_un_resultado():
    alerta = AlertaNotificacion(ciclo=1, atendida_en=datetime.now(UTC))
    aviso = Notificacion(ciclo=2, estado="EN_COLA")
    assert estado_excepcion(alerta, aviso) == "EN_PROCESO"
    aviso.estado = "FALLIDO_PERMANENTE"
    assert estado_excepcion(alerta, aviso) == "FALLIDA"
    aviso.estado = "ENVIADO"
    assert estado_excepcion(alerta, aviso) == "RESUELTA"
