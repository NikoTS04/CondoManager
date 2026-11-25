"""CON-84: alertas de fallos definitivos con origen y correlación, sin base de datos."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql

from src.core import jobs
from src.core.config import settings
from src.main import app
from src.modules.notificaciones import alertas
from src.modules.notificaciones.models import ORIGENES_ALERTA, TIPOS_ALERTA, AlertaNotificacion
from src.modules.notificaciones.persistencia import NotificacionesPersistentesService
from src.modules.notificaciones.schemas import AlertaNotificacionDTO


class DBFalsa:
    """Registra los INSERT y simula la restricción única de la base."""

    def __init__(self):
        self.vistos = set()
        self.sentencias = []

    async def scalar(self, _consulta):
        return "402"

    async def execute(self, sentencia):
        self.sentencias.append(sentencia)
        valores = {columna.name: valor.value for columna, valor in sentencia._values.items()}
        clave = (valores["origen_tipo"], valores["origen_id"], valores["ciclo"], valores["tipo"])
        nueva = clave not in self.vistos
        self.vistos.add(clave)
        self.ultimo = valores
        return SimpleNamespace(scalar_one_or_none=lambda: uuid4() if nueva else None)


AHORA = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)


def test_ciclo_de_job_es_la_fecha_utc_aaaammdd():
    assert alertas.ciclo_job(AHORA) == 20261125


@pytest.mark.asyncio
async def test_job_con_reintentos_pendientes_no_genera_alerta():
    db = DBFalsa()
    assert await alertas.crear_alerta_job(db, "diario", 1, 3, AHORA) is False
    assert db.sentencias == []


@pytest.mark.asyncio
async def test_job_agotado_crea_una_alerta_idempotente_con_origen():
    db = DBFalsa()
    assert await alertas.crear_alerta_job(db, "diario", 3, 3, AHORA, "corr-1") is True
    v = db.ultimo
    assert (v["origen_tipo"], v["origen_id"], v["tipo"]) == (
        "JOB",
        "diario",
        "JOB_FALLO_DEFINITIVO",
    )
    assert v["ciclo"] == 20261125 and v["referencia_correlacion"] == "corr-1"
    assert v["condominio_id"] is None and v["notificacion_id"] is None
    assert "Traceback" not in v["mensaje"] and "diario" in v["mensaje"]
    # El mismo job, ciclo y tipo no vuelve a crearse; otro job o día sí.
    assert await alertas.crear_alerta_job(db, "diario", 3, 3, AHORA) is False
    assert await alertas.crear_alerta_job(db, "notificaciones", 3, 3, AHORA) is True
    otro_dia = datetime(2026, 11, 26, 3, 0, tzinfo=UTC)
    assert await alertas.crear_alerta_job(db, "diario", 3, 3, otro_dia) is True


@pytest.mark.asyncio
async def test_referencia_se_trunca_y_es_opcional():
    db = DBFalsa()
    await alertas.crear_alerta_job(db, "diario", 1, 1, AHORA, "x" * 100)
    assert len(db.ultimo["referencia_correlacion"]) == 64
    await alertas.crear_alerta_job(db, "notificaciones", 1, 1, AHORA)
    assert db.ultimo["referencia_correlacion"] is None


@pytest.mark.asyncio
async def test_alerta_de_correo_referencia_su_origen_y_deduplica_por_ciclo():
    db = DBFalsa()
    log = SimpleNamespace(
        id=uuid4(), condominio_id=uuid4(), departamento_id=uuid4(), canal="EMAIL", ciclo=1
    )
    assert await alertas.crear_alerta(db, log, "INTENTOS_AGOTADOS", AHORA) is True
    assert db.ultimo["origen_tipo"] == "CORREO" and db.ultimo["origen_id"] == str(log.id)
    assert db.ultimo["referencia_correlacion"] is None
    assert await alertas.crear_alerta(db, log, "INTENTOS_AGOTADOS", AHORA) is False
    log.ciclo = 2
    assert await alertas.crear_alerta(db, log, "INTENTOS_AGOTADOS", AHORA) is True


def test_insercion_usa_la_unicidad_por_origen():
    sentencia = (
        postgresql.insert(AlertaNotificacion)
        .values(id=uuid4())
        .on_conflict_do_nothing(constraint="uq_alerta_origen_tipo")
    )
    assert "ON CONFLICT ON CONSTRAINT uq_alerta_origen_tipo" in str(
        sentencia.compile(dialect=postgresql.dialect())
    )
    nombres = {c.name for c in AlertaNotificacion.__table__.constraints}
    assert {"uq_alerta_origen_tipo", "ck_alerta_origen", "ck_alerta_origen_tipo"} <= nombres
    assert "JOB_FALLO_DEFINITIVO" in TIPOS_ALERTA and ORIGENES_ALERTA == ("CORREO", "JOB")


def test_dto_expone_origen_y_correlacion_nula_sin_notificacion():
    alerta = SimpleNamespace(
        id=uuid4(),
        notificacion_id=None,
        origen_tipo="JOB",
        origen_id="diario",
        referencia_correlacion=None,
        condominio_id=None,
        departamento_id=None,
        ciclo=20261125,
        tipo="JOB_FALLO_DEFINITIVO",
        mensaje="m",
        atendida_en=None,
        atendida_por=None,
        creada_en=AHORA,
    )
    dto = NotificacionesPersistentesService.alerta_dto(alerta, None, None)
    assert isinstance(dto, AlertaNotificacionDTO)
    assert dto.origen_tipo == "JOB" and dto.notificacion_id is None and dto.tipo_evento == "diario"
    assert dto.referencia_correlacion is None and dto.condominio_id is None


def test_migracion_0025_es_la_cabeza_sobre_la_0024():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_revision("20261125_0025").down_revision == "20261124_0024"


@pytest.mark.asyncio
async def test_registro_de_fallo_de_job_no_propaga_errores(monkeypatch):
    llamadas = []

    class DB:
        @asynccontextmanager
        async def begin(self):
            yield

    @asynccontextmanager
    async def factory():
        yield DB()

    async def crear(db, nombre, intentos, maximo, *a, **k):
        llamadas.append((nombre, intentos, maximo))

    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    monkeypatch.setattr(alertas, "crear_alerta_job", crear)
    await jobs.registrar_fallo_definitivo_job("diario")
    assert llamadas == [("diario", 1, jobs.MAX_INTENTOS_JOB)]
    monkeypatch.setattr(alertas, "crear_alerta_job", AsyncMock(side_effect=RuntimeError("bd")))
    await jobs.registrar_fallo_definitivo_job("diario")  # no lanza


@pytest.mark.parametrize(
    ("ruta", "nombre", "funcion", "metodo"),
    [
        ("diario", "diario", "ejecutar_diario", "get"),
        ("notificaciones", "notificaciones", "ejecutar_notificaciones", "post"),
    ],
)
def test_cron_con_error_alerta_sin_revelar_la_causa(monkeypatch, ruta, nombre, funcion, metodo):
    registrar = AsyncMock()
    monkeypatch.setattr(jobs, "registrar_fallo_definitivo_job", registrar)
    monkeypatch.setattr(jobs, funcion, AsyncMock(side_effect=RuntimeError("causa interna")))
    monkeypatch.setattr(settings, "CRON_SECRET", SecretStr("cron-prueba"))
    monkeypatch.setenv("VERCEL_ENV", "production")
    with TestClient(app) as client:
        r = getattr(client, metodo)(
            f"/api/v1/jobs/{ruta}", headers={"Authorization": "Bearer cron-prueba"}
        )
    assert r.status_code == 503 and "causa interna" not in r.text
    registrar.assert_awaited_once_with(nombre)


def test_job_en_curso_no_es_un_fallo(monkeypatch):
    from src.core.errors import APIError

    registrar = AsyncMock()
    monkeypatch.setattr(jobs, "registrar_fallo_definitivo_job", registrar)
    monkeypatch.setattr(
        jobs, "ejecutar_diario", AsyncMock(side_effect=APIError(409, "JOB_EN_CURSO", "x"))
    )
    monkeypatch.setattr(settings, "CRON_SECRET", SecretStr("cron-prueba"))
    monkeypatch.setenv("VERCEL_ENV", "production")
    with TestClient(app) as client:
        r = client.get("/api/v1/jobs/diario", headers={"Authorization": "Bearer cron-prueba"})
    assert r.status_code == 409
    registrar.assert_not_awaited()
