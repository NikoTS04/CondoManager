"""Aislamiento explícito de identidad para pruebas de otros dominios.

CON-04/BDD usa PostgreSQL y las dependencias reales. Las pruebas de contrato de
otros módulos aíslan autenticación pero siguen comprobando firma, expiración y
autorización de sus recursos; no requieren inventar usuarios en cada fixture.
"""

import pytest
from fastapi import Depends

from src.core.config import settings
from src.core.errors import APIError
from src.core.security import decode_access_token, get_current_user, security_scheme
from src.main import app
from src.modules.usuarios.departamentos import get_departamentos_portal_repository
from src.modules.usuarios.repository import get_usuarios_repository
from src.tests.departamentos import CatalogoDepartamentosFake
from src.tests.identidad import RepositorioIdentidadDemo

pytest_plugins = ["src.tests.usuarios_db"]


@pytest.fixture
def autorizacion_aislada():
    async def actor(auth=Depends(security_scheme)):
        if auth is None:
            raise APIError(401, "NO_AUTENTICADO", "Se requiere un Bearer Token válido.")
        return decode_access_token(auth.credentials)

    app.dependency_overrides[get_current_user] = actor
    catalogo = CatalogoDepartamentosFake()
    app.dependency_overrides[get_departamentos_portal_repository] = lambda: catalogo
    yield catalogo
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_departamentos_portal_repository, None)


@pytest.fixture
def identidad_piloto(monkeypatch):
    repo = RepositorioIdentidadDemo()
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    app.dependency_overrides[get_usuarios_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_usuarios_repository, None)
