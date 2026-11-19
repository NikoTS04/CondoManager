from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.reservas.models import BloqueoArea
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


async def test_bloqueo_calendario_reserva_y_liberacion(api_usuarios):
    client, base = api_usuarios
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    datos = turno(base, AREA)
    ruta = f"/api/v1/condominios/{base.cid}/areas/{AREA}/bloqueos"
    body = {
        "inicio": datos["fecha_reserva"] + "T14:00:00-05:00",
        "fin": datos["fecha_reserva"] + "T16:00:00-05:00", "motivo": "Mantenimiento",
    }
    assert (await client.post(ruta, headers=residente, json=body)).status_code == 403
    r = await client.post(ruta, headers=junta, json=body)
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    calendario = await client.get(f"/api/v1/areas/{AREA}/disponibilidad", headers=residente, params={"fecha": datos["fecha_reserva"]})
    assert calendario.json() == [{"hora_inicio": "14:00:00", "hora_fin": "16:00:00"}]
    assert (await client.post("/api/v1/reservas", headers=residente, json=datos)).status_code == 409
    assert (await client.delete(ruta + "/" + bid, headers=junta)).status_code == 200
    assert (await client.delete(ruta + "/" + bid, headers=junta)).status_code == 200
    assert (await client.post("/api/v1/reservas", headers=residente, json=datos)).status_code == 201
    assert (await client.post(ruta, headers=junta, json=body)).status_code == 409
    async with base.sessions() as db:
        assert (await db.get(BloqueoArea, UUID(bid))).activo is False
        assert await db.scalar(select(func.count()).select_from(AuditoriaLogORM).where(
            AuditoriaLogORM.accion_ejecutada.in_(["AREA_BLOQUEADA", "BLOQUEO_LEVANTADO"])
        )) == 2
