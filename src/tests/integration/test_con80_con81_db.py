"""CON-80/81: procesos reales y errores de esquema sobre PostgreSQL aislado."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import select, text

from src.core.database import Base
from src.core.readiness import revisiones_esperadas
from src.modules.notificaciones.consumo import consumir
from src.modules.notificaciones.models import Notificacion
from src.modules.reservas.models import EventoReservaOutbox
from src.modules.usuarios.demo import id_demo
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_catalogo_areas_db import turno
from src.tests.integration.test_pagos_db import reportar

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
AREA = "11111111-1111-1111-1111-111111111101"


async def proceso(base, method, url, headers, body=None):
    child = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "src.tests.proceso_reservas",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "DATABASE_URL": base.url, "DEBUG": "false"},
    )
    request = {"method": method, "url": url, "headers": headers}
    if body is not None:
        request["json"] = body
    try:
        stdout, stderr = await asyncio.wait_for(
            child.communicate(json.dumps({"esquema": base.esquema, "request": request}).encode()),
            timeout=30,
        )
    except BaseException:
        if child.returncode is None:
            child.kill()
        await child.wait()
        raise
    assert child.returncode == 0, stderr.decode()
    return json.loads(stdout)


async def test_dos_procesos_comparten_reserva_cancelacion_y_reinicio(api_usuarios):
    client, base = api_usuarios
    auth = await login(client, "residente102@villabonita3.pe", "Residente123!")
    body = turno(base, AREA)
    results = await asyncio.gather(*[
        proceso(base, "POST", "/api/v1/reservas", auth, body) for _ in range(2)
    ])
    assert len({r["pid"] for r in results}) == 2
    assert sorted(r["status"] for r in results) == [201, 409], results
    original = next(r["body"] for r in results if r["status"] == 201)
    listado = await proceso(base, "GET", "/api/v1/reservas", auth)
    assert listado["status"] == 200 and listado["body"] == [original]
    cancelada = await proceso(
        base, "POST", f"/api/v1/reservas/{original['id']}/cancelar", auth
    )
    assert cancelada["status"] == 200
    reinicio = await proceso(base, "GET", "/api/v1/reservas", auth)
    assert reinicio["body"][0]["id"] == original["id"]
    assert reinicio["body"][0]["estado"] == "CANCELADA"
    nueva = await proceso(base, "POST", "/api/v1/reservas", auth, body)
    assert nueva["status"] == 201 and nueva["body"]["id"] != original["id"]


async def test_dos_procesos_comparten_pago_y_aviso_persistidos(api_pagos):
    client, base = api_pagos
    auth = await login(client, "residente102@villabonita3.pe", "Residente123!")
    pago = await reportar(client, auth, numero="102")
    assert pago.status_code == 202
    reserva = await client.post("/api/v1/reservas", headers=auth, json=turno(base, AREA))
    assert reserva.status_code == 201
    async with base.sessions() as db:
        payload = (await db.scalar(select(EventoReservaOutbox))).payload
    assert await consumir(base.sessions, payload) == 1
    async with base.sessions() as db:
        aviso = await db.scalar(select(Notificacion))
        assert str(aviso.operacion_id) == reserva.json()["id"]
        aviso_id = str(aviso.id)
    for path in ("/api/v1/pagos/comprobantes", "/api/v1/notificaciones/logs"):
        a, b = await asyncio.gather(*[proceso(base, "GET", path, auth) for _ in range(2)])
        assert a["pid"] != b["pid"]
        assert a["status"] == b["status"] == 200
        assert a["body"] == b["body"] and len(a["body"]) == 1
        if path.endswith("comprobantes"):
            assert a["body"][0]["id"] == pago.json()["comprobante_id"]
        else:
            assert a["body"][0]["id"] == aviso_id


@pytest.mark.parametrize("tabla,path,codigo", [
    ("reservas", "/reservas", "RESERVAS_NO_DISPONIBLES"),
    ("reservas", f"/areas/{AREA}/disponibilidad", "DISPONIBILIDAD_NO_DISPONIBLE"),
    ("bloqueos_area", f"/areas/{AREA}/disponibilidad", "DISPONIBILIDAD_NO_DISPONIBLE"),
])
async def test_tabla_ausente_es_error_no_calendario_libre(api_usuarios, tabla, path, codigo):
    client, base = api_usuarios
    auth = await login(client, "residente102@villabonita3.pe", "Residente123!")
    async with base.engine.begin() as conn:
        await conn.execute(text(f'ALTER TABLE "{tabla}" RENAME TO "{tabla}_ausente"'))
    response = await client.get(
        "/api/v1" + path, headers=auth, params={"fecha": turno(base, AREA)["fecha_reserva"]}
    )
    assert response.status_code == 503 and response.json()["error_code"] == codigo
    assert base.esquema not in response.text


@pytest.mark.parametrize("rotura", ["ninguna", "revision", "tabla", "columna"])
async def test_readiness_comprueba_revision_y_columnas_reales(api_usuarios, rotura):
    client, base = api_usuarios
    async with base.engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)"))
        await conn.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": revisiones_esperadas()[0] if rotura != "revision" else "antigua"},
        )
        if rotura == "tabla":
            await conn.execute(text("ALTER TABLE bloqueos_area RENAME TO bloqueos_ausentes"))
        elif rotura == "columna":
            await conn.execute(text("ALTER TABLE reservas RENAME COLUMN usuario_id TO creador_ausente"))
    response = await client.get("/api/v1/ready")
    assert response.status_code == (200 if rotura == "ninguna" else 503), response.text


async def test_seed_repetible_conserva_cuentas_y_estados(db_usuarios):
    from scripts.seed_areas_demo import cargar_areas_demo
    from scripts.seed_usuarios_demo import cargar_demo
    from src.modules.usuarios.models import Usuario

    async with db_usuarios.sessions() as db, db.begin():
        user = await db.get(Usuario, id_demo("residente102@villabonita3.pe"))
        user.esta_activo = False
        password = user.password_hash
    async with db_usuarios.sessions() as db, db.begin():
        assert await cargar_demo(db) == 0
        assert await cargar_areas_demo(db) == 0
    async with db_usuarios.sessions() as db:
        user = await db.get(Usuario, id_demo("residente102@villabonita3.pe"))
        assert not user.esta_activo and user.password_hash == password


async def test_modo_normal_no_importa_dobles_ni_almacenes_reservas():
    import ast

    raiz = Path(__file__).resolve().parents[2]
    for path in (raiz / "modules").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("src.tests"), path
            elif isinstance(node, ast.Name):
                assert node.id != "RESERVAS_REGISTRADAS", path
    assert "bloqueos_area" in Base.metadata.tables
