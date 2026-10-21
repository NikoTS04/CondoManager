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
from src.modules.notificaciones.persistencia import get_notificaciones_service
from src.modules.reservas.areas.repository import get_areas_repository
from src.modules.reservas.persistencia import get_reservas_service
from src.modules.usuarios.departamentos import get_departamentos_portal_repository
from src.modules.usuarios.repository import get_usuarios_repository
from src.tests.areas import AreasCatalogoFake
from src.tests.departamentos import CatalogoDepartamentosFake
from src.tests.identidad import RepositorioIdentidadDemo

pytest_plugins = ["src.tests.usuarios_db", "src.tests.finanzas_contrato", "src.tests.pagos_db"]


@pytest.fixture
def autorizacion_aislada(finanzas_contrato, monkeypatch):
    from src.tests import reservas_contrato
    from src.tests.reservas_contrato import NotificacionesContrato, ReservasContrato

    monkeypatch.setattr(reservas_contrato, "RESERVAS_REGISTRADAS", {})
    monkeypatch.setattr(reservas_contrato, "NOTIFICACIONES_REGISTRADAS", {})

    async def actor(auth=Depends(security_scheme)):
        if auth is None:
            raise APIError(401, "NO_AUTENTICADO", "Se requiere un Bearer Token válido.")
        return decode_access_token(auth.credentials)

    app.dependency_overrides[get_current_user] = actor
    catalogo = CatalogoDepartamentosFake()
    app.dependency_overrides[get_departamentos_portal_repository] = lambda: catalogo
    areas = AreasCatalogoFake()
    app.dependency_overrides[get_areas_repository] = lambda: areas
    app.dependency_overrides[get_reservas_service] = lambda: ReservasContrato(
        areas, finanzas_contrato
    )
    app.dependency_overrides[get_notificaciones_service] = lambda: NotificacionesContrato()
    yield catalogo
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_departamentos_portal_repository, None)
    app.dependency_overrides.pop(get_areas_repository, None)
    app.dependency_overrides.pop(get_reservas_service, None)
    app.dependency_overrides.pop(get_notificaciones_service, None)


@pytest.fixture
def identidad_piloto(monkeypatch):
    repo = RepositorioIdentidadDemo()
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    app.dependency_overrides[get_usuarios_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_usuarios_repository, None)
