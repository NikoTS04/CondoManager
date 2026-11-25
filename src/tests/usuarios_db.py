"""Fixtures de identidad y tenencia: migraciones y sesiones PostgreSQL independientes."""

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.seed_areas_demo import cargar_areas_demo
from scripts.seed_usuarios_demo import cargar_demo
from src.core.config import settings
from src.core.database import get_db_session
from src.main import app
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID

REVISIONES = (
    "20261008_0001_crear_condominios_y_auditoria",
    "20261008_0002_crear_presupuestos_mensuales",
    "20261014_0003_crear_configuracion_distribucion",
    "20261014_0004_crear_aplicaciones_saldo_favor",
    "20261018_0005_estructura_inmobiliaria",
    "20261019_0006_emision_cuotas",
    "20261020_0007_alta_usuarios",
    "20261020_0008_roles_revocables",
    "20261020_0009_vinculos_departamentos",
    "20261020_0010_catalogo_areas",
    "20261020_0009_pagos_persistentes",
    "20261020_0012_reservas_notificaciones",
    "20261021_0013_convergencia_con72",
)
# Esquema completo (cabeza de Alembic) para la API: añade cancelaciones y alertas, que
# las pruebas de migración aplican por separado sobre REVISIONES.
REVISIONES_API = (
    *REVISIONES,
    "20261021_0012_cancelaciones_reserva",
    "20261021_0014_unir_reservas_y_convergencia",
    "20261021_0015_alertas_notificaciones",
    "20261024_0016_politica_mora_diaria",
    "20261024_0017_condiciones_pago",
    "20261025_0018_prorrateo_detallado",
    "20261025_0019_motor_mora_diaria",
    "20261025_0020_fondos_moras",
    "20261113_0021_invitaciones_identidad",
    "20261121_0022_notificaciones_completas",
    "20261124_0023_incidencias",
    "20261124_0024_clasificacion_incidencias",
    "20261125_0025_alertas_fallos_definitivos",
    "20261126_0026_alertas_contratos",
    "20261127_0027_asignacion_incidencias",
    "20261128_0028_seguimiento_incidencias",
    "20261129_0029_cierre_incidencias",
)

_ROOT = Path(__file__).resolve().parents[2]
_PLANTILLAS_LISTAS: set[tuple[str, str]] = set()
_PLANTILLAS_FALLBACK: set[str] = set()


def migrar(connection, revisiones=None):
    revisiones = REVISIONES_API if revisiones is None else revisiones
    with Operations.context(MigrationContext.configure(connection)):
        for nombre in revisiones:
            import_module("migrations.versions." + nombre).upgrade()


def copiar_demo_legacy(connection, esquema_origen):
    """Semilla histórica sin cargar el ORM actual sobre tablas de otra versión."""
    from sqlalchemy import inspect

    inspector = inspect(connection)
    quote = connection.dialect.identifier_preparer.quote_identifier
    for tabla in (
        "condominios",
        "edificios",
        "departamentos",
        "usuarios",
        "usuario_roles",
        "usuario_departamentos",
        "areas_comunes",
    ):
        columnas = ", ".join(quote(c["name"]) for c in inspector.get_columns(tabla))
        connection.execute(
            text(
                f"INSERT INTO {quote(tabla)} ({columnas}) "
                f"SELECT {columnas} FROM {quote(esquema_origen)}.{quote(tabla)}"
            )
        )


def worker_id() -> str:
    """Identificador corto y seguro de worker xdist para nombres efímeros."""
    raw = os.getenv("PYTEST_XDIST_WORKER", "main").lower()
    return re.sub(r"[^a-z0-9_]", "_", raw)[:10] or "main"


def _normalizar_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=False)


def _url_para_db(url: str, db_name: str) -> str:
    return make_url(url).set(database=db_name).render_as_string(hide_password=False)


def _hash_plantilla(revisiones: tuple[str, ...], esquema: str, *, con_seed: bool) -> str:
    h = hashlib.sha256()
    h.update(b"cm_template_v1\0")
    h.update(esquema.encode() + b"\0")
    h.update(b"seeded\0" if con_seed else b"plain\0")
    for rev in revisiones:
        h.update(rev.encode() + b"\0")
        ruta = _ROOT / "migrations" / "versions" / f"{rev}.py"
        if ruta.is_file():
            h.update(ruta.read_bytes())
    if con_seed:
        for rel in (
            "scripts/seed_usuarios_demo.py",
            "scripts/seed_areas_demo.py",
            "scripts/seed_condominio_piloto.py",
            "src/modules/usuarios/demo.py",
            "src/modules/usuarios/piloto.py",
        ):
            ruta = _ROOT / rel
            if ruta.is_file():
                h.update(rel.encode() + b"\0")
                h.update(ruta.read_bytes())
    return h.hexdigest()[:16]


def _sqlstate(exc: BaseException) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def _terminar_sesiones_db(conn, db_name: str) -> None:
    await conn.execute(
        text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :db AND pid <> pg_backend_pid()"
        ),
        {"db": db_name},
    )


async def _drop_database(conn, db_name: str) -> None:
    try:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    except DBAPIError:
        await _terminar_sesiones_db(conn, db_name)
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))


async def _poblar_db(
    db_url: str, esquema: str, revisiones: tuple[str, ...], *, con_seed: bool
) -> None:
    admin = create_async_engine(db_url, poolclass=NullPool)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{esquema}"'))
    finally:
        await admin.dispose()

    engine = create_async_engine(
        db_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": esquema}}
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: migrar(c, revisiones))
        if con_seed:
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as session, session.begin():
                await cargar_demo(session)
                await cargar_areas_demo(session)
    finally:
        await engine.dispose()


async def _asegurar_plantilla(
    admin_url: str, tpl_db: str, esquema: str, revisiones: tuple[str, ...], *, con_seed: bool
) -> None:
    clave = (_normalizar_url(admin_url), tpl_db)
    if clave in _PLANTILLAS_LISTAS:
        return

    admin = create_async_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    lock_id = int.from_bytes(hashlib.sha256(tpl_db.encode()).digest()[:8], "big", signed=True)
    try:
        async with admin.connect() as conn:
            await conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_id})
            try:
                existe = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": tpl_db}
                )
                if not existe:
                    build_db = f"{tpl_db}_b_{worker_id()}_{uuid4().hex[:8]}"
                    await conn.execute(text(f'CREATE DATABASE "{build_db}"'))
                    try:
                        await _poblar_db(
                            _url_para_db(admin_url, build_db),
                            esquema,
                            revisiones,
                            con_seed=con_seed,
                        )
                        await _terminar_sesiones_db(conn, build_db)
                        await conn.execute(
                            text(f'ALTER DATABASE "{build_db}" RENAME TO "{tpl_db}"')
                        )
                    except Exception:
                        await _drop_database(conn, build_db)
                        raise
                    await _terminar_sesiones_db(conn, tpl_db)
                _PLANTILLAS_LISTAS.add(clave)
            finally:
                await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_id})
    finally:
        await admin.dispose()


async def crear_base_plantilla(
    url: str,
    *,
    prefijo: str = "cm",
    esquema: str = "con04_tpl",
    revisiones: tuple[str, ...] | None = None,
    con_seed: bool = True,
) -> tuple[str, str, str] | None:
    """Clona una base plantilla migrada (y opcionalmente sembrada) o devuelve None en fallback."""
    norm_url = _normalizar_url(url)
    if norm_url in _PLANTILLAS_FALLBACK:
        return None

    revs = REVISIONES_API if revisiones is None else revisiones
    tpl_prefix = "cm_tpl" if con_seed else "cm_raw"
    tpl_db = f"{tpl_prefix}_{_hash_plantilla(revs, esquema, con_seed=con_seed)}"
    test_db = f"{prefijo}_{worker_id()}_{uuid4().hex[:14]}"

    try:
        await _asegurar_plantilla(url, tpl_db, esquema, revs, con_seed=con_seed)
        admin = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
        try:
            async with admin.connect() as conn:
                ver = int(await conn.scalar(text("SHOW server_version_num")) or 0)
                strategy = " STRATEGY = WAL_LOG" if ver >= 150000 else ""
                for intento in range(6):
                    try:
                        await conn.execute(
                            text(f'CREATE DATABASE "{test_db}" TEMPLATE "{tpl_db}"{strategy}')
                        )
                        break
                    except DBAPIError as exc:
                        state = _sqlstate(exc)
                        if state == "55006" and intento < 5:
                            await _terminar_sesiones_db(conn, tpl_db)
                            await asyncio.sleep(0.02 * (intento + 1))
                            continue
                        if state == "3D000" and intento == 0:
                            _PLANTILLAS_LISTAS.discard((norm_url, tpl_db))
                            await _asegurar_plantilla(url, tpl_db, esquema, revs, con_seed=con_seed)
                            continue
                        raise
        finally:
            await admin.dispose()
    except (DBAPIError, OSError):
        _PLANTILLAS_FALLBACK.add(norm_url)
        return None

    return _url_para_db(url, test_db), esquema, test_db


async def borrar_base_plantilla(admin_url: str, db_name: str) -> None:
    """Elimina la base de datos efímera clonada de plantilla."""
    admin = create_async_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await _drop_database(conn, db_name)
    finally:
        await admin.dispose()


@dataclass
class BaseUsuarios:
    engine: object
    sessions: object
    esquema: str
    url: str
    cid: str = str(CONDOMINIO_PILOTO_ID)
    _admin_url: str | None = None
    _db_name: str | None = None


async def crear_base(url):
    clonada = await crear_base_plantilla(
        url, prefijo="con04", esquema="con04_tpl", revisiones=REVISIONES_API, con_seed=True
    )
    if clonada is not None:
        db_url, esquema, db_name = clonada
        engine = create_async_engine(
            db_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": esquema}}
        )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return BaseUsuarios(engine, sessions, esquema, db_url, _admin_url=url, _db_name=db_name)

    esquema = f"con04_{worker_id()}_{uuid4().hex[:16]}"
    await _poblar_db(url, esquema, REVISIONES_API, con_seed=True)
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args={"server_settings": {"search_path": esquema}}
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
    return BaseUsuarios(engine, sessions, esquema, url)


async def borrar_base(base):
    await base.engine.dispose()
    if base._db_name and base._admin_url:
        await borrar_base_plantilla(base._admin_url, base._db_name)
        return
    admin = create_async_engine(base.url, poolclass=NullPool)
    async with admin.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA "{base.esquema}" CASCADE'))
    await admin.dispose()


@pytest.fixture
def db_usuarios(monkeypatch):
    url = (
        os.getenv("CON46_TEST_DATABASE_URL")
        or os.getenv("CON39_TEST_DATABASE_URL")
        or os.getenv("CON05_TEST_DATABASE_URL")
        or os.getenv("CON06_TEST_DATABASE_URL")
        or os.getenv("CON04_TEST_DATABASE_URL")
        or os.getenv("CON13_TEST_DATABASE_URL")
    )
    if not url:
        pytest.skip(
            "Defina CON46_TEST_DATABASE_URL o CON04_TEST_DATABASE_URL con PostgreSQL de pruebas."
        )
    base = asyncio.run(crear_base(url))
    new_engine = create_async_engine(
        base.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": base.esquema}},
    )
    base.engine = new_engine
    base.sessions = async_sessionmaker(new_engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "DEMO_MODE", True)

    async def session():
        async with base.sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    previous = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = session
    yield base
    if previous is None:
        app.dependency_overrides.pop(get_db_session, None)
    else:
        app.dependency_overrides[get_db_session] = previous
    asyncio.run(borrar_base(base))


@pytest_asyncio.fixture
async def api_usuarios(db_usuarios):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        yield client, db_usuarios


@pytest.fixture
def cliente_usuarios(db_usuarios):
    with TestClient(app) as client:
        yield client, db_usuarios
