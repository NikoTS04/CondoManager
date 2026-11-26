from datetime import UTC, datetime
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory

from src.core.config import settings
from src.core.reintentos_job import puede_reintentar_job
from src.modules.excepciones.jobs import acciones_job
from src.modules.excepciones.service import resumen
from src.modules.notificaciones.models import AlertaNotificacion


def alerta_job(nombre="notificaciones"):
    return AlertaNotificacion(
        id=uuid4(),
        origen_tipo="JOB",
        origen_id=nombre,
        ciclo=20261125,
        tipo="JOB_FALLO_DEFINITIVO",
        mensaje="El proceso programado falló tras 1 intento.",
        creada_en=datetime.now(UTC),
        referencia_correlacion="corr-1",
    )


def test_solo_los_jobs_registrados_como_seguros_admite_reintento(monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    assert puede_reintentar_job("notificaciones")
    assert not puede_reintentar_job("diario")
    assert "REINTENTAR_JOB" in acciones_job(alerta_job("notificaciones"), [])
    assert "REINTENTAR_JOB" not in acciones_job(alerta_job("diario"), [])


def test_el_resumen_de_un_job_expone_componente_y_operacion():
    dto = resumen(alerta_job("diario"), None)
    assert dto.origen == "JOB"
    assert dto.operacion_id == "diario" and dto.estado == "ABIERTA"


def test_migracion_de_reintentos_extiende_la_persistencia_de_con86():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_revision("20261130_0030").down_revision == "20261129_0029"
    assert scripts.get_revision("20261201_0031").down_revision == "20261130_0030"
    assert scripts.get_heads() == ["20261201_0031"]
