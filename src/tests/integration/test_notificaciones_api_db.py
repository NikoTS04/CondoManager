"""Pruebas de integración en PostgreSQL para la API persistente de notificaciones."""

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from src.core.config import settings
from src.core.database import get_db_session
from src.core.security import create_access_token
from src.main import app
from src.modules.condominios.models import Condominio
from src.modules.notificaciones.models import (
    AlertaAdministrativa,
    Notificacion,
    NotificacionIntento,
)
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import UsuarioDepartamento
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, vinculo_piloto
from src.tests.usuarios_db import borrar_base, crear_base, migrar

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


@pytest.fixture
def db_notificaciones_api(monkeypatch):
    url = (
        os.getenv("CON13_TEST_DATABASE_URL")
        or os.getenv("CON05_TEST_DATABASE_URL")
        or os.getenv("CON06_TEST_DATABASE_URL")
        or os.getenv("CON04_TEST_DATABASE_URL")
    )
    if not url:
        pytest.skip("Defina CON13_TEST_DATABASE_URL con una base PostgreSQL de pruebas.")

    async def _setup():
        base = await crear_base(url)
        async with base.engine.begin() as conn:
            reg = await conn.scalar(text("SELECT to_regclass('notificaciones')"))
            if reg is None:
                await conn.run_sync(
                    lambda c: migrar(c, ("20261021_0012_notificaciones_persistentes",))
                )
        return base

    base = asyncio.run(_setup())
    monkeypatch.setattr(settings, "DEMO_MODE", True)

    async def _session():
        async with base.sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    prev = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = _session
    yield base
    if prev is None:
        app.dependency_overrides.pop(get_db_session, None)
    else:
        app.dependency_overrides[get_db_session] = prev
    asyncio.run(borrar_base(base))


@pytest_asyncio.fixture
async def api_notificaciones(db_notificaciones_api):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client, db_notificaciones_api


async def _login(
    client: AsyncClient,
    email: str = "admin@villabonita3.pe",
    password: str = "Admin123!",
) -> dict[str, str]:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_comunicado_masivo_persistente_e_idempotente_por_id_y_nueva_sesion(
    api_notificaciones,
):
    client, base = api_notificaciones
    headers_junta = await _login(client, "admin@villabonita3.pe", "Admin123!")
    comunicado_id = uuid.uuid4()

    payload = {
        "id": str(comunicado_id),
        "condominio_id": base.cid,
        "titulo": "Corte programado de agua potable",
        "mensaje": "Sedapal realizará mantenimiento de cisternas el sábado de 08:00 a 13:00.",
        "canal": "EMAIL",
        "remitente": "Junta Directiva Villa Bonita 3",
    }

    res1 = await client.post(
        "/api/v1/notificaciones/comunicado-masivo",
        headers=headers_junta,
        json=payload,
    )
    assert res1.status_code == 202, res1.text
    datos1 = res1.json()
    assert datos1["comunicado_id"] == str(comunicado_id)
    assert datos1["condominio_id"] == base.cid
    assert datos1["total_destinatarios"] == 3
    assert datos1["notificaciones_generadas"] == 3
    assert datos1["estado_general"] == "EN_COLA"

    # Reintento con el mismo id -> idempotente, no duplica registros en BD
    res2 = await client.post(
        "/api/v1/notificaciones/comunicado-masivo",
        headers=headers_junta,
        json=payload,
    )
    assert res2.status_code == 202, res2.text
    datos2 = res2.json()
    assert datos2["comunicado_id"] == str(comunicado_id)
    assert datos2["total_destinatarios"] == 3
    assert datos2["notificaciones_generadas"] == 0

    # Verificación desde una nueva sesión independiente de PostgreSQL
    async with base.sessions() as nueva_sesion:
        filas = list(
            (
                await nueva_sesion.scalars(
                    select(Notificacion).where(
                        Notificacion.origen_tipo == "COMUNICADO",
                        Notificacion.origen_id == comunicado_id,
                    )
                )
            ).all()
        )
        assert len(filas) == 3
        assert all(f.estado == "EN_COLA" for f in filas)
        assert all(f.intentos == 0 for f in filas)
        assert {f.destinatario for f in filas} == {
            "residente102@villabonita3.pe",
            "inquilino504@villabonita3.pe",
            "moroso402@villabonita3.pe",
        }


async def test_logs_filtros_paginacion_y_detalle_con_historial_intentos(api_notificaciones):
    client, base = api_notificaciones
    headers_junta = await _login(client, "admin@villabonita3.pe", "Admin123!")
    headers_auditor = await _login(client, "auditor@villabonita3.pe", "Auditor123!")

    dpto_102 = uuid.UUID(vinculo_piloto("102", "PROPIETARIO_TITULAR")["departamento_id"])
    dpto_402 = uuid.UUID(vinculo_piloto("402", "PROPIETARIO_TITULAR")["departamento_id"])
    uid_102 = id_demo("residente102@villabonita3.pe")
    uid_402 = id_demo("moroso402@villabonita3.pe")
    ahora = datetime.now(UTC)

    notif_entregada_id = uuid.uuid4()
    notif_fallida_id = uuid.uuid4()

    async with base.sessions() as db, db.begin():
        db.add_all(
            [
                Notificacion(
                    id=notif_entregada_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_102,
                    usuario_id=uid_102,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_EMISION_CUOTA",
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"CUOTA:test:1:{notif_entregada_id}",
                    canal="EMAIL",
                    destinatario="residente102@villabonita3.pe",
                    asunto="Cuota 2026-10",
                    cuerpo="Detalle de cuota",
                    contexto={"dpto": "102", "periodo": "2026-10"},
                    estado="ENTREGADO",
                    intentos=2,
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    proveedor_message_id="sim-msg-102",
                    aceptado_en=ahora,
                    entregado_en=ahora,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
                Notificacion(
                    id=notif_fallida_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_402,
                    usuario_id=uid_402,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_PAGO_RECHAZADO",
                    plantilla="NOTIF_PAGO_RECHAZADO",
                    origen_tipo="COMPROBANTE",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"COMPROBANTE:test:1:{notif_fallida_id}",
                    canal="EMAIL",
                    destinatario="rebote402@villabonita3.pe",
                    asunto="Observación en comprobante",
                    cuerpo="Comprobante rechazado",
                    contexto={"dpto": "402"},
                    estado="FALLIDO_PERMANENTE",
                    intentos=1,
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    error_codigo="550",
                    error_mensaje="550 User unknown password=clave_secreta_smtp",
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
            ]
        )
        await db.flush()
        db.add_all(
            [
                NotificacionIntento(
                    notificacion_id=notif_entregada_id,
                    numero=1,
                    worker_id="worker-1",
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    resultado="FALLO_TEMPORAL",
                    codigo="503",
                    detalle="503 Service Unavailable token=secreto_interno",
                    iniciado_en=ahora,
                    finalizado_en=ahora,
                ),
                NotificacionIntento(
                    notificacion_id=notif_entregada_id,
                    numero=2,
                    worker_id="worker-1",
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    resultado="ACEPTADO",
                    proveedor_message_id="sim-msg-102",
                    iniciado_en=ahora,
                    finalizado_en=ahora,
                ),
            ]
        )

    # Filtro por departamento_id y estado
    res_logs = await client.get(
        "/api/v1/notificaciones/logs",
        headers=headers_junta,
        params={"departamento_id": str(dpto_402), "estado": "FALLIDO_PERMANENTE"},
    )
    assert res_logs.status_code == 200, res_logs.text
    lista = res_logs.json()
    assert len(lista) == 1
    item = lista[0]
    assert item["id"] == str(notif_fallida_id)
    assert item["transporte_simulado"] is True
    assert item["error_codigo"] == "550"
    assert "clave_secreta_smtp" not in item["error_mensaje"]
    assert "[REDACTED]" in item["error_mensaje"]

    # Filtro por origen_tipo y lectura por AUDITOR
    res_auditor = await client.get(
        "/api/v1/notificaciones/logs",
        headers=headers_auditor,
        params={"origen_tipo": "CUOTA"},
    )
    assert res_auditor.status_code == 200
    assert len(res_auditor.json()) == 1
    assert res_auditor.json()[0]["id"] == str(notif_entregada_id)
    assert res_auditor.json()[0]["aceptado_en"] is not None
    assert res_auditor.json()[0]["entregado_en"] is not None

    # Detalle con historial de intentos
    res_detalle = await client.get(
        f"/api/v1/notificaciones/logs/{notif_entregada_id}",
        headers=headers_auditor,
    )
    assert res_detalle.status_code == 200, res_detalle.text
    detalle = res_detalle.json()
    assert detalle["id"] == str(notif_entregada_id)
    assert len(detalle["historial_intentos"]) == 2
    assert [i["numero"] for i in detalle["historial_intentos"]] == [1, 2]
    assert "secreto_interno" not in (detalle["historial_intentos"][0]["detalle"] or "")


async def test_mis_notificaciones_aislamiento_residente_y_vinculos_activos(api_notificaciones):
    client, base = api_notificaciones
    headers_res_102 = await _login(client, "residente102@villabonita3.pe", "Residente123!")

    uid_102 = id_demo("residente102@villabonita3.pe")
    uid_504 = id_demo("inquilino504@villabonita3.pe")
    dpto_102 = uuid.UUID(vinculo_piloto("102", "PROPIETARIO_TITULAR")["departamento_id"])
    dpto_302 = uuid.UUID(vinculo_piloto("302", "PROPIETARIO_TITULAR")["departamento_id"])
    dpto_504 = uuid.UUID(vinculo_piloto("504", "INQUILINO")["departamento_id"])
    ahora = datetime.now(UTC)

    notif_propia_activa = uuid.uuid4()
    notif_propia_inactiva = uuid.uuid4()
    notif_otro_residente_misma_unidad = uuid.uuid4()
    notif_otro_residente_otra_unidad = uuid.uuid4()

    async with base.sessions() as db, db.begin():
        # Vínculo inactivo de uid_102 con dpto_302
        db.add(
            UsuarioDepartamento(
                usuario_id=uid_102,
                departamento_id=dpto_302,
                tipo_relacion="COPROPIETARIO",
                es_activo=False,
            )
        )
        db.add_all(
            [
                Notificacion(
                    id=notif_propia_activa,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_102,
                    usuario_id=uid_102,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_PAGO_CONCILIADO",
                    plantilla="NOTIF_PAGO_CONCILIADO",
                    origen_tipo="COMPROBANTE",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"N:{notif_propia_activa}",
                    canal="EMAIL",
                    destinatario="residente102@villabonita3.pe",
                    asunto="Pago conciliado 102",
                    cuerpo="Su pago fue aprobado",
                    contexto={"dpto": "102"},
                    estado="ENTREGADO",
                    intentos=1,
                    transporte_simulado=True,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
                Notificacion(
                    id=notif_propia_inactiva,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_302,
                    usuario_id=uid_102,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_EMISION_CUOTA",
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"N:{notif_propia_inactiva}",
                    canal="EMAIL",
                    destinatario="residente102@villabonita3.pe",
                    asunto="Cuota 302 vínculo inactivo",
                    cuerpo="No debe mostrarse",
                    contexto={"dpto": "302"},
                    estado="ENTREGADO",
                    intentos=1,
                    transporte_simulado=True,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
                Notificacion(
                    id=notif_otro_residente_misma_unidad,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_102,
                    usuario_id=uid_504,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_RESERVA_CONFIRMADA",
                    plantilla="NOTIF_RESERVA_CONFIRMADA",
                    origen_tipo="RESERVA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"N:{notif_otro_residente_misma_unidad}",
                    canal="EMAIL",
                    destinatario="inquilino504@villabonita3.pe",
                    asunto="Reserva de otro usuario",
                    cuerpo="Privado de otro usuario",
                    contexto={"dpto": "102"},
                    estado="ENTREGADO",
                    intentos=1,
                    transporte_simulado=True,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
                Notificacion(
                    id=notif_otro_residente_otra_unidad,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_504,
                    usuario_id=uid_504,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_EMISION_CUOTA",
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"N:{notif_otro_residente_otra_unidad}",
                    canal="EMAIL",
                    destinatario="inquilino504@villabonita3.pe",
                    asunto="Cuota 504",
                    cuerpo="Privado 504",
                    contexto={"dpto": "504"},
                    estado="ENTREGADO",
                    intentos=1,
                    transporte_simulado=True,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
            ]
        )

    res = await client.get("/api/v1/notificaciones/mis-notificaciones", headers=headers_res_102)
    assert res.status_code == 200, res.text
    propias = res.json()
    assert [n["id"] for n in propias] == [str(notif_propia_activa)]

    # Filtrar por unidad ajena o unidad con vínculo inactivo responde 403
    for dpto_no_autorizado in (dpto_504, dpto_302):
        res_ajeno = await client.get(
            "/api/v1/notificaciones/mis-notificaciones",
            headers=headers_res_102,
            params={"departamento_id": str(dpto_no_autorizado)},
        )
        assert res_ajeno.status_code == 403


async def test_alertas_y_reenvio_manual_solo_en_fallido_permanente(api_notificaciones):
    client, base = api_notificaciones
    headers_junta = await _login(client, "admin@villabonita3.pe", "Admin123!")

    dpto_402 = uuid.UUID(vinculo_piloto("402", "PROPIETARIO_TITULAR")["departamento_id"])
    uid_402 = id_demo("moroso402@villabonita3.pe")
    ahora = datetime.now(UTC)

    notif_fallida_id = uuid.uuid4()
    notif_en_cola_id = uuid.uuid4()
    alerta_1_id = uuid.uuid4()
    alerta_2_id = uuid.uuid4()

    async with base.sessions() as db, db.begin():
        db.add_all(
            [
                Notificacion(
                    id=notif_fallida_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_402,
                    usuario_id=uid_402,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_EMISION_CUOTA",
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"F:{notif_fallida_id}",
                    canal="EMAIL",
                    destinatario="erroneo402@villabonita3.pe",
                    asunto="Aviso de cuota",
                    cuerpo="Cuerpo de cuota",
                    contexto={"dpto": "402"},
                    estado="FALLIDO_PERMANENTE",
                    intentos=4,
                    error_codigo="550",
                    error_mensaje="[550] User unknown",
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
                Notificacion(
                    id=notif_en_cola_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    departamento_id=dpto_402,
                    usuario_id=uid_402,
                    evento_id=uuid.uuid4(),
                    tipo_evento="NOTIF_EMISION_CUOTA",
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=uuid.uuid4(),
                    clave_deduplicacion=f"C:{notif_en_cola_id}",
                    canal="EMAIL",
                    destinatario="moroso402@villabonita3.pe",
                    asunto="Aviso en cola",
                    cuerpo="Cuerpo en cola",
                    contexto={"dpto": "402"},
                    estado="EN_COLA",
                    intentos=0,
                    creado_en=ahora,
                    actualizado_en=ahora,
                ),
            ]
        )
        await db.flush()
        db.add_all(
            [
                AlertaAdministrativa(
                    id=alerta_1_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    notificacion_id=notif_fallida_id,
                    tipo="NOTIFICACION_FALLIDA",
                    severidad="BAJA",
                    mensaje="El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto.",
                    creado_en=ahora,
                ),
                AlertaAdministrativa(
                    id=alerta_2_id,
                    condominio_id=CONDOMINIO_PILOTO_ID,
                    notificacion_id=notif_en_cola_id,
                    tipo="NOTIFICACION_FALLIDA",
                    severidad="BAJA",
                    mensaje="Alerta administrativa de prueba para atención directa.",
                    creado_en=ahora,
                ),
            ]
        )

    # 1. Listar alertas abiertas
    res_alertas = await client.get("/api/v1/notificaciones/alertas", headers=headers_junta)
    assert res_alertas.status_code == 200
    assert {a["id"] for a in res_alertas.json()} == {str(alerta_1_id), str(alerta_2_id)}

    # 2. Rechazo 409 al intentar reenviar una notificación que NO está en FALLIDO_PERMANENTE
    res_409 = await client.post(
        f"/api/v1/notificaciones/reenviar/{notif_en_cola_id}",
        headers=headers_junta,
        json={"nuevo_destinatario": "otro@villabonita3.pe"},
    )
    assert res_409.status_code == 409

    # 3. Reenvío manual exitoso sobre FALLIDO_PERMANENTE -> pasa a EN_COLA, intentos=0, ciclo=2 y atiende su alerta
    res_reenvio = await client.post(
        f"/api/v1/notificaciones/reenviar/{notif_fallida_id}",
        headers=headers_junta,
        json={"nuevo_destinatario": "corregido402@villabonita3.pe"},
    )
    assert res_reenvio.status_code == 200, res_reenvio.text
    reenviada = res_reenvio.json()
    assert reenviada["estado"] == "EN_COLA"
    assert reenviada["intentos"] == 0
    assert reenviada["ciclo"] == 2
    assert reenviada["destinatario"] == "corregido402@villabonita3.pe"
    assert reenviada["error_mensaje"] is None

    # 4. Atender manualmente la segunda alerta
    res_atender = await client.post(
        f"/api/v1/notificaciones/alertas/{alerta_2_id}/atender",
        headers=headers_junta,
    )
    assert res_atender.status_code == 200
    assert res_atender.json()["atendida_en"] is not None

    # 5. Ya no quedan alertas abiertas en nueva consulta
    res_abiertas = await client.get("/api/v1/notificaciones/alertas", headers=headers_junta)
    assert res_abiertas.status_code == 200
    assert res_abiertas.json() == []


async def test_reenvio_manual_incrementa_ciclo_y_conserva_intentos_del_ciclo_anterior(
    api_notificaciones,
):
    client, base = api_notificaciones
    headers_junta = await _login(client, "admin@villabonita3.pe", "Admin123!")

    dpto_402 = uuid.UUID(vinculo_piloto("402", "PROPIETARIO_TITULAR")["departamento_id"])
    uid_402 = id_demo("moroso402@villabonita3.pe")
    ahora = datetime.now(UTC)
    notif_id = uuid.uuid4()

    async with base.sessions() as db, db.begin():
        db.add(
            Notificacion(
                id=notif_id,
                condominio_id=CONDOMINIO_PILOTO_ID,
                departamento_id=dpto_402,
                usuario_id=uid_402,
                evento_id=uuid.uuid4(),
                tipo_evento="NOTIF_EMISION_CUOTA",
                plantilla="NOTIF_EMISION_CUOTA",
                origen_tipo="CUOTA",
                origen_id=uuid.uuid4(),
                clave_deduplicacion=f"CICLO:{notif_id}",
                canal="EMAIL",
                destinatario="rebote402@villabonita3.pe",
                asunto="Cuota vencida",
                cuerpo="Detalle de cuota",
                contexto={"dpto": "402"},
                estado="FALLIDO_PERMANENTE",
                intentos=2,
                ciclo=1,
                error_codigo="550",
                error_mensaje="[550] Buzón inexistente",
                creado_en=ahora,
                actualizado_en=ahora,
            )
        )
        await db.flush()
        db.add_all(
            [
                NotificacionIntento(
                    notificacion_id=notif_id,
                    ciclo=1,
                    numero=1,
                    worker_id="worker-1",
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    resultado="FALLO_TEMPORAL",
                    codigo="421",
                    detalle="Timeout temporal",
                    iniciado_en=ahora,
                    finalizado_en=ahora,
                ),
                NotificacionIntento(
                    notificacion_id=notif_id,
                    ciclo=1,
                    numero=2,
                    worker_id="worker-1",
                    transporte="SIMULADO",
                    transporte_simulado=True,
                    resultado="FALLO_DEFINITIVO",
                    codigo="550",
                    detalle="Buzón inexistente",
                    iniciado_en=ahora,
                    finalizado_en=ahora,
                ),
            ]
        )

    res_reenvio = await client.post(
        f"/api/v1/notificaciones/reenviar/{notif_id}",
        headers=headers_junta,
        json={"nuevo_destinatario": "corregido402@villabonita3.pe"},
    )
    assert res_reenvio.status_code == 200, res_reenvio.text
    reenviada = res_reenvio.json()
    assert reenviada["ciclo"] == 2
    assert reenviada["intentos"] == 0
    assert reenviada["estado"] == "EN_COLA"

    res_detalle = await client.get(
        f"/api/v1/notificaciones/logs/{notif_id}",
        headers=headers_junta,
    )
    assert res_detalle.status_code == 200, res_detalle.text
    detalle = res_detalle.json()
    assert detalle["ciclo"] == 2
    assert detalle["intentos"] == 0
    assert len(detalle["historial_intentos"]) == 2
    assert [(i["ciclo"], i["numero"], i["resultado"]) for i in detalle["historial_intentos"]] == [
        (1, 1, "FALLO_TEMPORAL"),
        (1, 2, "FALLO_DEFINITIVO"),
    ]


async def test_autorizacion_auditor_solo_lectura_y_condominio_cruzado(api_notificaciones):
    client, base = api_notificaciones
    headers_auditor = await _login(client, "auditor@villabonita3.pe", "Auditor123!")
    headers_residente = await _login(client, "residente102@villabonita3.pe", "Residente123!")

    otro_cid = uuid.uuid4()
    notif_id = uuid.uuid4()
    alerta_id = uuid.uuid4()
    ahora = datetime.now(UTC)

    async with base.sessions() as db, db.begin():
        db.add(
            Condominio(
                id=otro_cid,
                nombre="Condominio Ajeno",
                direccion="Av. Ajena 999",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=0,
                dia_vencimiento=20,
                dias_gracia=0,
                activo=True,
            )
        )
        await db.flush()
        db.add(
            Notificacion(
                id=notif_id,
                condominio_id=otro_cid,
                evento_id=uuid.uuid4(),
                tipo_evento="NOTIF_COMUNICADO_GENERAL",
                plantilla="NOTIF_COMUNICADO_GENERAL",
                origen_tipo="COMUNICADO",
                origen_id=uuid.uuid4(),
                clave_deduplicacion=f"OTRO:{notif_id}",
                canal="EMAIL",
                destinatario="ajeno@condominio.pe",
                asunto="Ajeno",
                cuerpo="Cuerpo ajeno",
                contexto={},
                estado="FALLIDO_PERMANENTE",
                intentos=4,
                creado_en=ahora,
                actualizado_en=ahora,
            )
        )
        await db.flush()
        db.add(
            AlertaAdministrativa(
                id=alerta_id,
                condominio_id=otro_cid,
                notificacion_id=notif_id,
                tipo="NOTIFICACION_FALLIDA",
                severidad="BAJA",
                mensaje="Alerta ajena",
                creado_en=ahora,
            )
        )

    # AUDITOR: lectura permitida en su propio condominio, escritura 403
    assert (
        await client.get("/api/v1/notificaciones/logs", headers=headers_auditor)
    ).status_code == 200
    assert (
        await client.get("/api/v1/notificaciones/alertas", headers=headers_auditor)
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/notificaciones/comunicado-masivo",
            headers=headers_auditor,
            json={
                "condominio_id": base.cid,
                "titulo": "Intento auditor",
                "mensaje": "El auditor no puede emitir comunicados masivos.",
            },
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/notificaciones/reenviar/{notif_id}",
            headers=headers_auditor,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/notificaciones/alertas/{alerta_id}/atender",
            headers=headers_auditor,
        )
    ).status_code == 403

    # RESIDENTE: no puede leer bitácora administrativa ni alertas ni emitir comunicados
    assert (
        await client.get("/api/v1/notificaciones/logs", headers=headers_residente)
    ).status_code == 403
    assert (
        await client.get("/api/v1/notificaciones/alertas", headers=headers_residente)
    ).status_code == 403

    # Condominio cruzado: ADMIN_JUNTA de Villa Bonita 3 no puede operar ni leer otro_cid
    headers_junta = await _login(client, "admin@villabonita3.pe", "Admin123!")
    assert (
        await client.get(
            "/api/v1/notificaciones/logs",
            headers=headers_junta,
            params={"condominio_id": str(otro_cid)},
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/notificaciones/logs/{notif_id}",
            headers=headers_junta,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/notificaciones/reenviar/{notif_id}",
            headers=headers_junta,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/notificaciones/alertas/{alerta_id}/atender",
            headers=headers_junta,
        )
    ).status_code == 403

    # Ningún comunicado fue creado por intentos denegados
    async with base.sessions() as db:
        total = await db.scalar(
            select(func.count())
            .select_from(Notificacion)
            .where(Notificacion.condominio_id == CONDOMINIO_PILOTO_ID)
        )
        assert total == 0
    assert create_access_token is not None
