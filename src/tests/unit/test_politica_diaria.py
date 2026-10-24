from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.condominios.models import Condominio
from src.modules.condominios.schemas import ActualizarPoliticaMoraRequest, CrearCondominioRequest
from src.modules.condominios.service import actualizar_politica_mora
from src.modules.pagos.contabilidad import saldo_en_mora


def crear(**kwargs):
    return CrearCondominioRequest(nombre="Piloto", direccion="Lima", moneda="PEN", **kwargs)


def test_defaults_y_moneda_explicita():
    datos = crear()
    assert (datos.monto_mora_diario, datos.dia_vencimiento, datos.dias_gracia) == (Decimal("1.00"), 10, 0)
    with pytest.raises(ValidationError):
        CrearCondominioRequest(nombre="Piloto", direccion="Lima", moneda="USD")


@pytest.mark.parametrize("valor", ["0.00", "-1.00", "NaN", "Infinity", "1.001", 1.0, None])
def test_rechaza_importe_diario_invalido(valor):
    with pytest.raises(ValidationError):
        crear(monto_mora_diario=valor)


def test_compatibilidad_fija_y_modalidades_excluyentes():
    assert crear(regla_mora_tipo="MONTO_FIJO", monto_mora_fijo="20.00").monto_mora_diario is None
    with pytest.raises(ValidationError):
        crear(monto_mora_fijo="20.00")


def test_gracia_historica_no_cambia_con_politica_global():
    cuota = SimpleNamespace(estado="PENDIENTE", monto_total_exigible=Decimal("100.00"),
                            monto_pagado=Decimal("0.00"), fecha_vencimiento=date(2026, 10, 10),
                            dias_gracia_aplicados=0)
    assert saldo_en_mora([cuota], 30, date(2026, 10, 11)) == Decimal("100.00")
    cuota.dias_gracia_aplicados = 2
    assert saldo_en_mora([cuota], 0, date(2026, 10, 11)) == Decimal("0.00")


@pytest.mark.asyncio
async def test_edicion_version_auditoria_noop_y_conflicto():
    from datetime import UTC, datetime

    cid = uuid4()
    condominio = Condominio(id=cid, nombre="Piloto", direccion="Lima", moneda="PEN",
                           regla_mora_tipo="MONTO_FIJO", monto_mora_fijo=Decimal("20.00"),
                           monto_mora_diario=None, tasa_mora_porcentaje=None, dia_vencimiento=20,
                           dias_gracia=2, politica_version=1, activo=True, creado_en=datetime.now(UTC))
    session = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    session.scalar = AsyncMock(side_effect=[condominio, None])
    session.flush = AsyncMock()
    actor = {"sub": str(uuid4()), "rol": "ADMIN_JUNTA", "condominio_id": str(cid)}
    req = ActualizarPoliticaMoraRequest(regla_mora_tipo="MONTO_DIARIO", monto_mora_diario="2.50",
                                      dia_vencimiento=10, dias_gracia=0, version_esperada=1,
                                      motivo="Acta aprobada")
    await actualizar_politica_mora(session, cid, req, actor)
    assert condominio.monto_mora_diario == Decimal("2.50")
    assert condominio.politica_version == 2
    log = session.add.call_args.args[0]
    assert log.estado_anterior["dias_gracia"] == 2
    assert log.estado_posterior["dias_gracia"] == 0
    assert log.hash_actual and log.actor_id == actor["sub"]
    session.scalar = AsyncMock(return_value=condominio)
    with pytest.raises(APIError):
        await actualizar_politica_mora(session, cid, req, actor)
    session.add.reset_mock()
    await actualizar_politica_mora(session, cid, req.model_copy(update={"version_esperada": 2}), actor)
    session.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["AUDITOR", "RESIDENTE"])
async def test_no_permite_editar_a_roles_sin_permiso(rol):
    cid = uuid4()
    req = ActualizarPoliticaMoraRequest(regla_mora_tipo="MONTO_DIARIO", monto_mora_diario="1.00",
                                      dia_vencimiento=10, dias_gracia=0, version_esperada=1, motivo="Acta")
    with pytest.raises(Exception) as exc:
        await actualizar_politica_mora(MagicMock(), cid, req, {"rol": rol, "condominio_id": str(cid)})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_emision_diaria_bloqueada_hasta_integrar_motor():
    from src.modules.cuotas.emision import EmisionCuotasService
    from src.modules.cuotas.saldos.service import ActorSaldoFavor
    from src.modules.cuotas.schemas import EmitirLoteRequest

    cid = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=Condominio(id=cid, activo=True, regla_mora_tipo="MONTO_DIARIO"))
    service = EmisionCuotasService(session)
    with pytest.raises(APIError) as exc:
        await service._emitir(EmitirLoteRequest(condominio_id=cid, periodo="2026-10"),
                             ActorSaldoFavor(str(uuid4()), "ADMIN_JUNTA", cid))
    assert exc.value.error_code == "MOTOR_DIARIO_PENDIENTE"
    session.add.assert_not_called()
