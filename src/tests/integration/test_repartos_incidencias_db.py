import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.incidencias.models import ActualizacionIncidencia
from src.modules.incidencias.reparto_models import CargoIncidencia, RepartoIncidencia
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.mora_diaria import MoraDiariaService
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.demo import id_demo
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_asignacion_incidencias_db import junta, reportar_y_asignar
from src.tests.integration.test_incidencias_db import JUNTA, RUTA, residente
from src.tests.integration.test_seguimiento_incidencias_db import avance, foto
from src.tests.pagos_db import did as did_piloto

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


@pytest.fixture(autouse=True)
def evidencia_aislada(monkeypatch, tmp_path):
    from src.core.config import settings

    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)


def did():
    return did_piloto("102")


async def costo(client, base, headers, iid=None, version=2, monto="100.01"):
    if iid is None:
        iid, _ = await reportar_y_asignar(client, headers)
    respuesta = await client.post(
        f"{RUTA}/{iid}/seguimiento",
        headers=headers,
        files=avance(version, monto=monto),
    )
    assert respuesta.status_code == 201, respuesta.text
    async with base.sessions() as db:
        aid = await db.scalar(
            select(ActualizacionIncidencia.id)
            .where(ActualizacionIncidencia.incidencia_id == UUID(iid))
            .order_by(ActualizacionIncidencia.creado_en.desc())
        )
    return iid, str(aid)


async def publicar(client, headers, iid, aid, *, alcance="SELECCIONADOS", metodo="EQUITATIVA"):
    ruta = f"{RUTA}/{iid}/costos/{aid}/reparto"
    body = {
        "alcance": alcance,
        "metodo": metodo,
        "departamento_ids": [str(did())] if alcance == "SELECCIONADOS" else [],
        "concepto": "Reparación de iluminación",
        "motivo": "Gasto aprobado por Junta",
    }
    preview = await client.post(f"{ruta}/previsualizacion", headers=headers, json=body)
    assert preview.status_code == 200, preview.text
    body["huella"] = preview.json()["huella"]
    clave = {**headers, "Idempotency-Key": str(uuid4())}
    publicado = await client.post(ruta, headers=clave, json=body)
    assert publicado.status_code == 201, publicado.text
    return ruta, body, clave, publicado


async def reportar_pago(client, headers, cargos, monto, operacion=None):
    archivos = [
        (k, (None, v))
        for k, v in {
            "departamento_id": str(did()),
            "banco": "YAPE",
            "numero_operacion": operacion or str(uuid4()),
            "fecha_operacion": date.today().isoformat(),
            "monto": monto,
        }.items()
    ]
    archivos.extend(("cargos_incidencia_ids", (None, str(id))) for id in cargos)
    archivos.append(("archivo_voucher", foto()))
    return await client.post("/api/v1/pagos/reportar", headers=headers, files=archivos)


@pytest.mark.parametrize("alcance", ["TODOS", "SELECCIONADOS"])
@pytest.mark.parametrize("metodo", ["EQUITATIVA", "POR_ALICUOTA"])
async def test_publica_suma_exacta_y_repite_sin_duplicar(api_usuarios, alcance, metodo):
    client, base = api_usuarios
    headers = await junta(client)
    iid, aid = await costo(client, base, headers)
    ruta, body, clave, primero = await publicar(
        client,
        headers,
        iid,
        aid,
        alcance=alcance,
        metodo=metodo,
    )
    assert sum(
        (Decimal(p["monto"]) for p in primero.json()["participantes"]), Decimal("0")
    ) == Decimal("100.01")
    repetido = await client.post(ruta, headers=clave, json=body)
    assert repetido.status_code == 200, repetido.text
    assert repetido.json() == primero.json()
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(RepartoIncidencia)) == 1
        log = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "PUBLICACION_REPARTO_INCIDENCIA",
            )
        )
        assert log.hash_actual and log.estado_posterior["monto"] == "100.01"


async def test_rechaza_preview_obsoleto_y_residente_publicando(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, aid = await costo(client, base, headers)
    ruta = f"{RUTA}/{iid}/costos/{aid}/reparto"
    body = {
        "alcance": "SELECCIONADOS",
        "metodo": "POR_ALICUOTA",
        "departamento_ids": [str(did())],
        "concepto": "Luz",
        "motivo": "Aprobado",
    }
    preview = await client.post(f"{ruta}/previsualizacion", headers=headers, json=body)
    assert preview.status_code == 200, preview.text
    async with base.sessions() as db, db.begin():
        unidad = await db.get(Departamento, did())
        unidad.coeficiente_participacion += Decimal("0.0001")
    body["huella"] = preview.json()["huella"]
    respuesta = await client.post(
        ruta, headers={**headers, "Idempotency-Key": str(uuid4())}, json=body
    )
    assert respuesta.status_code == 409, respuesta.text
    prohibido = await client.post(
        f"{ruta}/previsualizacion",
        headers=await residente(client),
        json={k: v for k, v in body.items() if k != "huella"},
    )
    assert prohibido.status_code == 403


async def test_paga_uno_y_luego_todos_sin_tocar_cuotas(api_usuarios, monkeypatch, tmp_path):
    from src.core.config import settings

    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path))
    client, base = api_usuarios
    base.sessions.configure(autoflush=False)
    headers = await junta(client)
    rh = await residente(client)
    async with base.sessions() as db, db.begin():
        db.add(
            CuotaMantenimiento(
                departamento_id=did(),
                periodo=date.today().strftime("%Y-%m"),
                monto_ordinario=Decimal("50.00"),
                monto_extraordinario=Decimal("0.00"),
                monto_mora=Decimal("0.00"),
                monto_descuento=Decimal("0.00"),
                monto_total_exigible=Decimal("50.00"),
                monto_pagado=Decimal("0.00"),
                fecha_emision=date.today(),
                fecha_vencimiento=date.today() + timedelta(days=3),
                estado="EMITIDA",
                politica_mora_aplicada={
                    "modalidad": "MONTO_DIARIO",
                    "monto_diario": "1.00",
                    "dias_gracia": 0,
                    "zona_horaria": "America/Lima",
                },
            )
        )
    iid, aid = await costo(client, base, headers, monto="25.00")
    await publicar(client, headers, iid, aid)
    for version in (3, 4):
        _, aid = await costo(client, base, headers, iid, version, "10.00")
        await publicar(client, headers, iid, aid)
    ruta_cargos = f"/api/v1/pagos/cargos-incidencias?departamento_id={did()}"
    cargos = (await client.get(ruta_cargos, headers=rh)).json()
    assert len(cargos) == 3
    assert all("descripcion" not in c and "motivo" not in c for c in cargos)
    for elegidos in ([cargos[0]], cargos[1:]):
        monto = f"{sum(Decimal(c['pendiente']) for c in elegidos):.2f}"
        reporte = await reportar_pago(client, rh, [c["id"] for c in elegidos], monto)
        assert reporte.status_code == 202, reporte.text
        pid = reporte.json()["comprobante_id"]
        antes = (await client.get(ruta_cargos, headers=rh)).json()
        assert all(
            c["estado"] == "PENDIENTE" for c in antes if c["id"] in {e["id"] for e in elegidos}
        )
        decision = await client.post(
            f"/api/v1/pagos/{pid}/conciliar", headers=headers, json={"decision": "APROBADO"}
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["monto_imputado"] == monto
        assert decision.json()["saldo_a_favor_generado"] == "0.00"
        async with base.sessions() as db:
            log = await db.scalar(
                select(AuditoriaLogORM).where(
                    AuditoriaLogORM.accion_ejecutada == "REVISION_PAGO_APROBADO",
                    AuditoriaLogORM.estado_posterior["comprobante_id"].astext == pid,
                )
            )
            assert all(
                log.estado_anterior["cargos_incidencia"][c["id"]]["pagado"] == "0.00"
                and log.estado_posterior["cargos_incidencia"][c["id"]]["pagado"] == c["pendiente"]
                for c in elegidos
            )
        repetida = await client.post(
            f"/api/v1/pagos/{pid}/conciliar", headers=headers, json={"decision": "APROBADO"}
        )
        assert repetida.json() == decision.json()
    finales = (await client.get(ruta_cargos, headers=rh)).json()
    assert all(c["estado"] == "PAGADO" for c in finales)
    async with base.sessions() as db, db.begin():
        repo = SQLAlchemyPagosRepository(db)
        unidad = await db.get(Departamento, did())
        condominio = await db.get(Condominio, CONDOMINIO_PILOTO_ID)
        cuotas = await repo.cuotas(did(), bloquear=True)
        resultado = await MoraDiariaService(db).reconstruir(
            unidad,
            condominio,
            cuotas,
            {"sub": str(id_demo(JUNTA)), "rol": "ADMIN_JUNTA"},
            date.today(),
        )
        assert resultado is not None
        assert cuotas[0].monto_pagado == Decimal("0.00")
        assert unidad.saldo_a_favor == Decimal("0.00")
    cuenta = await client.get(f"/api/v1/cuotas/departamentos/{did()}/estado-cuenta", headers=rh)
    assert cuenta.status_code == 200, cuenta.text
    assert cuenta.json()["saldo_a_favor_actual"] == "0.00"
    assert cuenta.json()["deuda_actual"] == "50.00"
    assert len([m for m in cuenta.json()["movimientos"] if m["tipo"] == "CARGO_INCIDENCIA"]) == 3


async def test_monto_ajeno_o_total_incorrecto_no_se_reporta(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, aid = await costo(client, base, headers)
    await publicar(client, headers, iid, aid, alcance="TODOS")
    rh = await residente(client)
    async with base.sessions() as db:
        ajeno = await db.scalar(
            select(CargoIncidencia.id).where(
                CargoIncidencia.departamento_id != did(),
            )
        )
    assert (await reportar_pago(client, rh, [ajeno], "100.01")).status_code == 409
    cargos = (
        await client.get(f"/api/v1/pagos/cargos-incidencias?departamento_id={did()}", headers=rh)
    ).json()
    assert (await reportar_pago(client, rh, [cargos[0]["id"]], "100.00")).status_code == 422
    async with base.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ComprobantePago)) == 0


async def test_publicacion_concurrente_y_cargos_sin_acceso_al_ticket(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    iid, aid = await costo(client, base, headers)
    ruta, body, clave, publicado = await publicar(client, headers, iid, aid, alcance="TODOS")
    respuestas = await asyncio.gather(
        *(client.post(ruta, headers=clave, json=body) for _ in range(2))
    )
    assert all(r.status_code == 200 for r in respuestas)
    assert all(r.json()["id"] == publicado.json()["id"] for r in respuestas)
    moroso = await login(client, "moroso402@villabonita3.pe", "Moroso123!")
    consulta = await client.get(
        f"/api/v1/pagos/cargos-incidencias?departamento_id={did_piloto('402')}",
        headers=moroso,
    )
    assert consulta.status_code == 200 and len(consulta.json()) == 1
    assert consulta.json()[0]["concepto"] == "Reparación de iluminación"
    ticket = await client.get(f"{RUTA}/{iid}", headers=moroso)
    assert ticket.status_code in (403, 404)


async def test_observacion_y_rechazo_no_pagan_y_doble_aprobacion_no_duplica(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    rh = await residente(client)
    iid, aid = await costo(client, base, headers, monto="20.00")
    await publicar(client, headers, iid, aid)
    ruta = f"/api/v1/pagos/cargos-incidencias?departamento_id={did()}"
    cargo = (await client.get(ruta, headers=rh)).json()[0]
    ids = []
    for decision in ("OBSERVADO", "RECHAZADO", "APROBADO", "APROBADO"):
        reporte = await reportar_pago(client, rh, [cargo["id"]], "20.00")
        assert reporte.status_code == 202, reporte.text
        pid = reporte.json()["comprobante_id"]
        ids.append(pid)
        if decision != "APROBADO":
            respuesta = await client.post(
                f"/api/v1/pagos/{pid}/conciliar",
                headers=headers,
                json={"decision": decision, "motivo_rechazo": "Revisar evidencia"},
            )
            assert respuesta.status_code == 200, respuesta.text
            assert respuesta.json()["monto_imputado"] == "0.00"
    aprobaciones = await asyncio.gather(
        *(
            client.post(
                f"/api/v1/pagos/{pid}/conciliar", headers=headers, json={"decision": "APROBADO"}
            )
            for pid in ids[-2:]
        )
    )
    assert sorted(r.status_code for r in aprobaciones) == [200, 409]
    final = (await client.get(ruta, headers=rh)).json()[0]
    assert final["pagado"] == "20.00"


async def test_el_mismo_voucher_no_cambia_destinos(api_usuarios):
    client, base = api_usuarios
    headers = await junta(client)
    rh = await residente(client)
    iid, aid = await costo(client, base, headers, monto="20.00")
    await publicar(client, headers, iid, aid)
    _, aid = await costo(client, base, headers, iid, 3, "20.00")
    await publicar(client, headers, iid, aid)
    cargos = (
        await client.get(f"/api/v1/pagos/cargos-incidencias?departamento_id={did()}", headers=rh)
    ).json()
    reporte = await reportar_pago(client, rh, [cargos[0]["id"]], "20.00", "123456")
    repetido = await reportar_pago(client, rh, [cargos[0]["id"]], "20.00", "123456")
    cambiado = await reportar_pago(client, rh, [cargos[1]["id"]], "20.00", "123456")
    assert reporte.status_code == 202 and repetido.status_code == 200
    assert repetido.json()["comprobante_id"] == reporte.json()["comprobante_id"]
    assert cambiado.status_code == 409
