from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.condominios.condiciones_pago import (
    CondicionesPagoRequest,
    CondicionesPagoService,
    fotografiar_politica,
    gracia_efectiva,
)
from src.shared.fechas import fecha_lima


@pytest.mark.parametrize("override,activo,esperado", [(None, True, 2), (0, True, 0), (5, True, 5), (5, False, 2)])
def test_herencia_y_override(override, activo, esperado):
    vinculo = SimpleNamespace(es_activo=activo, dias_gracia_override=override)
    assert gracia_efectiva(2, vinculo) == esperado
    assert gracia_efectiva(2, None) == 2


@pytest.mark.parametrize("dias", [-1, 31, 1.5, True, "2"])
def test_gracia_solo_entera_en_rango(dias):
    with pytest.raises(ValidationError):
        CondicionesPagoRequest(vinculo_responsable_id=uuid4(), dias_gracia_override=dias,
                               version_esperada=1, motivo="Acta")


def test_sin_responsable_hereda_y_motivo_obligatorio():
    for cambios in ({"dias_gracia_override": 2}, {"motivo": "  "}):
        with pytest.raises(ValidationError):
            CondicionesPagoRequest(**({"vinculo_responsable_id": None, "dias_gracia_override": None,
                                       "version_esperada": 1, "motivo": "Acta"} | cambios))


def test_snapshot_no_cambia_con_configuracion_vigente():
    condominio = SimpleNamespace(politica_version=1, regla_mora_tipo="MONTO_DIARIO", monto_mora_diario=Decimal("1.00"),
                                 monto_mora_fijo=None, tasa_mora_porcentaje=None, dias_gracia=2)
    vinculo = SimpleNamespace(id=uuid4(), es_activo=True, dias_gracia_override=0)
    snapshot = fotografiar_politica(condominio, vinculo)
    condominio.monto_mora_diario = Decimal("5.00")
    vinculo.dias_gracia_override = 10
    assert snapshot["monto_diario"] == "1.00" and snapshot["dias_gracia"] == 0
    assert snapshot["zona_horaria"] == "America/Lima"


def test_frontera_lima_no_utc():
    # 11 de octubre UTC todavía es 10 de octubre en Lima.
    instante = datetime(2026, 10, 11, 2, tzinfo=UTC)
    with patch("src.shared.fechas.datetime") as reloj:
        reloj.now.side_effect = lambda zona: instante.astimezone(zona)
        assert fecha_lima().isoformat() == "2026-10-10"


@pytest.mark.asyncio
async def test_designacion_auditada_noop_y_version_obsoleta():
    did, vid = uuid4(), uuid4()
    depto = SimpleNamespace(responsable_pago_id=None, condiciones_pago_version=1)
    condominio = SimpleNamespace(id=uuid4(), dias_gracia=2)
    vinculo = SimpleNamespace(id=vid, es_activo=True, dias_gracia_override=None)
    session = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    service = CondicionesPagoService(session)
    service.repo = MagicMock()
    service.repo.departamento = AsyncMock(return_value=(depto, condominio))
    service.repo.auditar = AsyncMock()
    service._vinculo = AsyncMock(side_effect=[None, vinculo])
    actor = {"rol": "ADMIN_JUNTA", "condominio_id": str(condominio.id)}
    req = CondicionesPagoRequest(vinculo_responsable_id=vid, dias_gracia_override=0, version_esperada=1, motivo="Acta")
    resultado = await service.procesar(did, actor, req)
    assert resultado.dias_gracia_efectivos == 0 and resultado.version == 2
    assert depto.responsable_pago_id == vid and vinculo.dias_gracia_override == 0
    service.repo.auditar.assert_awaited_once()
    service._vinculo = AsyncMock(return_value=vinculo)
    with pytest.raises(APIError) as exc:
        await service.procesar(did, actor, req)
    assert exc.value.status_code == 409
    await service.procesar(did, actor, req.model_copy(update={"version_esperada": 2}))
    service.repo.auditar.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_permite_vinculo_ajeno_o_inactivo():
    session = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    service = CondicionesPagoService(session)
    service.repo.departamento = AsyncMock(return_value=(SimpleNamespace(responsable_pago_id=None, condiciones_pago_version=1), SimpleNamespace(id=uuid4(), dias_gracia=0)))
    service.repo.auditar = AsyncMock()
    service._vinculo = AsyncMock(return_value=None)
    req = CondicionesPagoRequest(vinculo_responsable_id=uuid4(), dias_gracia_override=0, version_esperada=1, motivo="Acta")
    with pytest.raises(APIError) as exc:
        await service.procesar(uuid4(), {"rol": "SUPERADMIN"}, req)
    assert exc.value.status_code == 422
    service.repo.auditar.assert_not_awaited()


@pytest.mark.asyncio
async def test_revocacion_retira_responsable_sin_reactivarlo():
    from src.modules.usuarios.service import UsuariosService

    cid, uid, did, vid = uuid4(), uuid4(), uuid4(), uuid4()
    usuario = SimpleNamespace(auth_revision=1)
    depto = SimpleNamespace(activo=True, responsable_pago_id=vid, condiciones_pago_version=1)
    vinculo = SimpleNamespace(id=vid, es_activo=True, tipo_relacion="INQUILINO")
    repo = MagicMock()
    repo.por_id = AsyncMock(return_value=usuario)
    repo.condominios_usuario = AsyncMock(return_value=[cid])
    repo.bloquear_contextos = AsyncMock()
    repo.departamento = AsyncMock(return_value=(depto, object()))
    repo.vinculo = AsyncMock(return_value=vinculo)
    repo.hay_otro_titular = AsyncMock(return_value=True)
    repo.agregar = AsyncMock()
    repo.confirmar = AsyncMock()
    repo.representar_vinculo.side_effect = lambda v, *_: SimpleNamespace(
        model_dump=lambda **_: {"es_activo": v.es_activo}
    )
    service = UsuariosService(repo)
    service._autorizar = AsyncMock()
    service._asignacion_para_vinculo = AsyncMock()
    service._auditar = AsyncMock()
    await service.gestionar_vinculo(cid, uid, did, None, {})
    assert depto.responsable_pago_id is None and depto.condiciones_pago_version == 2
    assert not vinculo.es_activo
    service._auditar.assert_awaited_once()
    await service.gestionar_vinculo(cid, uid, did, "INQUILINO", {})
    assert vinculo.es_activo and depto.responsable_pago_id is None
