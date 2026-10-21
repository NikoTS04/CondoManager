"""CON-39: catálogo, condiciones, permisos y adopción en PostgreSQL real."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select, text

from scripts.seed_areas_demo import cargar_areas_demo
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento, Edificio
from src.modules.reservas import router as reservas
from src.modules.reservas.areas.models import AreaComun
from src.modules.reservas.areas.repository import AreasRepository
from src.modules.reservas.schemas import CancelarReservaRequest
from src.modules.reservas.service import CancelacionInvalidaException, ReservasService
from src.modules.usuarios.demo import id_demo
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


def datos_area(**extra):
    return {
        "nombre": "Salón CON-39",
        "descripcion": "Condiciones de prueba",
        "edificio_id": None,
        "aforo_maximo": 12,
        "costo_reserva": "35.75",
        "hora_apertura": "08:00",
        "hora_cierre": "22:00",
        "tiempo_maximo_horas": 4,
        **extra,
    }


def ruta(base, aid=None):
    return f"/api/v1/condominios/{base.cid}/areas" + (f"/{aid}" if aid else "")


def turno(base, aid, inicio="14:00", fin="16:00", did=None):
    from src.modules.usuarios.piloto import vinculo_piloto

    return {
        "condominio_id": base.cid,
        "area_id": str(aid),
        "departamento_id": str(
            did or vinculo_piloto("102", "PROPIETARIO_TITULAR")["departamento_id"]
        ),
        "fecha_reserva": (datetime.now(UTC).date() + timedelta(days=10)).isoformat(),
        "hora_inicio": inicio,
        "hora_fin": fin,
    }


@pytest_asyncio.fixture
async def caso_areas(api_usuarios, monkeypatch):
    client, base = api_usuarios
    monkeypatch.setattr(reservas, "RESERVAS_REGISTRADAS", {})
    return client, base, await login(client)


async def crear(client, base, admin, **extra):
    response = await client.post(ruta(base), headers=admin, json=datos_area(**extra))
    assert response.status_code == 201, response.text
    return response.json()


async def auditorias(base):
    async with base.sessions() as db:
        return list(
            await db.scalars(
                select(AuditoriaLogORM)
                .where(AuditoriaLogORM.accion_ejecutada.like("AREA_%"))
                .order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )


async def test_crud_sql_moneda_horas_normalizacion_y_persistencia(caso_areas):
    client, base, admin = caso_areas
    area = await crear(
        client, base, admin, nombre="  Salón CON-39  ", costo_reserva="9999999999.99"
    )
    assert area["nombre"] == "Salón CON-39" and area["esta_activa"]
    assert area["costo_reserva"] == "9999999999.99" and area["moneda"] == "PEN"
    assert area["hora_apertura"] == "08:00" and area["zona_horaria"] == "America/Lima"
    aid = area["id"]
    response = await client.put(
        ruta(base, aid),
        headers=admin,
        json=datos_area(nombre="Salón editado", costo_reserva="0.10"),
    )
    assert response.status_code == 200 and response.json()["costo_reserva"] == "0.10"
    await base.engine.dispose()
    assert (await client.get(ruta(base, aid), headers=admin)).json()["nombre"] == "Salón editado"
    async with base.sessions() as db:
        assert (await db.get(AreaComun, UUID(aid))).costo_reserva == Decimal("0.10")
    logs = await auditorias(base)
    assert [a.accion_ejecutada for a in logs] == ["AREA_CREADA", "AREA_ACTUALIZADA"]
    assert logs[1].hash_previo == logs[0].hash_actual
    assert logs[0].actor_id == str(id_demo("superadmin@condomanager.pe"))
    assert logs[1].estado_anterior["costo_reserva"] == "9999999999.99"


async def test_junta_escribe_auditor_solo_lee_y_residente_no_administra(caso_areas):
    client, base, _ = caso_areas
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    area = await crear(client, base, junta)
    auditor = await login(client, "auditor@villabonita3.pe", "Auditor123!")
    assert (await client.get(ruta(base), headers=auditor)).status_code == 200
    assert (await client.get(ruta(base, area["id"]), headers=auditor)).status_code == 200
    assert (await client.post(ruta(base), headers=auditor, json=datos_area())).status_code == 403
    assert (
        await client.put(ruta(base, area["id"]), headers=auditor, json=datos_area())
    ).status_code == 403
    assert (
        await client.patch(
            ruta(base, area["id"]) + "/estado", headers=auditor, json={"esta_activa": False}
        )
    ).status_code == 403
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    assert (await client.get(ruta(base), headers=residente)).status_code == 403
    assert (await client.post(ruta(base), headers=residente, json=datos_area())).status_code == 403
    assert (await client.get("/api/v1/areas", headers=residente)).status_code == 200


async def test_desactivacion_historial_costo_instantanea_y_restauracion(caso_areas):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    original = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, area["id"])
    )
    assert original.status_code == 201
    await client.put(
        ruta(base, area["id"]),
        headers=admin,
        json=datos_area(nombre="Nombre nuevo", costo_reserva="99.99"),
    )
    await client.patch(
        ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": False}
    )
    assert area["id"] not in {
        a["id"] for a in (await client.get("/api/v1/areas", headers=residente)).json()
    }
    assert not (await client.get(ruta(base, area["id"]), headers=admin)).json()["esta_activa"]
    respuesta = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, area["id"], "17:00", "18:00")
    )
    assert respuesta.status_code == 409 and respuesta.json()["error_code"] == "AREA_INACTIVA"
    assert (
        await client.get(
            f"/api/v1/areas/{area['id']}/disponibilidad?fecha=2026-12-01", headers=residente
        )
    ).status_code == 409
    historial = await client.get(f"/api/v1/reservas?area_id={area['id']}", headers=residente)
    assert historial.status_code == 200 and len(historial.json()) == 1
    assert (
        historial.json()[0]["costo_reserva"] == "35.75"
        and historial.json()[0]["area_nombre"] == area["nombre"]
    )
    # PUT sobre área inactiva conserva ese estado.
    assert not (await client.put(ruta(base, area["id"]), headers=admin, json=datos_area())).json()[
        "esta_activa"
    ]
    assert (
        await client.patch(
            ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": True}
        )
    ).json()["esta_activa"]
    assert (
        await client.post(
            "/api/v1/reservas", headers=residente, json=turno(base, area["id"], "18:00", "19:00")
        )
    ).status_code == 201


@pytest.mark.parametrize(
    "inicio,fin",
    [
        ("07:59", "09:00"),
        ("21:00", "22:01"),
        ("08:00", "12:01"),
        ("12:00", "12:00"),
        ("10:00:01", "11:00"),
        ("10:00+00:00", "11:00+00:00"),
    ],
)
async def test_horario_y_duracion_rechazados_sin_reserva(caso_areas, inicio, fin):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    response = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, area["id"], inicio, fin)
    )
    assert (
        response.status_code == 400
        and response.json()["detail"]["error_code"] == "HORARIO_INVALIDO"
    )
    assert reservas.RESERVAS_REGISTRADAS == {}


async def test_fronteras_exactas_y_precio_desde_sql(caso_areas):
    client, base, admin = caso_areas
    area = await crear(client, base, admin, costo_reserva="0.15")
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    for inicio, fin in (("08:00", "12:00"), ("18:00", "22:00")):
        body = {**turno(base, area["id"], inicio, fin), "costo_reserva": "0.00"}
        response = await client.post("/api/v1/reservas", headers=residente, json=body)
        assert response.status_code == 201 and response.json()["costo_reserva"] == "0.15"


@pytest.mark.parametrize("segundos", [-1, 0, 1])
async def test_cancelacion_de_turno_local_respetando_frontera_24_horas(caso_areas, segundos):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    response = await client.post(
        "/api/v1/reservas", headers=residente, json=turno(base, area["id"], "10:00", "11:00")
    )
    assert response.status_code == 201 and response.json()["moneda"] == "PEN"
    registro = reservas.RESERVAS_REGISTRADAS[UUID(response.json()["id"])]
    # 10:00 Lima equivale a 15:00 UTC; el límite es el día anterior a esa hora.
    limite = datetime.combine(
        registro["fecha_reserva"] - timedelta(days=1), datetime.min.time(), tzinfo=UTC
    ) + timedelta(hours=15)
    if segundos > 0:
        with pytest.raises(CancelacionInvalidaException):
            ReservasService.procesar_cancelacion(
                registro,
                CancelarReservaRequest(),
                momento_actual=limite + timedelta(seconds=segundos),
            )
    else:
        resultado, _ = ReservasService.procesar_cancelacion(
            registro, CancelarReservaRequest(), momento_actual=limite + timedelta(seconds=segundos)
        )
        assert resultado.estado == "CANCELADA"


async def test_dos_condominios_moneda_y_edificio_ajeno(caso_areas):
    client, base, admin = caso_areas
    otro = await otro_condominio(base)
    async with base.sessions() as db, db.begin():
        await db.execute(text("UPDATE condominios SET moneda='USD' WHERE id=:id"), {"id": otro})
        edificio = Edificio(
            id=uuid4(), condominio_id=otro, nombre_bloque="Edificio ajeno", total_pisos=2
        )
        db.add(edificio)
        await db.flush()
        unidad = Departamento(
            id=uuid4(),
            edificio_id=edificio.id,
            numero="USD-1",
            piso=1,
            coeficiente_participacion=Decimal("1.0000"),
            activo=True,
        )
        db.add(unidad)
    foreign = await client.post(
        f"/api/v1/condominios/{otro}/areas", headers=admin, json=datos_area()
    )
    assert foreign.status_code == 201 and foreign.json()["moneda"] == "USD"
    reserva_usd = await client.post(
        "/api/v1/reservas",
        headers=admin,
        json={
            **turno(base, foreign.json()["id"], did=unidad.id),
            "condominio_id": str(otro),
        },
    )
    assert reserva_usd.status_code == 201 and reserva_usd.json()["moneda"] == "USD"
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    assert (await client.get(f"/api/v1/condominios/{otro}/areas", headers=junta)).status_code == 403
    assert (await client.get(ruta(base, foreign.json()["id"]), headers=admin)).status_code == 404
    assert (
        await client.put(ruta(base, foreign.json()["id"]), headers=admin, json=datos_area())
    ).status_code == 404
    assert (
        await client.post(ruta(base), headers=admin, json=datos_area(edificio_id=str(edificio.id)))
    ).status_code == 404


async def test_area_exclusiva_filtra_catalogo_y_unidad_de_reserva(caso_areas):
    client, base, admin = caso_areas
    async with base.sessions() as db, db.begin():
        edificio = Edificio(
            id=uuid4(), condominio_id=UUID(base.cid), nombre_bloque="Exclusivo", total_pisos=1
        )
        db.add(edificio)
        await db.flush()
        unidad = Departamento(
            id=uuid4(),
            edificio_id=edificio.id,
            numero="EX-1",
            piso=1,
            coeficiente_participacion=Decimal("1.0000"),
            activo=True,
        )
        db.add(unidad)
    area = await crear(client, base, admin, edificio_id=str(edificio.id))
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    assert area["id"] not in {
        a["id"] for a in (await client.get("/api/v1/areas", headers=residente)).json()
    }
    assert (
        await client.get(
            f"/api/v1/areas/{area['id']}/disponibilidad?fecha=2026-12-01", headers=residente
        )
    ).status_code == 403
    assert (
        await client.post("/api/v1/reservas", headers=admin, json=turno(base, area["id"]))
    ).status_code == 403
    await client.put(
        f"/api/v1/condominios/{base.cid}/usuarios/{id_demo('residente102@villabonita3.pe')}/departamentos/{unidad.id}",
        headers=admin,
        json={"tipo_relacion": "PROPIETARIO_TITULAR"},
    )
    nuevo = await login(client, "residente102@villabonita3.pe", "Residente123!")
    assert area["id"] in {
        a["id"] for a in (await client.get("/api/v1/areas", headers=nuevo)).json()
    }
    assert (
        await client.post(
            "/api/v1/reservas", headers=nuevo, json=turno(base, area["id"], did=unidad.id)
        )
    ).status_code == 201


async def test_noop_paginacion_filtro_y_estado_concurrente(caso_areas):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    await client.put(ruta(base, area["id"]), headers=admin, json=datos_area())
    await client.patch(
        ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": True}
    )
    responses = await asyncio.gather(
        *(
            client.patch(
                ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": False}
            )
            for _ in range(2)
        )
    )
    assert [r.status_code for r in responses] == [200, 200]
    logs = await auditorias(base)
    assert [a.accion_ejecutada for a in logs] == ["AREA_CREADA", "AREA_ESTADO_CAMBIADO"]
    inactivas = await client.get(ruta(base) + "?esta_activa=false&limit=1&offset=0", headers=admin)
    assert [a["id"] for a in inactivas.json()] == [area["id"]]
    assert (await client.get(ruta(base) + "?limit=1&offset=100", headers=admin)).json() == []


async def test_rollback_de_auditoria_en_alta_edicion_y_estado(caso_areas):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    async with base.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE FUNCTION fallo_areas() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Fallo controlado'; END; $$"
            )
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fallo_areas BEFORE INSERT ON auditoria_logs FOR EACH ROW EXECUTE FUNCTION fallo_areas()"
            )
        )
    assert (
        await client.post(ruta(base), headers=admin, json=datos_area(nombre="No confirmar"))
    ).status_code == 500
    assert (
        await client.put(
            ruta(base, area["id"]), headers=admin, json=datos_area(costo_reserva="99.99")
        )
    ).status_code == 500
    assert (
        await client.patch(
            ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": False}
        )
    ).status_code == 500
    async with base.sessions() as db:
        original = await db.get(AreaComun, UUID(area["id"]))
        assert original.esta_activa and original.costo_reserva == Decimal("35.75")
        assert (
            await db.scalar(select(AreaComun.id).where(AreaComun.nombre == "No confirmar")) is None
        )


@pytest.mark.parametrize("reserva_primero", [False, True])
async def test_reserva_y_desactivacion_se_serializan(caso_areas, monkeypatch, reserva_primero):
    client, base, admin = caso_areas
    area = await crear(client, base, admin)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    esperando = asyncio.Event()
    original = AreasRepository.area

    async def area_bloqueada(repo, cid, aid, bloquear=False):
        if bloquear:
            esperando.set()
        return await original(repo, cid, aid, bloquear)

    monkeypatch.setattr(AreasRepository, "area", area_bloqueada)

    def patch():
        return client.patch(
            ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": False}
        )

    def reserva():
        return client.post("/api/v1/reservas", headers=residente, json=turno(base, area["id"]))

    async with base.sessions() as db:
        await db.execute(
            select(AreaComun).where(AreaComun.id == UUID(area["id"])).with_for_update()
        )
        primera = asyncio.create_task(reserva() if reserva_primero else patch())
        try:
            await asyncio.wait_for(esperando.wait(), timeout=10)
            segunda = asyncio.create_task(patch() if reserva_primero else reserva())
        finally:
            await db.rollback()
        responses = await asyncio.wait_for(asyncio.gather(primera, segunda), timeout=10)
    assert [r.status_code for r in responses] == ([201, 200] if reserva_primero else [200, 409])
    assert len(reservas.RESERVAS_REGISTRADAS) == (1 if reserva_primero else 0)


async def test_revalida_actor_que_esperaba_el_contexto(caso_areas, monkeypatch):
    client, base, _ = caso_areas
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    esperando = asyncio.Event()
    original = AreasRepository.contexto

    async def contexto(repo, cid, bloquear=False):
        if bloquear:
            esperando.set()
        return await original(repo, cid, bloquear)

    monkeypatch.setattr(AreasRepository, "contexto", contexto)
    async with base.engine.connect() as bloqueador:
        await bloqueador.execute(
            text("SELECT id FROM condominios WHERE id=:id FOR UPDATE"), {"id": UUID(base.cid)}
        )
        pendiente = asyncio.create_task(client.post(ruta(base), headers=junta, json=datos_area()))
        try:
            await asyncio.wait_for(esperando.wait(), timeout=10)
            async with base.engine.begin() as conn:
                await conn.execute(
                    text("UPDATE usuarios SET auth_revision=auth_revision+1 WHERE id=:id"),
                    {"id": id_demo("admin@villabonita3.pe")},
                )
        finally:
            await bloqueador.rollback()
        assert (await asyncio.wait_for(pendiente, timeout=10)).status_code == 401
    assert await auditorias(base) == []


@pytest.mark.parametrize(
    "cambios",
    [
        {"nombre": " "},
        {"nombre": "x" * 101},
        {"aforo_maximo": 0},
        {"aforo_maximo": True},
        {"aforo_maximo": 1.5},
        {"aforo_maximo": 2147483648},
        {"costo_reserva": 1.1},
        {"costo_reserva": "-1.00"},
        {"costo_reserva": "1.001"},
        {"costo_reserva": "10000000000.00"},
        {"costo_reserva": "NaN"},
        {"costo_reserva": "١.٠٠"},
        {"hora_apertura": "08:00:00"},
        {"hora_cierre": "08:00"},
        {"hora_cierre": "01:00"},
        {"hora_apertura": "25:00"},
        {"hora_apertura": "08:00+00:00"},
        {"hora_apertura": "0١:0١"},
        {"tiempo_maximo_horas": 0},
        {"tiempo_maximo_horas": 25},
        {"esta_activa": False},
        {"condominio_id": str(uuid4())},
        {"actor_id": "falso"},
    ],
)
async def test_validacion_de_configuracion_sin_escribir(caso_areas, cambios):
    client, base, admin = caso_areas
    response = await client.post(ruta(base), headers=admin, json=datos_area(**cambios))
    assert response.status_code == 422 and response.json()["error_code"] == "DATOS_AREA_INVALIDOS"
    assert await auditorias(base) == []


async def test_inexistentes_estado_estricto_y_sin_token(caso_areas):
    client, base, admin = caso_areas
    assert (await client.get(ruta(base))).status_code == 401
    # Un parámetro inválido de otro recurso no debe confundirse con el catálogo.
    invalido = await client.put(
        f"/api/v1/condominios/{base.cid}/usuarios/{id_demo('residente102@villabonita3.pe')}/departamentos/areas",
        headers=admin,
        json={"tipo_relacion": "PROPIETARIO_TITULAR"},
    )
    assert (
        invalido.status_code == 422 and invalido.json()["error_code"] == "DATOS_VINCULO_INVALIDOS"
    )
    assert (await client.get(ruta(base, uuid4()), headers=admin)).status_code == 404
    assert (
        await client.put(ruta(base, uuid4()), headers=admin, json=datos_area())
    ).status_code == 404
    assert (await client.get(ruta(base) + "?limit=101", headers=admin)).status_code == 422
    assert (
        await client.post(f"/api/v1/condominios/{uuid4()}/areas", headers=admin, json=datos_area())
    ).status_code == 404
    area = await crear(client, base, admin)
    for valor in ("true", 1, None):
        response = await client.patch(
            ruta(base, area["id"]) + "/estado", headers=admin, json={"esta_activa": valor}
        )
        assert (
            response.status_code == 422 and response.json()["error_code"] == "DATOS_AREA_INVALIDOS"
        )


async def test_seed_conserva_configuracion_y_area_desactivada(caso_areas):
    client, base, admin = caso_areas
    aid = "11111111-1111-1111-1111-111111111101"
    await client.put(
        ruta(base, aid),
        headers=admin,
        json=datos_area(nombre="Demo configurada", costo_reserva="0.25"),
    )
    await client.patch(ruta(base, aid) + "/estado", headers=admin, json={"esta_activa": False})
    async with base.sessions() as db, db.begin():
        assert await cargar_areas_demo(db) == 0
        area = await db.get(AreaComun, UUID(aid))
        assert (
            not area.esta_activa
            and area.nombre == "Demo configurada"
            and area.costo_reserva == Decimal("0.25")
        )


def operacion(conn, func):
    with Operations.context(MigrationContext.configure(conn)):
        func()


@pytest.mark.parametrize("base_antigua", [False, True])
async def test_migracion_adopta_preserva_datos_y_referencias(db_usuarios, base_antigua):
    base = db_usuarios
    revision = import_module("migrations.versions.20261020_0010_catalogo_areas")
    async with base.engine.begin() as conn:
        await conn.execute(text("COMMENT ON TABLE areas_comunes IS 'Catálogo histórico'"))
        await conn.execute(
            text(
                "UPDATE areas_comunes SET esta_activa=false,costo_reserva=17.25 WHERE id='11111111-1111-1111-1111-111111111101'"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE reserva_historica (id uuid PRIMARY KEY, area_id uuid REFERENCES areas_comunes(id) ON DELETE RESTRICT, costo numeric(12,2))"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO reserva_historica VALUES (gen_random_uuid(),'11111111-1111-1111-1111-111111111101',17.25)"
            )
        )
        await conn.run_sync(lambda c: operacion(c, revision.downgrade))
        if base_antigua:
            await conn.execute(
                text(
                    "ALTER TABLE areas_comunes DROP COLUMN edificio_id, DROP COLUMN tiempo_maximo_horas"
                )
            )
        await conn.run_sync(lambda c: operacion(c, revision.upgrade))
        assert await conn.scalar(text("SELECT count(*) FROM areas_comunes")) == 4
        assert await conn.scalar(
            text("SELECT costo_reserva FROM areas_comunes WHERE NOT esta_activa")
        ) == Decimal("17.25")
        assert await conn.scalar(text("SELECT costo FROM reserva_historica")) == Decimal("17.25")
        assert (
            await conn.scalar(text("SELECT hora_apertura::text FROM areas_comunes LIMIT 1"))
            == "00:00:00"
        )
        assert (await conn.run_sync(lambda c: inspect(c).get_table_comment("areas_comunes")))[
            "text"
        ] == "Catálogo histórico"
        await conn.run_sync(lambda c: operacion(c, revision.downgrade))
        assert await conn.scalar(text("SELECT count(*) FROM areas_comunes")) == 4
        assert await conn.scalar(text("SELECT count(*) FROM reserva_historica")) == 1


async def test_migracion_rechaza_edificio_de_otro_condominio(db_usuarios):
    base = db_usuarios
    otro = await otro_condominio(base)
    eid = uuid4()
    async with base.sessions() as db, db.begin():
        db.add(Edificio(id=eid, condominio_id=otro, nombre_bloque="Otro", total_pisos=1))
    revision = import_module("migrations.versions.20261020_0010_catalogo_areas")
    with pytest.raises(RuntimeError, match="condominios distintos"):
        async with base.engine.begin() as conn:
            await conn.run_sync(lambda c: operacion(c, revision.downgrade))
            await conn.execute(text("UPDATE areas_comunes SET edificio_id=:eid"), {"eid": eid})
            await conn.run_sync(lambda c: operacion(c, revision.upgrade))
    async with base.engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT count(*) FROM areas_comunes WHERE edificio_id IS NULL"))
            == 4
        )
