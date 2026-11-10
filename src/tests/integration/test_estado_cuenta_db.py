"""CON-14: consulta privada sobre la conciliación legacy y diaria reales."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from src.core.config import settings
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.pagos.models_mora import AjusteDevengoMora, DevengoMora
from src.modules.pagos.models_persistencia import EventoPagoOutbox
from src.modules.pagos.worker import evaluar_moras_diarias
from src.modules.usuarios.demo import id_demo
from src.tests.integration.test_alta_usuarios_db import login, otro_condominio
from src.tests.integration.test_mora_diaria_db import AHORA, HOY, aprobar
from src.tests.integration.test_mora_diaria_db import diaria as diaria
from src.tests.integration.test_mora_diaria_db import reportar as reportar_diario
from src.tests.integration.test_pagos_db import reportar
from src.tests.pagos_db import did

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]
RANGO = "desde=2026-01-01&hasta=2026-12-31"


class RegistroFijo(datetime):
    @classmethod
    def now(cls, tz=None):
        valor = datetime(2026, 10, 20, 15, tzinfo=UTC)
        return valor.astimezone(tz) if tz else valor.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def reloj_cuenta(monkeypatch):
    # Fechas de registro fijas: estas pruebas no caducan al cambiar el año real.
    monkeypatch.setattr("src.modules.pagos.persistencia.datetime", RegistroFijo)
    monkeypatch.setattr("src.modules.pagos.models.datetime", RegistroFijo)
    monkeypatch.setattr("src.modules.cuotas.estado_cuenta.fecha_lima", lambda: HOY)


def ruta(unidad=None, rango=RANGO):
    return f"/api/v1/cuotas/departamentos/{unidad or did('102')}/estado-cuenta?{rango}"


async def preparar_cuota(base, numero="102", diaria=False):
    async with base.sessions() as db, db.begin():
        d = await db.get(Departamento, did(numero))
        d.saldo_a_favor = Decimal("0.00")
        db.add(
            CuotaMantenimiento(
                id=uuid4(),
                departamento_id=d.id,
                periodo="2026-10",
                monto_ordinario=Decimal("100.00"),
                monto_extraordinario=Decimal("0.00"),
                monto_mora=Decimal("0.00"),
                monto_descuento=Decimal("0.00"),
                monto_total_exigible=Decimal("100.00"),
                monto_pagado=Decimal("0.00"),
                fecha_emision=date(2026, 10, 1),
                fecha_vencimiento=date(2026, 10, 10),
                estado="PENDIENTE",
                dias_gracia_aplicados=0,
                politica_mora_aplicada={
                    "modalidad": "MONTO_DIARIO",
                    "monto_diario": "1.00",
                    "dias_gracia": 0,
                    "zona_horaria": "America/Lima",
                    "version": 1,
                }
                if diaria
                else None,
            )
        )


async def recorrido_parciales(client, base, preparar=True):
    if preparar:
        await preparar_cuota(base)
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")

    async def pagar(monto, aprobarlo=True):
        r = await reportar(client, residente, numero="102", monto=monto)
        assert r.status_code == 202, r.text
        if aprobarlo:
            r = await client.post(
                f"/api/v1/pagos/{r.json()['comprobante_id']}/conciliar",
                headers=junta,
                json={"decision": "APROBADO"},
            )
            assert r.status_code == 200, r.text

    await pagar("40.00")
    parcial = await client.get(ruta(), headers=residente)
    assert parcial.status_code == 200, parcial.text
    await pagar("80.00")
    await pagar("999.99", False)
    final = await client.get(ruta(), headers=residente)
    assert final.status_code == 200, final.text
    return parcial.json(), final.json(), residente


@pytest_asyncio.fixture
async def sistema(api_usuarios, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    monkeypatch.setattr("src.modules.cuotas.estado_cuenta.fecha_lima", lambda: date(2026, 10, 20))
    monkeypatch.setattr("src.modules.pagos.persistencia.fecha_lima", lambda: date(2026, 10, 20))
    return api_usuarios


async def test_parcial_excedente_revision_y_contrato(sistema):
    client, base = sistema
    parcial, final, _ = await recorrido_parciales(client, base)
    assert parcial["deuda_actual"] == "60.00" and parcial["abonos_periodo"] == "40.00"
    assert final["deuda_actual"] == "0.00" and final["saldo_a_favor_actual"] == "20.00"
    assert final["saldo_final"] == "-20.00" and final["abonos_periodo"] == "120.00"
    assert final["pagos_en_revision"][0]["monto"] == "999.99"
    assert sum(m["tipo"] == "PAGO_APROBADO" for m in final["movimientos"]) == 2
    # Validación con el contrato publicado y su resolver, no solo con el modelo FastAPI.
    from jsonschema import Draft202012Validator, FormatChecker

    from src.tests.integration.test_convergencia_con72 import CONTRATOS, REGISTRY

    ref = (
        CONTRATOS / "openapi/estado-cuenta.schemas.yaml"
    ).as_uri() + "#/schemas/EstadoCuentaResponse"
    Draft202012Validator({"$ref": ref}, registry=REGISTRY, format_checker=FormatChecker()).validate(
        final
    )


async def test_paginacion_estable_y_consulta_no_modifica_finanzas(sistema):
    client, base = sistema
    _, completa, residente = await recorrido_parciales(client, base)

    async def huella():
        async with base.sessions() as db:
            d = await db.get(Departamento, did("102"))
            cuenta = await db.scalar(
                select(CuotaMantenimiento).where(CuotaMantenimiento.departamento_id == d.id)
            )
            conteos = [
                await db.scalar(select(func.count()).select_from(m))
                for m in (AuditoriaLogORM, EventoPagoOutbox, DevengoMora, AjusteDevengoMora)
            ]
            return (
                d.saldo_a_favor,
                cuenta.monto_pagado,
                cuenta.monto_total_exigible,
                *conteos,
            )

    antes = await huella()
    ids = []
    for offset in range(completa["total_movimientos"]):
        r = await client.get(ruta() + f"&limite=1&offset={offset}", headers=residente)
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "private, no-store"
        data = r.json()
        assert data["saldo_final"] == completa["saldo_final"]
        assert data["cargos_periodo"] == completa["cargos_periodo"]
        ids.append(data["movimientos"][0]["id"])
    assert ids == [m["id"] for m in completa["movimientos"]] and len(set(ids)) == len(ids)
    assert await huella() == antes


async def test_dos_condominios_uuid_distintos_y_revocacion(sistema):
    client, base = sistema
    await preparar_cuota(base)
    cid = await otro_condominio(base)
    eid, unidad = uuid4(), uuid4()
    async with base.sessions() as db, db.begin():
        db.add(Edificio(id=eid, condominio_id=cid, nombre_bloque="B", total_pisos=2))
        await db.flush()
        db.add(
            Departamento(
                id=unidad,
                edificio_id=eid,
                numero="102",
                piso=1,
                coeficiente_participacion=100,
                saldo_a_favor=0,
                estado_financiero="AL_DIA",
            )
        )
    residente = await login(client, "residente102@villabonita3.pe", "Residente123!")
    for email, password in (
        ("admin@villabonita3.pe", "Admin123!"),
        ("auditor@villabonita3.pe", "Auditor123!"),
        ("residente102@villabonita3.pe", "Residente123!"),
    ):
        headers = await login(client, email, password)
        assert (await client.get(ruta(), headers=headers)).status_code == 200
        assert (await client.get(ruta(unidad), headers=headers)).status_code == 403
    assert (await client.get(ruta(did("504")), headers=residente)).status_code == 403
    superadmin = await login(client)
    permitido = await client.get(ruta(unidad), headers=superadmin)
    assert permitido.status_code == 200 and permitido.json()["condominio_id"] == str(cid)
    assert (await client.get(ruta(uuid4()), headers=superadmin)).status_code == 404
    r = await client.delete(
        f"/api/v1/condominios/{base.cid}/usuarios/{id_demo('residente102@villabonita3.pe')}/rol",
        headers=superadmin,
    )
    assert r.status_code == 200, r.text
    assert (await client.get(ruta(), headers=residente)).status_code == 401
    assert (await client.get(ruta())).status_code == 401


@pytest.mark.parametrize(
    "query",
    [
        "desde=2026-01-01",
        "desde=2026-02-02&hasta=2026-02-01",
        "desde=2025-01-01&hasta=2026-12-31",
        "limite=201",
        "offset=-1",
    ],
)
async def test_filtros_invalidos(sistema, query):
    client, _ = sistema
    headers = await login(client, "residente102@villabonita3.pe", "Residente123!")
    assert (await client.get(ruta(rango=query), headers=headers)).status_code == 422


async def test_historial_diario_tras_retroactivo_no_suma_recibos_obsoletos(diaria):
    client, base, _ = diaria
    await evaluar_moras_diarias(base.sessions, HOY, AHORA)
    residente = await login(client, "moroso402@villabonita3.pe", "Moroso123!")
    junta = await login(client, "admin@villabonita3.pe", "Admin123!")
    posterior = await reportar_diario(client, residente, 12, "50.00")
    await aprobar(client, junta, posterior)
    anterior = await reportar_diario(client, residente, 10, "100.00")
    await aprobar(client, junta, anterior)
    r = await client.get(ruta(did()), headers=residente)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deuda_actual"] == "0.00" and data["saldo_a_favor_actual"] == "50.00"
    assert data["saldo_final"] == "-50.00"
    assert not data["base_historica_sin_fecha"]
    assert {m["tipo"] for m in data["movimientos"]} >= {
        "DEVENGO_MORA",
        "AJUSTE_MORA",
        "DISTRIBUCION_PAGO",
    }
    assert {m["comprobante_id"] for m in data["movimientos"] if m["tipo"] == "PAGO_APROBADO"} == {
        posterior,
        anterior,
    }


async def test_credito_inicial_y_consistencia_controlada(sistema):
    client, base = sistema
    await preparar_cuota(base)
    async with base.sessions() as db, db.begin():
        d = await db.get(Departamento, did("102"))
        d.saldo_a_favor = Decimal("25.00")
    headers = await login(client, "residente102@villabonita3.pe", "Residente123!")
    r = await client.get(ruta(), headers=headers)
    assert r.status_code == 200 and r.json()["credito_inicial_sin_desglose"] == "25.00"
    assert r.json()["saldo_final"] == "75.00" and r.json()["base_historica_sin_fecha"]
