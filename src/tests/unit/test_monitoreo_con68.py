"""CON-68: salud por componente, jobs y alertas visibles, sin base de datos."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from src.core import salud_operativa
from src.core.config import settings
from src.core.database import get_db_session
from src.core.security import get_current_user
from src.main import app
from src.modules.notificaciones import monitoreo

CID, OTRO = uuid4(), uuid4()
INICIO = datetime(2026, 11, 24, 3, 0, tzinfo=UTC)


class DBFalsa:
    def __init__(self, filas=(), jobs=()):
        self.filas, self.jobs, self.consultas = list(filas), list(jobs), []

    @asynccontextmanager
    async def begin(self):
        yield

    async def execute(self, consulta):
        self.consultas.append(consulta)
        filas = self.filas
        return SimpleNamespace(
            all=lambda: filas,
            scalars=lambda: SimpleNamespace(all=lambda: self.jobs),
        )


def sql(consulta):
    return str(
        consulta.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


def usuario(rol, cid=CID):
    return {"sub": str(uuid4()), "rol": rol, "condominio_id": str(cid) if cid else None}


@pytest.fixture
def api(monkeypatch):
    estado = SimpleNamespace(user=usuario("SUPERADMIN", None), db=DBFalsa())

    async def sesion():
        yield estado.db

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: estado.user)
    monkeypatch.setitem(app.dependency_overrides, get_db_session, sesion)
    monkeypatch.setattr(settings, "REDIS_REQUIRED", True)
    monkeypatch.setattr(salud_operativa, "comprobar_postgres", AsyncMock())
    monkeypatch.setattr(salud_operativa, "comprobar_redis", AsyncMock(), raising=False)
    monkeypatch.setattr(salud_operativa, "estado_redis", AsyncMock(return_value="ok"))
    with TestClient(app) as client:
        yield client, estado


def componentes(cuerpo):
    return {c["componente"]: c["estado"] for c in cuerpo["componentes"]}


def alerta(origen="CORREO", cid=CID, **extra):
    datos = {
        "id": uuid4(),
        "origen_tipo": origen,
        "origen_id": "diario" if origen == "JOB" else "n-1",
        "referencia_correlacion": None,
        "condominio_id": cid if origen == "CORREO" else None,
        "tipo": "JOB_FALLO_DEFINITIVO" if origen == "JOB" else "INTENTOS_AGOTADOS",
        "mensaje": "Mensaje operativo",
        "creada_en": INICIO,
        "atendida_en": None,
    } | extra
    return (
        SimpleNamespace(**datos),
        None if origen == "JOB" else "402",
        None if origen == "JOB" else "NOTIF_COMUNICADO_GENERAL",
    )


def test_salud_sana_muestra_componentes_y_jobs_sin_registro(api):
    client, _ = api
    r = client.get("/api/v1/monitoreo/salud")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    cuerpo = r.json()
    assert componentes(cuerpo) == {
        "api": "ok",
        "postgresql": "ok",
        "redis": "ok",
        "correo": "deshabilitado",
    }
    assert cuerpo["estado_general"] == "ok" and cuerpo["perfil"] == settings.APP_ENV
    assert {j["nombre"]: j["resultado"] for j in cuerpo["jobs"]} == {
        "notificaciones": "SIN_REGISTRO",
        "diario": "SIN_REGISTRO",
    }


def test_redis_deshabilitado_no_degrada_el_estado(api, monkeypatch):
    monkeypatch.setattr(salud_operativa, "estado_redis", AsyncMock(return_value="disabled"))
    cuerpo = api[0].get("/api/v1/monitoreo/salud").json()
    assert componentes(cuerpo)["redis"] == "deshabilitado" and cuerpo["estado_general"] == "ok"


def test_correo_ok_si_mailjet_esta_habilitado(api, monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    assert componentes(api[0].get("/api/v1/monitoreo/salud").json())["correo"] == "ok"


def test_postgres_caido_responde_200_degradado_sin_secretos(api, monkeypatch):
    monkeypatch.setattr(
        salud_operativa,
        "comprobar_postgres",
        AsyncMock(side_effect=ConnectionError("postgresql://u:secreto@host/db")),
    )
    client, estado = api
    estado.db.begin = lambda: (_ for _ in ()).throw(ConnectionError("postgresql://u:secreto@h/db"))
    r = client.get("/api/v1/monitoreo/salud")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado_general"] == "degradado" and componentes(cuerpo)["postgresql"] == "error"
    assert "secreto" not in r.text and "postgresql://" not in r.text
    assert all(j["resultado"] == "SIN_REGISTRO" for j in cuerpo["jobs"])


def test_ultimo_job_con_duracion_y_en_curso_sin_ella(api):
    client, estado = api
    estado.db.jobs = [
        SimpleNamespace(
            nombre="correo",
            inicio=INICIO,
            fin=INICIO + timedelta(seconds=12.5),
            estado="COMPLETADO",
        ),
        SimpleNamespace(nombre="otro", inicio=INICIO, fin=None, estado="EN_CURSO"),
    ]
    jobs = {j["nombre"]: j for j in client.get("/api/v1/monitoreo/salud").json()["jobs"]}
    assert jobs["notificaciones"]["resultado"] == "COMPLETADO"
    assert jobs["notificaciones"]["duracion_segundos"] == 12.5
    assert jobs["notificaciones"]["fin"] is not None
    assert jobs["otro"] == {**jobs["otro"], "duracion_segundos": None, "resultado": "EN_CURSO"}
    assert jobs["diario"]["resultado"] == "SIN_REGISTRO"


@pytest.mark.parametrize("rol", ["ADMIN_JUNTA", "AUDITOR", "RESIDENTE"])
def test_salud_es_solo_para_superadmin(api, rol):
    client, estado = api
    estado.user = usuario(rol)
    assert client.get("/api/v1/monitoreo/salud").status_code == 403


def test_alertas_traen_componente_operacion_y_referencia(api):
    client, estado = api
    estado.db.filas = [
        alerta(),
        alerta("JOB"),
        alerta(referencia_correlacion="corr-82"),
    ]
    cuerpo = client.get("/api/v1/monitoreo/alertas").json()
    correo, job, con_ref = cuerpo
    assert (correo["componente"], correo["operacion"]) == ("correo", "NOTIF_COMUNICADO_GENERAL")
    assert correo["referencia_diagnostico"] == {
        "origen_tipo": "CORREO",
        "origen_id": "n-1",
        "referencia_correlacion": None,
    }
    assert (job["componente"], job["operacion"], job["condominio_id"]) == ("job", "diario", None)
    assert job["referencia_diagnostico"]["origen_id"] == "diario"
    assert con_ref["referencia_diagnostico"]["referencia_correlacion"] == "corr-82"
    assert {"notificacion_id", "destinatario"}.isdisjoint(correo)


def test_superadmin_ve_todo_y_puede_filtrar_por_condominio(api):
    client, estado = api
    client.get("/api/v1/monitoreo/alertas")
    assert "condominio_id =" not in sql(estado.db.consultas[-1])
    client.get("/api/v1/monitoreo/alertas", params={"condominio_id": str(OTRO)})
    assert f"notificaciones_alertas.condominio_id = '{OTRO}'" in sql(estado.db.consultas[-1])


@pytest.mark.parametrize("rol", ["ADMIN_JUNTA", "AUDITOR"])
def test_junta_y_auditor_se_limitan_a_su_condominio_y_excluyen_jobs(api, rol):
    client, estado = api
    estado.user = usuario(rol)
    assert client.get("/api/v1/monitoreo/alertas").status_code == 200
    consulta = sql(estado.db.consultas[-1])
    assert f"notificaciones_alertas.condominio_id = '{CID}'" in consulta
    assert str(OTRO) not in consulta


@pytest.mark.parametrize("rol", ["ADMIN_JUNTA", "AUDITOR"])
def test_condominio_ajeno_es_403_sin_consultar(api, rol):
    client, estado = api
    estado.user = usuario(rol)
    r = client.get("/api/v1/monitoreo/alertas", params={"condominio_id": str(OTRO)})
    assert r.status_code == 403 and not estado.db.consultas


def test_residente_no_consulta_alertas(api):
    client, estado = api
    estado.user = usuario("RESIDENTE")
    assert client.get("/api/v1/monitoreo/alertas").status_code == 403


def test_estado_paginacion_y_validacion(api):
    client, estado = api
    client.get("/api/v1/monitoreo/alertas", params={"estado": "ATENDIDA", "limit": 10, "offset": 5})
    consulta = sql(estado.db.consultas[-1])
    assert "atendida_en IS NOT NULL" in consulta and "LIMIT 10 OFFSET 5" in consulta
    client.get("/api/v1/monitoreo/alertas")
    assert "atendida_en IS NULL" in sql(estado.db.consultas[-1])
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"estado": "X"}):
        assert client.get("/api/v1/monitoreo/alertas", params=params).status_code == 422


def test_rutas_monitoreo_registradas_y_requieren_sesion():
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        rutas = client.get("/openapi.json").json()["paths"]
        assert {"/api/v1/monitoreo/salud", "/api/v1/monitoreo/alertas"} <= set(rutas)
        assert client.get("/api/v1/monitoreo/salud").status_code in (401, 403)
        assert client.get("/api/v1/monitoreo/alertas").status_code in (401, 403)


def test_modulo_expone_alerta_visible():
    assert monitoreo.alerta_visible
