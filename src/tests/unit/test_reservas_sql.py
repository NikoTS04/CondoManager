"""Ausencia de fallbacks y retiro explícito del endpoint financiero ficticio."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.core.errors import APIError
from src.core.security import get_current_user
from src.main import app
from src.modules.reservas import router
from src.modules.reservas.cancelaciones import CancelacionesService
from src.modules.reservas.disponibilidad import DisponibilidadRepository, DisponibilidadService


@pytest.mark.asyncio
async def test_calendario_no_oculta_esquema_ausente():
    session = AsyncMock()
    session.execute.side_effect = SQLAlchemyError("tabla ausente")
    with pytest.raises(APIError) as error:
        await DisponibilidadRepository(session).reservas_confirmadas(uuid4(), uuid4(), date.today())
    assert error.value.status_code == 503
    assert session.execute.await_count == 1
    session.scalar.assert_not_awaited()
    assert not hasattr(router, "RESERVAS_REGISTRADAS")
    assert not hasattr(DisponibilidadService, "combinar_fuentes")


@pytest.mark.asyncio
async def test_historial_no_oculta_esquema_ausente():
    session = AsyncMock()
    session.execute.side_effect = SQLAlchemyError("tabla ausente")
    with pytest.raises(APIError) as error:
        await CancelacionesService(session).historial(uuid4(), {"rol": "ADMIN_JUNTA"})
    assert error.value.status_code == 503
    session.scalar.assert_not_awaited()


@pytest.mark.parametrize(
    "rol,ajeno,esperado",
    [
        ("ADMIN_JUNTA", False, 410),
        ("SUPERADMIN", False, 410),
        ("ADMIN_JUNTA", True, 403),
        ("AUDITOR", False, 403),
        ("RESIDENTE", False, 403),
    ],
)
def test_mora_manual_retirada_conserva_autorizacion(rol, ajeno, esperado):
    cid = uuid4()
    actor = {"rol": rol, "condominio_id": str(cid), "sub": str(uuid4())}
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/moras/evaluar",
                json={
                    "condominio_id": str(uuid4() if ajeno else cid),
                },
            )
            assert response.status_code == esperado, response.text
            if esperado == 410:
                assert response.json()["error_code"] == "EVALUACION_MANUAL_RETIRADA"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
