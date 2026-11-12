from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.core.security import get_current_user
from src.main import app
from src.modules.pagos.persistencia import get_pagos_service


@pytest.mark.parametrize("disposicion", ["inline", "attachment"])
def test_vista_privada_y_descarga(tmp_path, disposicion):
    archivo = tmp_path / "evidencia.pdf"
    archivo.write_bytes(b"%PDF-1.4\nprueba")
    service = AsyncMock()
    service.voucher.return_value = (archivo, archivo.name)
    app.dependency_overrides[get_current_user] = lambda: {"rol": "ADMIN_JUNTA"}
    app.dependency_overrides[get_pagos_service] = lambda: service
    try:
        id = uuid4()
        with TestClient(app) as client:
            response = client.get(f"/api/v1/pagos/{id}/voucher?disposicion={disposicion}")
            assert response.status_code == 200
            assert response.headers["content-disposition"].startswith(disposicion)
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert client.get(f"/api/v1/pagos/{id}/voucher?disposicion=public").status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_pagos_service, None)
