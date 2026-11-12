"""Escenarios SDD de CON-73 ejecutados sobre PostgreSQL real."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.main import app
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.notificaciones.worker import procesar_uno
from src.modules.reservas.models import EventoReservaOutbox, Reserva
from src.modules.reservas.persistencia import ReservasPersistentesService
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno

pytestmark = pytest.mark.postgres
scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/04-reservas/features/persistencia_sprint_2.feature"
    )
)
AREA = "11111111-1111-1111-1111-111111111101"


@pytest.fixture
def caso(db_usuarios):
    return {"base": db_usuarios}


async def crear(caso, veces=1):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        headers = await login(client, "residente102@villabonita3.pe", "Residente123!")
        respuestas = await asyncio.gather(
            *[
                client.post("/api/v1/reservas", headers=headers, json=turno(caso["base"], AREA))
                for _ in range(veces)
            ]
        )
        caso["respuestas"] = respuestas


async def obtener_evento(caso):
    async with caso["base"].sessions() as db:
        return (await db.scalar(select(EventoReservaOutbox))).payload


@given("un residente activo con unidad solvente y área persistente")
def precondicion(caso):
    async def comprobar():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login(client, "residente102@villabonita3.pe", "Residente123!")
            r = await client.get("/api/v1/areas", headers=headers)
            assert any(a["id"] == AREA for a in r.json())

    asyncio.run(comprobar())


@when("confirma una reserva y abre una sesión independiente")
def confirmar(caso):
    asyncio.run(crear(caso))
    assert caso["respuestas"][0].status_code == 201
    asyncio.run(caso["base"].engine.dispose())


@then("conserva el mismo identificador, tarifa y horario")
def conservada(caso):
    data = caso["respuestas"][0].json()

    async def comprobar():
        async with caso["base"].sessions() as db:
            r = await db.get(Reserva, UUID(data["id"]))
            assert str(r.costo_reserva) == data["costo_reserva"]
            assert r.hora_inicio.isoformat() == data["hora_inicio"]

    asyncio.run(comprobar())


@then("existe una auditoría y un evento pendiente de confirmación")
def evento_y_auditoria(caso):
    async def comprobar():
        async with caso["base"].sessions() as db:
            assert await db.scalar(
                select(AuditoriaLogORM.id).where(
                    AuditoriaLogORM.accion_ejecutada == "RESERVA_CONFIRMADA"
                )
            )
            assert (await db.scalar(select(EventoReservaOutbox))).publicado_en is None

    asyncio.run(comprobar())


@when("falla la escritura del evento de reserva")
def fallar_evento(caso, monkeypatch):
    def fallo(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr(ReservasPersistentesService, "evento", fallo)
    asyncio.run(crear(caso))
    assert caso["respuestas"][0].status_code == 500


@then("no quedan reserva, auditoría ni evento de éxito parciales")
def rollback(caso):
    async def comprobar():
        async with caso["base"].sessions() as db:
            assert await db.scalar(select(Reserva.id)) is None
            assert await db.scalar(select(EventoReservaOutbox.id)) is None
            assert (
                await db.scalar(
                    select(AuditoriaLogORM.id).where(
                        AuditoriaLogORM.accion_ejecutada == "RESERVA_CONFIRMADA"
                    )
                )
                is None
            )

    asyncio.run(comprobar())


@when("diez sesiones solicitan el mismo intervalo")
def diez(caso):
    asyncio.run(crear(caso, 10))


@then("una obtiene 201 y nueve obtienen 409")
def unico_ganador(caso):
    assert sorted(r.status_code for r in caso["respuestas"]) == [201] + [409] * 9


@given("una reserva confirmada con evento persistido")
def reserva_confirmada(caso):
    asyncio.run(crear(caso))
    assert caso["respuestas"][0].status_code == 201
    caso["payload"] = asyncio.run(obtener_evento(caso))


@when("dos workers consumen el mismo evento")
def reentrega(caso):
    async def ejecutar():
        return await asyncio.gather(
            *[consumir(caso["base"].sessions, caso["payload"]) for _ in range(2)]
        )

    assert sorted(asyncio.run(ejecutar())) == [0, 1]


@then("cada destinatario tiene un solo aviso lógico persistido")
def aviso_unico(caso):
    async def comprobar():
        async with caso["base"].sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Notificacion)) == 1

    asyncio.run(comprobar())


@given("un aviso persistido cuyo primer envío falla temporalmente")
def fallo_temporal(caso):
    reserva_confirmada(caso)
    asyncio.run(consumir(caso["base"].sessions, caso["payload"]))
    caso["ahora"] = datetime.now(UTC)
    asyncio.run(
        procesar_uno(
            caso["base"].sessions,
            lambda n, k: {"status": 503},
            caso["ahora"],
            jitter=lambda a, b: 0,
        )
    )


@when("reinicia el worker y vence el próximo reintento")
def reiniciar(caso):
    asyncio.run(caso["base"].engine.dispose())
    assert asyncio.run(
        procesar_uno(caso["base"].sessions, ahora=caso["ahora"] + timedelta(minutes=2))
    )


@then("conserva ambos intentos y la aceptación simulada queda ENVIADO")
def aceptado(caso):
    async def comprobar():
        async with caso["base"].sessions() as db:
            assert await db.scalar(select(func.count()).select_from(IntentoNotificacion)) == 2
            n = await db.scalar(select(Notificacion))
            assert n.estado == "ENVIADO" and n.transporte == "SIMULADO"

    asyncio.run(comprobar())
