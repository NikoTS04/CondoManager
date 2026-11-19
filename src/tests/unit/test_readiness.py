"""CON-81: salud HTTP independiente y fallos operativos sin filtración de secretos."""

from unittest.mock import AsyncMock

import pytest
from asyncpg import InvalidPasswordError
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.core.database import get_db_session
from src.core.readiness import revisiones_esperadas, verificar_esquema
from src.main import app


@pytest.fixture
def session(monkeypatch):
    session = AsyncMock()

    async def dependency():
        yield session

    monkeypatch.setitem(app.dependency_overrides, get_db_session, dependency)
    return session


def test_liveness_no_consulta_postgres(session):
    with TestClient(app) as client:
        for path in ("/health", "/api/v1/health"):
            assert client.get(path).status_code == 200
    session.execute.assert_not_called()
    session.scalars.assert_not_called()


@pytest.mark.parametrize("path", ["/ready", "/api/v1/ready"])
def test_readiness_informa_revision_sin_secretos(session, monkeypatch, path):
    check = AsyncMock(return_value=revisiones_esperadas())
    monkeypatch.setattr("src.core.readiness.verificar_esquema", check)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "status": "ok", "database": "ok", "schema_revision": revisiones_esperadas()
    }
    check.assert_awaited_once_with(session)


@pytest.mark.parametrize("error", [
    SQLAlchemyError("postgresql://usuario:secreto@host/base"),
    InvalidPasswordError("password privado"),
    OSError("host privado"), TimeoutError("timeout"), ValueError("columna privada"),
])
def test_readiness_falla_cerrado(session, monkeypatch, error):
    monkeypatch.setattr("src.core.readiness.verificar_esquema", AsyncMock(side_effect=error))
    with TestClient(app) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "error_code": "SERVICIO_NO_DISPONIBLE",
        "mensaje": "El servicio no está disponible. Intente más tarde.",
    }


@pytest.mark.asyncio
async def test_revision_distinta_o_multiple_no_declara_listo():
    session = AsyncMock()
    for revisions in ([], ["vieja"], [*revisiones_esperadas(), "otra"]):
        session.scalars.return_value = revisions
        with pytest.raises(ValueError):
            await verificar_esquema(session)
