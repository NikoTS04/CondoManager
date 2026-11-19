import io
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from src.core import jobs
from src.core.config import Settings, settings
from src.core.errors import APIError
from src.main import app
from src.modules.pagos import storage


def produccion():
    return Settings(_env_file=None, APP_ENV="production", DEBUG=False, DEMO_MODE=False,
        JWT_SECRET="x" * 40, CORS_ORIGINS=["https://portal.vercel.app"],
        ACTIVACION_WEB_URL="https://portal.vercel.app/activar", CRON_SECRET="c" * 40,
        VOUCHER_STORAGE="supabase", VOUCHER_MAX_BYTES=3145728,
        SUPABASE_URL="https://proyecto.supabase.co", SUPABASE_SERVICE_ROLE_KEY="privada",
        DATABASE_URL="postgresql+asyncpg://user:pass@db.prueba.supabase.co/postgres?ssl=require",
    )


def test_perfil_valido():
    assert produccion().VOUCHER_MAX_BYTES == 3145728


@pytest.mark.parametrize("campo,valor", [
    ("DEBUG", True), ("DEMO_MODE", True), ("JWT_SECRET", "corto"),
    ("CORS_ORIGINS", ["*"]), ("ACTIVACION_WEB_URL", "http://local"),
    ("VOUCHER_STORAGE", "local"), ("VOUCHER_MAX_BYTES", 5242880),
    ("DATABASE_URL", "postgresql+asyncpg://local/db"),
])
def test_produccion_falla_cerrada(campo, valor):
    valores = produccion().model_dump()
    valores[campo] = valor
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **valores)


@pytest.fixture
def remoto(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://prueba.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "vouchers")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", SecretStr("secreto"))
    return storage.SupabaseVoucherStorage()


def test_storage_privado_y_nombre_validado(monkeypatch, remoto):
    peticiones = []
    class Transporte:
        def open(self, request, **kwargs):
            peticiones.append(request)
            return io.BytesIO(b"evidencia")
    monkeypatch.setattr(storage, "build_opener", lambda *a: Transporte())
    nombre = f"{uuid4()}.png"
    assert remoto.ruta(nombre) == b"evidencia"
    assert peticiones[0].get_header("Authorization") == "Bearer secreto"
    assert "secreto" not in peticiones[0].full_url
    remoto.eliminar(nombre)
    assert peticiones[-1].get_method() == "DELETE"
    with pytest.raises(APIError):
        remoto.ruta("../otra.pdf")
    assert len(peticiones) == 2
    assert storage.SinRedireccion().redirect_request(None, None, 302, "", {}, "https://ajeno") is None


def test_storage_subida_real_y_limite(monkeypatch, remoto):
    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGB", (1, 1)).save(stream, format="PNG")
    datos = stream.getvalue()
    peticiones = []
    class Transporte:
        def open(self, request, **kwargs):
            peticiones.append(request)
            return io.BytesIO(b"{}")
    monkeypatch.setattr(storage, "build_opener", lambda *a: Transporte())
    nombre, mime = remoto.guardar(datos)
    assert storage.NOMBRE.fullmatch(nombre) and mime == "image/png"
    assert peticiones[0].data == datos and peticiones[0].get_method() == "POST"
    monkeypatch.setattr(settings, "VOUCHER_MAX_BYTES", 10)
    with pytest.raises(APIError) as error:
        remoto.guardar(datos)
    assert error.value.status_code == 413 and len(peticiones) == 1


def test_readiness_sin_redis_no_fabrica_ping(monkeypatch):
    from src.core import health

    monkeypatch.setattr(settings, "REDIS_REQUIRED", False)
    ping = AsyncMock()
    monkeypatch.setattr(health, "comprobar_redis", ping)
    monkeypatch.setattr(health, "comprobar_postgres", AsyncMock())
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["dependencies"]["redis"] == "disabled"
    ping.assert_not_awaited()


def test_descarga_remota_sigue_siendo_privada():
    from src.core.security import get_current_user
    from src.modules.pagos.persistencia import get_pagos_service

    service = AsyncMock()
    service.voucher.return_value = (b"contenido", f"{uuid4()}.pdf")
    app.dependency_overrides[get_current_user] = lambda: {"rol": "ADMIN_JUNTA"}
    app.dependency_overrides[get_pagos_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/pagos/{uuid4()}/voucher")
            assert response.content == b"contenido"
            assert response.headers["content-type"] == "application/pdf"
            assert response.headers["cache-control"] == "private, no-store"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_pagos_service, None)


@pytest.mark.parametrize("codigo,esperado", [(404, 404), (403, 503), (500, 503), (302, 503)])
def test_storage_no_expone_error(monkeypatch, remoto, codigo, esperado):
    class Transporte:
        def open(self, *args, **kwargs):
            raise HTTPError("https://secreto", codigo, "secreto", {}, None)
    monkeypatch.setattr(storage, "build_opener", lambda *a: Transporte())
    with pytest.raises(APIError) as e:
        remoto.ruta(f"{uuid4()}.pdf")
    assert e.value.status_code == esperado and "secreto" not in e.value.mensaje


@pytest.mark.asyncio
async def test_job_exclusion_y_orden(monkeypatch):
    pasos = []
    class DB:
        @asynccontextmanager
        async def begin(self):
            yield
        async def scalar(self, query):
            return True
    @asynccontextmanager
    async def factory():
        yield DB()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    for nombre in ("emitir_pendientes", "evaluar_moras_diarias", "recuperar_eventos", "limpiar_pendientes"):
        async def paso(_nombre=nombre, **kwargs):
            pasos.append((_nombre, kwargs))
        monkeypatch.setattr(jobs, nombre, paso)
    await jobs.ejecutar_diario()
    assert [p[0] for p in pasos] == ["emitir_pendientes", "evaluar_moras_diarias", "recuperar_eventos", "limpiar_pendientes"]
    assert pasos[0][1] == pasos[1][1] == {"estricto": True}
    monkeypatch.setattr(DB, "scalar", AsyncMock(return_value=False))
    with pytest.raises(APIError) as error:
        await jobs.ejecutar_diario()
    assert error.value.status_code == 409 and len(pasos) == 4


def test_cron_protegido_preview_y_fallo(monkeypatch):
    ejecutar = AsyncMock()
    monkeypatch.setattr(jobs, "ejecutar_diario", ejecutar)
    monkeypatch.setattr(settings, "CRON_SECRET", SecretStr("cron-prueba"))
    with TestClient(app) as client:
        assert client.get("/api/v1/jobs/diario").status_code == 401
        ejecutar.assert_not_awaited()
        headers = {"Authorization": "Bearer cron-prueba"}
        monkeypatch.setenv("VERCEL_ENV", "preview")
        assert client.get("/api/v1/jobs/diario", headers=headers).status_code == 403
        ejecutar.assert_not_awaited()
        monkeypatch.setenv("VERCEL_ENV", "production")
        assert client.get("/api/v1/jobs/diario", headers=headers).json()["correo_enviado"] is False
        ejecutar.side_effect = RuntimeError("no divulgar")
        r = client.get("/api/v1/jobs/diario", headers=headers)
        assert r.status_code == 503 and "no divulgar" not in r.text
