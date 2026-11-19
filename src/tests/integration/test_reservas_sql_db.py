"""CON-80: PostgreSQL real, fallo cerrado y proceso ASGI independiente."""

import asyncio
import json
import os
import subprocess
import sys
from uuid import UUID

import pytest
from sqlalchemy import func, select, text

from src.modules.reservas.models import CancelacionReserva, EventoReservaOutbox, Reserva
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


@pytest.mark.parametrize("tabla", ["reservas", "bloqueos_area"])
async def test_esquema_incompleto_no_simula_calendario(api_usuarios, tabla):
    client, base = api_usuarios
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    solicitud = turno(base, AREA)
    async with base.sessions() as db, db.begin():
        # La fixture crea un esquema exclusivo por prueba; no toca tablas operativas.
        await db.execute(text(f"ALTER TABLE {tabla} RENAME TO tabla_no_disponible"))
    response = await client.get(
        f"/api/v1/areas/{AREA}/disponibilidad",
        headers=residente,
        params={"fecha": solicitud["fecha_reserva"]},
    )
    assert response.status_code == 503, response.text
    response = await client.post("/api/v1/reservas", headers=residente, json=solicitud)
    assert response.status_code == 503, response.text
    if tabla == "reservas":
        response = await client.get("/api/v1/reservas", headers=residente)
        assert response.status_code == 503, response.text
    else:
        async with base.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Reserva)) == 0


OTRO_PROCESO = """
import asyncio, json, sys
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.main import app
from src.core.database import get_db_session

datos = json.load(sys.stdin)
async def main():
    engine = create_async_engine(datos['url'], connect_args={
        'server_settings': {'search_path': datos['esquema']}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def session():
        async with sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    app.dependency_overrides[get_db_session] = session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            headers = datos['headers']
            listado = await client.get('/api/v1/reservas', headers=headers)
            assert listado.status_code == 200 and any(
                r['id'] == datos['rid'] for r in listado.json())
            calendario = await client.get(
                '/api/v1/areas/' + datos['area'] + '/disponibilidad',
                headers=headers, params={'fecha': datos['fecha']})
            assert calendario.status_code == 200 and calendario.json()
            cancelada = await client.post(
                '/api/v1/reservas/' + datos['rid'] + '/cancelar', headers=headers)
            assert cancelada.status_code == 200, cancelada.text
            print(json.dumps(cancelada.json()))
    finally:
        await engine.dispose()
asyncio.run(main())
"""


async def test_otro_proceso_lee_y_cancela_sin_memoria(api_usuarios):
    client, base = api_usuarios
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    response = await client.post("/api/v1/reservas", headers=residente, json=turno(base, AREA))
    assert response.status_code == 201, response.text
    reserva = response.json()
    url = base.engine.url.render_as_string(hide_password=False)
    resultado = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", OTRO_PROCESO],
        input=json.dumps(
            {
                "url": url,
                "esquema": base.esquema,
                "headers": residente,
                "rid": reserva["id"],
                "area": AREA,
                "fecha": reserva["fecha_reserva"],
            }
        ),
        env={**os.environ, "DATABASE_URL": url, "DEBUG": "false"},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    cancelada = json.loads(resultado.stdout)
    repetida = await client.post(f"/api/v1/reservas/{reserva['id']}/cancelar", headers=residente)
    assert repetida.status_code == 200 and repetida.json() == cancelada
    async with base.sessions() as db:
        assert (await db.get(Reserva, UUID(reserva["id"]))).estado == "CANCELADA"
        assert await db.scalar(select(func.count()).select_from(CancelacionReserva)) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(EventoReservaOutbox)
                .where(EventoReservaOutbox.tipo == "ReservaCanceladaEvent")
            )
            == 1
        )


async def test_retiro_manual_no_modifica_finanzas(api_usuarios):
    from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID
    from src.tests.integration.test_aislamiento_con77_db import huella

    client, base = api_usuarios
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    antes = await huella(base)
    response = await client.post(
        "/api/v1/moras/evaluar",
        headers=junta,
        json={"condominio_id": str(CONDOMINIO_PILOTO_ID)},
    )
    assert response.status_code == 410, response.text
    assert response.json()["error_code"] == "EVALUACION_MANUAL_RETIRADA"
    assert await huella(base) == antes
