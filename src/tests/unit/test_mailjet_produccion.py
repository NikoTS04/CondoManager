from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.core import jobs
from src.core.config import settings
from src.main import app
from src.modules.notificaciones import eventos_mailjet


@pytest.mark.asyncio
async def test_job_deshabilitado_no_usa_base(monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    def no_conectar():
        raise AssertionError("No debe abrir SQL")
    monkeypatch.setattr(jobs, "AsyncSessionLocal", no_conectar)
    assert await jobs.ejecutar_notificaciones() == {"estado": "DESHABILITADO", "procesadas": 0}


@pytest.mark.asyncio
async def test_job_lote_acotado_y_exclusion(monkeypatch):
    from src.core.errors import APIError
    from src.modules.notificaciones import recordatorios, worker

    class DB:
        permitido = True
        @asynccontextmanager
        async def begin(self):
            yield
        async def scalar(self, query):
            return self.permitido

    @asynccontextmanager
    async def factory():
        yield DB()

    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    for modulo, nombre in (
        (worker, "recuperar_inciertos"), (jobs, "recuperar_eventos"),
        (recordatorios, "generar_recordatorios"),
    ):
        monkeypatch.setattr(modulo, nombre, AsyncMock())
    enviar = AsyncMock(return_value=True)
    monkeypatch.setattr(worker, "procesar_uno", enviar)
    assert (await jobs.ejecutar_notificaciones())["procesadas"] == 20
    assert enviar.await_count == 20
    enviar.assert_awaited_with(solo_proveedor=True)
    DB.permitido = False
    with pytest.raises(APIError) as error:
        await jobs.ejecutar_notificaciones()
    assert error.value.status_code == 409 and enviar.await_count == 20


def test_job_autenticado_y_preview(monkeypatch):
    ejecutar = AsyncMock(return_value={"estado": "COMPLETADO", "procesadas": 2})
    monkeypatch.setattr(jobs, "ejecutar_notificaciones", ejecutar)
    monkeypatch.setattr(settings, "CRON_SECRET", SecretStr("test-cron"))
    with TestClient(app) as client:
        assert client.post("/api/v1/jobs/notificaciones").status_code == 401
        headers = {"Authorization": "Bearer test-cron"}
        monkeypatch.setenv("VERCEL_ENV", "preview")
        assert client.post("/api/v1/jobs/notificaciones", headers=headers).status_code == 403
        ejecutar.assert_not_awaited()
        monkeypatch.setenv("VERCEL_ENV", "production")
        r = client.post("/api/v1/jobs/notificaciones", headers=headers)
        assert r.json()["procesadas"] == 2 and r.headers["cache-control"] == "no-store"
        ejecutar.side_effect = RuntimeError("secreto-no-divulgar")
        r = client.post("/api/v1/jobs/notificaciones", headers=headers)
        assert r.status_code == 503 and "secreto-no-divulgar" not in r.text


def test_callback_autenticacion_limites_y_validacion(monkeypatch):
    aplicar = AsyncMock()
    monkeypatch.setattr(eventos_mailjet, "aplicar_evento", aplicar)
    monkeypatch.setattr(settings, "MAILJET_WEBHOOK_SECRET", SecretStr("x" * 32))
    ruta = "/api/v1/notificaciones/mailjet/eventos"
    auth = ("mailjet", "x" * 32)
    with TestClient(app) as client:
        assert client.post(ruta, json={}).status_code == 401
        assert client.post(ruta, auth=("mailjet", "incorrecta"), json={}).status_code == 401
        assert client.post(ruta, auth=auth, content=b"x" * 65537).status_code == 413
        assert client.post(ruta, auth=auth, json={}).status_code == 422
        assert client.post(ruta, auth=auth, json=[{}] * 101).status_code == 422
        aplicar.assert_not_awaited()
        evento = {"event": "sent", "MessageID": 123, "CustomID": "test", "email": "test@test.test"}
        assert client.post(ruta, auth=auth, json=[evento, evento]).status_code == 200
        assert aplicar.await_count == 2
