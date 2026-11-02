"""CON-77: dos condominios SQL, login real e intentos de acceso cruzado por HTTP."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from src.core.config import settings
from src.core.database import Base
from src.core.security import hash_password
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.reservas.areas.models import AreaComun
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_pagos_db import imagen
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
PASSWORD = "Con77Prueba123!"
ROLES = ("ADMIN_JUNTA", "AUDITOR", "RESIDENTE")


async def solicitar(client, metodo, ruta, headers, **kwargs):
    return await client.request(metodo, "/api/v1" + ruta, headers=headers, **kwargs)


async def huella(base):
    """Comparar datos, auditorías, outbox y archivos sin exponer su contenido."""
    # Los nombres proceden del metadata del proyecto, nunca de entradas HTTP.
    consultas = [
        f"SELECT '{tabla}' AS tabla, "
        f"COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '[]') AS filas "
        f'FROM "{tabla}" t'
        for tabla in sorted(Base.metadata.tables)
    ]
    async with base.sessions() as db:
        rows = (await db.execute(text(" UNION ALL ".join(consultas)))).all()
    archivos = [
        (str(p.relative_to(settings.VOUCHERS_DIR)), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(Path(settings.VOUCHERS_DIR).rglob("*"))
        if p.is_file()
    ]
    return hashlib.sha256(json.dumps([rows_as_lists(rows), archivos]).encode()).hexdigest()


def rows_as_lists(rows):
    return [list(row) for row in rows]


@pytest_asyncio.fixture
async def escenario(api_pagos):
    client, base = api_pagos
    cid, eid, unidad, area = (uuid4() for _ in range(4))
    usuarios = {rol: uuid4() for rol in ROLES}
    async with base.sessions() as db, db.begin():
        db.add(
            Condominio(
                id=cid,
                nombre="Condominio B",
                direccion="Prueba CON-77",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=0,
                dia_vencimiento=20,
                dias_gracia=0,
                activo=True,
            )
        )
        await db.flush()
        db.add(Edificio(id=eid, condominio_id=cid, nombre_bloque="Torre B", total_pisos=2))
        await db.flush()
        db.add(
            Departamento(
                id=unidad,
                edificio_id=eid,
                numero="102",
                piso=1,
                coeficiente_participacion="100.0000",
                saldo_a_favor="0.00",
                estado_financiero="AL_DIA",
                activo=True,
            )
        )
        db.add(AreaComun(id=area, condominio_id=cid, nombre="Área B", aforo_maximo=10))
        for rol, uid in usuarios.items():
            db.add(
                Usuario(
                    id=uid,
                    email=f"{rol.lower()}@con77.test",
                    nombre=rol,
                    apellido="B",
                    documento_identidad=uuid4().hex[:20],
                    password_hash=hash_password(PASSWORD),
                    esta_activo=True,
                    es_superadmin=False,
                    auth_revision=1,
                )
            )
        await db.flush()
        for rol, uid in usuarios.items():
            db.add(UsuarioRol(usuario_id=uid, condominio_id=cid, rol=rol))
        db.add(
            UsuarioDepartamento(
                usuario_id=usuarios["RESIDENTE"],
                departamento_id=unidad,
                tipo_relacion="PROPIETARIO_TITULAR",
                es_activo=True,
            )
        )

    a = {
        "ADMIN_JUNTA": await login(client, "admin@villabonita3.pe", "Admin123!"),
        "AUDITOR": await login(client, "auditor@villabonita3.pe", "Auditor123!"),
        "RESIDENTE": await login(client, "residente102@villabonita3.pe", "Residente123!"),
    }
    b = {rol: await login(client, f"{rol.lower()}@con77.test", PASSWORD) for rol in ROLES}
    superadmin = await login(client)
    concepto = await solicitar(
        client,
        "POST",
        f"/condominios/{cid}/conceptos-presupuestales",
        b["ADMIN_JUNTA"],
        json={"codigo": "CON77", "categoria": "MANTENIMIENTO_PREVENTIVO", "descripcion": "B"},
    )
    assert concepto.status_code == 201, concepto.text
    presupuesto = await solicitar(
        client,
        "POST",
        "/presupuestos",
        b["ADMIN_JUNTA"],
        json={
            "condominio_id": str(cid),
            "periodo": "2026-11",
            "moneda": "PEN",
            "fecha_vencimiento": "2026-11-20",
            "items": [
                {"concepto_id": concepto.json()["id"], "seccion": "AACC", "monto_periodo": "100.00"}
            ],
        },
    )
    assert presupuesto.status_code == 201, presupuesto.text
    pago = await solicitar(
        client,
        "POST",
        "/pagos/reportar",
        b["RESIDENTE"],
        data={
            "departamento_id": str(unidad),
            "banco": "BCP",
            "numero_operacion": "CON77",
            "fecha_operacion": "2026-10-15",
            "monto": "25.00",
        },
        files={"archivo_voucher": ("b.png", imagen(), "image/png")},
    )
    assert pago.status_code == 202, pago.text
    reserva_body = {
        "condominio_id": str(cid),
        "departamento_id": str(unidad),
        "area_id": str(area),
        "fecha_reserva": (date.today() + timedelta(days=10)).isoformat(),
        "hora_inicio": "14:00",
        "hora_fin": "16:00",
    }
    reserva = await solicitar(client, "POST", "/reservas", b["RESIDENTE"], json=reserva_body)
    assert reserva.status_code == 201, reserva.text
    comunicado = await solicitar(
        client,
        "POST",
        "/notificaciones/comunicado-masivo",
        b["ADMIN_JUNTA"],
        json={"condominio_id": str(cid), "titulo": "Aviso B", "mensaje": "Mensaje exclusivo de B"},
    )
    assert comunicado.status_code == 202, comunicado.text
    logs = await solicitar(client, "GET", "/notificaciones/logs", b["ADMIN_JUNTA"])
    assert logs.status_code == 200 and logs.json()
    yield {
        "client": client,
        "base": base,
        "cid": str(cid),
        "eid": str(eid),
        "did": str(unidad),
        "area": str(area),
        "usuarios": usuarios,
        "a": a,
        "b": b,
        "superadmin": superadmin,
        "presupuesto": presupuesto.json(),
        "pago": pago.json(),
        "reserva": reserva.json(),
        "reserva_body": reserva_body,
        "log": logs.json()[0],
    }


@pytest.mark.parametrize("rol", ROLES)
async def test_identificadores_de_otro_condominio_no_leen_ni_escriben(escenario, rol):
    s = escenario
    cid, eid, did_b = s["cid"], s["eid"], s["did"]
    pid, pago, rid = s["presupuesto"]["id"], s["pago"]["comprobante_id"], s["reserva"]["id"]
    casos = [
        ("GET", f"/cuotas/departamentos?condominio_id={cid}", {}),
        ("GET", f"/pagos/comprobantes?condominio_id={cid}", {}),
        ("GET", f"/reservas?condominio_id={cid}", {}),
        ("GET", f"/areas?condominio_id={cid}", {}),
        (
            "GET",
            f"/areas/{s['area']}/disponibilidad?fecha={s['reserva_body']['fecha_reserva']}",
            {},
        ),
        ("GET", f"/pagos/solvencia/{did_b}", {}),
        ("GET", f"/departamentos/{did_b}/condiciones-pago", {}),
        ("GET", f"/edificios/{eid}/fondos-moras", {}),
        ("GET", f"/presupuestos/{pid}/aplicaciones-moras", {}),
        ("GET", f"/presupuestos/{pid}/prorrateo", {}),
        ("GET", f"/presupuestos/{pid}/prorrateo/exportar?version=1&formato=pdf", {}),
        ("GET", f"/presupuestos/{pid}/prorrateo/exportar?version=1&formato=docx", {}),
        ("GET", f"/pagos/{pago}/voucher", {}),
        ("GET", f"/pagos/{pago}/evidencias", {}),
        ("GET", f"/pagos/{pago}/resultado", {}),
        ("GET", f"/notificaciones/logs?condominio_id={cid}", {}),
        ("GET", f"/notificaciones/alertas?condominio_id={cid}", {}),
        ("GET", f"/condominios/{cid}/conceptos-presupuestales", {}),
        ("GET", f"/condominios/{cid}/presupuestos/2026-11", {}),
        ("GET", f"/condominios/{cid}/usuarios", {}),
        ("GET", f"/condominios/{cid}/edificios", {}),
        ("GET", f"/condominios/{cid}/departamentos", {}),
        ("GET", f"/condominios/{cid}/areas", {}),
        ("GET", f"/condominios/{cid}/areas/{s['area']}", {}),
        ("GET", f"/condominios/{cid}/distribucion", {}),
        ("POST", "/reservas", {"json": s["reserva_body"]}),
        ("POST", f"/reservas/{rid}/cancelar", {"json": {"es_admin": True}}),
        ("POST", f"/pagos/{pago}/conciliar", {"json": {"decision": "APROBADO"}}),
        ("PUT", f"/departamentos/{did_b}/condiciones-pago", {"json": condiciones()}),
        (
            "POST",
            f"/presupuestos/{pid}/aplicaciones-moras",
            {
                "headers": {"Idempotency-Key": "con77"},
                "json": {
                    "version_esperada": 1,
                    "item_id": s["presupuesto"]["items"][0]["id"],
                    "edificio_id": eid,
                    "monto": "1.00",
                    "motivo": "Cruce",
                },
            },
        ),
        ("POST", f"/notificaciones/reenviar/{s['log']['id']}", {"json": {}}),
        (
            "POST",
            "/notificaciones/comunicado-masivo",
            {
                "json": {"condominio_id": cid, "titulo": "Cruce", "mensaje": "No encolar"},
            },
        ),
    ]
    antes = await huella(s["base"])
    for metodo, ruta, opciones in casos:
        headers = {**s["a"][rol], **opciones.pop("headers", {})}
        r = await solicitar(s["client"], metodo, ruta, headers, **opciones)
        assert r.status_code == 403, (rol, metodo, ruta, r.status_code, r.text)
    assert await huella(s["base"]) == antes


def condiciones(**extras):
    return {
        "vinculo_responsable_id": None,
        "dias_gracia_override": None,
        "version_esperada": 1,
        "motivo": "Verificar aislamiento",
        **extras,
    }


@pytest.mark.parametrize("rol", ROLES)
async def test_lectura_legitima_y_superadmin_separan_resultados(escenario, rol):
    s = escenario
    for headers, cid, unidad in (
        (s["a"][rol], s["base"].cid, str(did("102"))),
        (s["b"][rol], s["cid"], s["did"]),
        (s["superadmin"], s["cid"], s["did"]),
    ):
        r = await solicitar(
            s["client"], "GET", f"/cuotas/departamentos?condominio_id={cid}", headers
        )
        assert r.status_code == 200, r.text
        assert unidad in {d["id"] for d in r.json()}
        assert {d["condominio_id"] for d in r.json()} == {cid}
        if rol == "RESIDENTE" and headers != s["superadmin"]:
            assert len(r.json()) == 1 and r.json()[0]["numero"] == "102"
        for ruta in ("/pagos/comprobantes", "/reservas", "/notificaciones/logs"):
            r = await solicitar(s["client"], "GET", f"{ruta}?condominio_id={cid}", headers)
            assert r.status_code == 200, r.text
            if cid == s["base"].cid:
                assert r.json() == []
            else:
                assert r.json() and all(x["departamento_id"] == s["did"] for x in r.json())


@pytest.mark.parametrize("rol", ("SUPERADMIN", *ROLES))
async def test_condiciones_y_reportes_respetan_roles(escenario, rol):
    s = escenario
    headers = s["superadmin"] if rol == "SUPERADMIN" else s["b"][rol]
    ruta = f"/departamentos/{s['did']}/condiciones-pago"
    antes = await huella(s["base"])
    r = await solicitar(s["client"], "GET", ruta, headers)
    assert r.status_code == (403 if rol == "RESIDENTE" else 200), r.text
    cambio = await solicitar(s["client"], "PUT", ruta, headers, json=condiciones())
    assert cambio.status_code == (200 if rol in {"SUPERADMIN", "ADMIN_JUNTA"} else 403)
    # La modificación válida es un no-op; ni siquiera aumenta la versión.
    assert await huella(s["base"]) == antes
    for recurso in (
        f"/edificios/{s['eid']}/fondos-moras",
        f"/presupuestos/{s['presupuesto']['id']}/aplicaciones-moras",
        f"/presupuestos/{s['presupuesto']['id']}/prorrateo/exportar?version=1",
    ):
        r = await solicitar(s["client"], "GET", recurso, headers)
        assert r.status_code == (403 if rol == "RESIDENTE" else 200), r.text[:500]


async def test_recursos_encadenados_ajenos_no_modifican_el_contexto(escenario):
    s = escenario
    async with s["base"].sessions() as db:
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(UsuarioDepartamento.departamento_id == UUID(s["did"]))
        )
        vinculo_b = str(vinculo.id)
    antes = await huella(s["base"])
    r = await solicitar(
        s["client"],
        "PUT",
        f"/departamentos/{did('102')}/condiciones-pago",
        s["a"]["ADMIN_JUNTA"],
        json=condiciones(vinculo_responsable_id=vinculo_b, dias_gracia_override=5),
    )
    assert r.status_code == 422 and r.json()["error_code"] == "RESPONSABLE_INVALIDO"
    body = {**s["reserva_body"], "condominio_id": s["base"].cid, "departamento_id": str(did("102"))}
    r = await solicitar(s["client"], "POST", "/reservas", s["a"]["ADMIN_JUNTA"], json=body)
    assert r.status_code == 403, r.text
    assert await huella(s["base"]) == antes


async def test_revocar_rol_invalida_lecturas_financieras_y_archivos(escenario):
    s = escenario
    uid = s["usuarios"]["AUDITOR"]
    r = await solicitar(
        s["client"], "DELETE", f"/condominios/{s['cid']}/usuarios/{uid}/rol", s["superadmin"]
    )
    assert r.status_code == 200, r.text
    antes = await huella(s["base"])
    for ruta in (
        f"/departamentos/{s['did']}/condiciones-pago",
        f"/edificios/{s['eid']}/fondos-moras",
        f"/pagos/{s['pago']['comprobante_id']}/voucher",
        f"/presupuestos/{s['presupuesto']['id']}/prorrateo/exportar?version=1",
    ):
        r = await solicitar(s["client"], "GET", ruta, s["b"]["AUDITOR"])
        assert r.status_code == 401 and r.json()["error_code"] == "SESION_REVOCADA", r.text
    assert await huella(s["base"]) == antes


async def test_usuario_multicondominio_no_hereda_vinculos_del_otro_contexto(escenario):
    s = escenario
    uid = id_demo("residente102@villabonita3.pe")
    async with s["base"].sessions() as db, db.begin():
        db.add(UsuarioRol(usuario_id=uid, condominio_id=UUID(s["cid"]), rol="RESIDENTE"))
        db.add(
            UsuarioDepartamento(
                usuario_id=uid,
                departamento_id=UUID(s["did"]),
                tipo_relacion="INQUILINO",
                es_activo=True,
            )
        )
    for cid, unidad, ajena in (
        (s["base"].cid, str(did("102")), s["did"]),
        (s["cid"], s["did"], str(did("102"))),
    ):
        headers = await login(
            s["client"], "residente102@villabonita3.pe", "Residente123!", condominio_id=cid
        )
        perfil = await solicitar(s["client"], "GET", "/auth/me", headers)
        assert {v["departamento_id"] for v in perfil.json()["departamentos"]} == {unidad}
        r = await solicitar(s["client"], "GET", f"/pagos/solvencia/{ajena}", headers)
        assert r.status_code == 403, r.text


async def test_junta_modifica_condiciones_propias_y_auditor_no_muta(escenario):
    s = escenario
    async with s["base"].sessions() as db:
        vinculo = await db.scalar(
            select(UsuarioDepartamento).where(UsuarioDepartamento.departamento_id == UUID(s["did"]))
        )
        vid = str(vinculo.id)
    ruta = f"/departamentos/{s['did']}/condiciones-pago"
    cambio = condiciones(vinculo_responsable_id=vid, dias_gracia_override=5)
    r = await solicitar(s["client"], "PUT", ruta, s["b"]["ADMIN_JUNTA"], json=cambio)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2 and r.json()["dias_gracia_efectivos"] == 5
    antes = await huella(s["base"])
    pid = s["presupuesto"]["id"]
    casos = [
        ("PUT", ruta, {"json": {**cambio, "version_esperada": 2, "dias_gracia_override": 10}}),
        (
            "POST",
            f"/pagos/{s['pago']['comprobante_id']}/conciliar",
            {"json": {"decision": "APROBADO"}},
        ),
        ("POST", f"/presupuestos/{pid}/aprobar", {}),
        ("DELETE", f"/presupuestos/{pid}/aplicaciones-moras/{uuid4()}?version_esperada=1", {}),
        ("POST", f"/reservas/{s['reserva']['id']}/cancelar", {"json": {"es_admin": True}}),
        (
            "POST",
            "/notificaciones/comunicado-masivo",
            {
                "json": {
                    "condominio_id": s["cid"],
                    "titulo": "Aviso",
                    "mensaje": "No debe enviarse",
                },
            },
        ),
    ]
    for metodo, recurso, opciones in casos:
        r = await solicitar(s["client"], metodo, recurso, s["b"]["AUDITOR"], **opciones)
        assert r.status_code == 403, (recurso, r.text)
    assert await huella(s["base"]) == antes
    lectura = await solicitar(s["client"], "GET", ruta, s["b"]["AUDITOR"])
    assert lectura.status_code == 200 and lectura.json()["dias_gracia_efectivos"] == 5


async def test_reporte_aprobado_residente_sin_datos_privados_y_exportacion_ajena(escenario):
    s = escenario
    pid = s["presupuesto"]["id"]
    r = await solicitar(
        s["client"],
        "POST",
        f"/presupuestos/{pid}/aprobar?version_esperada=1",
        s["b"]["ADMIN_JUNTA"],
    )
    assert r.status_code == 200, r.text
    ruta = f"/presupuestos/{pid}/prorrateo?edificio_id={s['eid']}"
    reporte = await solicitar(s["client"], "GET", ruta, s["b"]["RESIDENTE"])
    assert reporte.status_code == 200, reporte.text
    data = reporte.json()
    assert "cuotas" not in data
    assert all("departamentos" not in e for e in data["edificios"])
    assert all("cuotas" not in a for i in data["items"] for a in i["asignaciones"])
    for formato in ("pdf", "docx"):
        ruta = f"/presupuestos/{pid}/prorrateo/exportar?version={data['version']}&edificio_id={s['eid']}&formato={formato}"
        propio = await solicitar(s["client"], "GET", ruta, s["b"]["RESIDENTE"])
        assert propio.status_code == 200, propio.text[:500]
        assert propio.headers["cache-control"] == "no-store"
        ajeno = await solicitar(s["client"], "GET", ruta, s["a"]["RESIDENTE"])
        assert ajeno.status_code == 403, ajeno.text
