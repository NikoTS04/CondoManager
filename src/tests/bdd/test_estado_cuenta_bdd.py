"""CON-14: escenarios de aceptación sobre PostgreSQL y API real."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from pytest_bdd import given, scenarios, then, when

from src.core.config import settings
from src.main import app
from src.modules.pagos.worker import evaluar_moras_diarias
from src.modules.usuarios.demo import id_demo
from src.tests.integration.test_alta_usuarios_db import login
from src.tests.integration.test_estado_cuenta_db import preparar_cuota, recorrido_parciales, ruta
from src.tests.integration.test_estado_cuenta_db import reloj_cuenta as reloj_cuenta
from src.tests.integration.test_mora_diaria_db import AHORA, HOY, aprobar, reportar
from src.tests.pagos_db import did

scenarios("../../../specs/02-domains/01-cuotas/features/estado_cuenta.feature")
pytestmark = pytest.mark.postgres


@pytest.fixture
def caso(db_usuarios, monkeypatch, tmp_path, reloj_cuenta):
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    monkeypatch.setattr("src.modules.pagos.persistencia.fecha_lima", lambda: HOY)
    return {"base": db_usuarios}


def ejecutar(caso, accion):
    async def run():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            return await accion(client)

    return asyncio.run(run())


@given("un departamento con un cargo de 100.00")
def cargo(caso):
    asyncio.run(preparar_cuota(caso["base"]))


@when("se aprueban abonos de 40.00 y 80.00")
def abonos(caso):
    async def accion(client):
        return await recorrido_parciales(client, caso["base"], preparar=False)

    caso["parcial"], caso["cuenta"], _ = ejecutar(caso, accion)


@then("la deuda actual es 0.00 y el saldo a favor es 20.00")
def deuda_credito(caso):
    assert caso["parcial"]["deuda_actual"] == "60.00"
    assert caso["cuenta"]["deuda_actual"] == "0.00"
    assert caso["cuenta"]["saldo_a_favor_actual"] == "20.00"


@then("el saldo neto de cierre es -20.00")
def cierre(caso):
    assert caso["cuenta"]["saldo_final"] == "-20.00"


@then("el pago en revisión no se cuenta como otro abono")
def revision(caso):
    assert caso["cuenta"]["abonos_periodo"] == "120.00"
    assert caso["cuenta"]["pagos_en_revision"][0]["monto"] == "999.99"


@given("un devengo y un pago aprobados con sus registros originales")
def devengo_y_pago(caso):
    async def accion(client):
        await preparar_cuota(caso["base"], "402", diaria=True)
        await evaluar_moras_diarias(caso["base"].sessions, HOY, AHORA)
        residente = await login(client, "moroso402@villabonita3.pe", "Moroso123!")
        junta = await login(client, "admin@villabonita3.pe", "Admin123!")
        await aprobar(client, junta, await reportar(client, residente, 12, "50.00"))
        return residente, junta

    caso["residente"], caso["junta"] = ejecutar(caso, accion)


@when("un pago retroactivo genera compensaciones de mora e imputación")
def retroactivo(caso):
    async def accion(client):
        await aprobar(
            client, caso["junta"], await reportar(client, caso["residente"], 10, "100.00")
        )
        r = await client.get(ruta(did()), headers=caso["residente"])
        assert r.status_code == 200, r.text
        return r.json()

    caso["cuenta"] = ejecutar(caso, accion)


@then("los movimientos originales y sus compensaciones permanecen consultables")
def historia(caso):
    assert {m["tipo"] for m in caso["cuenta"]["movimientos"]} >= {
        "DEVENGO_MORA",
        "AJUSTE_MORA",
        "DISTRIBUCION_PAGO",
    }


@then("el estado de cuenta concilia con la deuda y crédito persistidos sin duplicar recibos")
def concilia(caso):
    assert caso["cuenta"]["saldo_final"] == "-50.00"
    assert (
        caso["cuenta"]["deuda_actual"] == "0.00"
        and caso["cuenta"]["saldo_a_favor_actual"] == "50.00"
    )


@given("un residente con una unidad autorizada")
def unidad(caso):
    cargo(caso)


@when("consulta movimientos por rango y página")
def consulta(caso):
    async def accion(client):
        residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
        r = await client.get(ruta() + "&limite=1", headers=residente)
        assert r.status_code == 200, r.text
        repetida = await client.get(ruta() + "&limite=1", headers=residente)
        assert repetida.json()["movimientos"] == r.json()["movimientos"]
        assert (await client.get(ruta(did("504")), headers=residente)).status_code == 403
        superadmin = await login(client)
        revocar = await client.delete(
            f"/api/v1/condominios/{caso['base'].cid}/usuarios/{id_demo('residente102@villabonita3.pe')}/rol",
            headers=superadmin,
        )
        assert revocar.status_code == 200, revocar.text
        assert (await client.get(ruta(), headers=residente)).status_code == 401
        return r.json()

    caso["cuenta"] = ejecutar(caso, accion)


@then("los saldos corresponden a todo el rango y el orden es estable")
def pagina(caso):
    assert caso["cuenta"]["saldo_final"] == "100.00" and caso["cuenta"]["total_movimientos"] == 1


@then("consultar una unidad ajena o con vínculo revocado es rechazado")
def rechazo(caso):
    assert caso["cuenta"]["departamento_id"] == str(did("102"))
