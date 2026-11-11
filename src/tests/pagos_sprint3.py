"""Datos sintéticos y reloj fijo de CON-25–28; no accede a bases operativas."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest_asyncio

from src.core.config import settings
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.tests.integration.test_pagos_db import imagen, login
from src.tests.pagos_db import did

HOY = date(2026, 10, 20)


class RelojPago(datetime):
    @classmethod
    def now(cls, tz=None):
        valor = datetime(2026, 10, 20, 15, tzinfo=UTC)
        return valor.astimezone(tz) if tz else valor.replace(tzinfo=None)


def fijar_reloj(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "VOUCHERS_DIR", str(tmp_path / "vouchers"))
    monkeypatch.setattr("src.modules.pagos.persistencia.fecha_lima", lambda: HOY)
    monkeypatch.setattr("src.modules.pagos.solvencia.fecha_lima", lambda: HOY)
    monkeypatch.setattr("src.modules.cuotas.estado_cuenta.fecha_lima", lambda: HOY)
    monkeypatch.setattr("src.modules.pagos.persistencia.datetime", RelojPago)
    monkeypatch.setattr("src.modules.pagos.models.datetime", RelojPago)


async def preparar(base, *, diaria=False, vencimiento=date(2026, 10, 10)):
    # La misma configuración de la fábrica productiva, sin modificar fixtures ajenas.
    base.sessions.configure(autoflush=False)
    async with base.sessions() as db, db.begin():
        depto = await db.get(Departamento, did("102"))
        depto.saldo_a_favor = Decimal("0.00")
        cuota = CuotaMantenimiento(
            id=uuid4(),
            departamento_id=depto.id,
            periodo="2026-10",
            fecha_emision=date(2026, 10, 1),
            fecha_vencimiento=vencimiento,
            monto_ordinario=Decimal("100.00"),
            monto_total_exigible=Decimal("100.00"),
            monto_pagado=Decimal("0.00"),
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
        db.add(cuota)
        return cuota.id


async def reportar(client, headers, monto="100.00", fecha="2026-10-10"):
    r = await client.post(
        "/api/v1/pagos/reportar",
        headers=headers,
        data={
            "departamento_id": str(did("102")),
            "banco": "BCP",
            "numero_operacion": uuid4().hex,
            "fecha_operacion": fecha,
            "monto": monto,
        },
        files={"archivo_voucher": ("sprint3.png", imagen(), "image/png")},
    )
    assert r.status_code == 202, r.text
    return r.json()["comprobante_id"]


async def revisar(client, junta, pid, decision="APROBADO", **campos):
    return await client.post(
        f"/api/v1/pagos/{pid}/conciliar",
        headers=junta,
        json={"decision": decision, **campos},
    )


@pytest_asyncio.fixture
async def sistema(api_usuarios, monkeypatch, tmp_path, request):
    client, base = api_usuarios
    fijar_reloj(monkeypatch, tmp_path)
    cuota_id = await preparar(base, **getattr(request, "param", {}))
    residente = await login(client, "residente102", "Residente123!")
    junta = await login(client, "admin", "Admin123!")
    return client, base, cuota_id, residente, junta
