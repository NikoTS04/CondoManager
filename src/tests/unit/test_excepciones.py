from datetime import UTC, datetime

from src.core.config import settings
from src.modules.excepciones.jobs import acciones_job, estado_job
from src.modules.excepciones.models import ResolucionJob
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


def test_solo_notificaciones_habilitadas_admite_reintento(monkeypatch):
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    alerta = AlertaNotificacion(origen_id="notificaciones")
    assert "REINTENTAR_JOB" not in acciones_job(alerta, [])
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    assert "REINTENTAR_JOB" in acciones_job(alerta, [])
    alerta.origen_id = "diario"
    assert "REINTENTAR_JOB" not in acciones_job(alerta, [])


def test_intento_incierto_conserva_revision_humana(monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    alerta = AlertaNotificacion(origen_id="notificaciones")
    intento = ResolucionJob(accion="REINTENTAR_JOB", resultado="EN_CURSO")
    assert acciones_job(alerta, [intento]) == []
    intento.resultado = "INCIERTO"
    assert estado_job(alerta, intento) == "FALLIDA"
    assert acciones_job(alerta, [intento]) == ["CERRAR_CON_MOTIVO", "SOLICITAR_INFORMACION"]
