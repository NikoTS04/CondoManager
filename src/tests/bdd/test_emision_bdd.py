"""Escenarios CON-11 ejecutados contra PostgreSQL con migraciones, sin mocks de BD."""

import asyncio
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import func, select

from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox, LoteCuotas
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor
from src.modules.cuotas.saldos.service import SaldosFavorService
from src.tests.integration.test_emision_db import base_emision, emitir, preparar, verificar_lote

scenarios(
    str(Path(__file__).resolve().parents[3] / "specs/02-domains/01-cuotas/features/emision.feature")
)


@pytest.fixture
def contexto():
    with asyncio.Runner() as runner:
        base = base_emision()
        factory = runner.run(base.__aenter__())
        try:
            yield {"run": runner.run, "factory": factory}
        finally:
            runner.run(base.__aexit__(None, None, None))


@given('un presupuesto aprobado de "100.00" y tres departamentos activos equitativos')
@given("un presupuesto aprobado y departamentos con créditos")
def aprobado(contexto):
    contexto["cid"] = contexto["run"](preparar(contexto["factory"]))


@given('un departamento inactivo y un crédito de "40.00" en la primera unidad')
def credito(contexto):
    async def verificar():
        async with contexto["factory"]() as session:
            assert (await session.get(Departamento, UUID(int=1))).saldo_a_favor == Decimal("40.00")
            assert (await session.get(Departamento, UUID(int=4))).activo is False

    contexto["run"](verificar())


@given('un lote persistido para el periodo "2026-10"')
def lote(contexto):
    aprobado(contexto)
    emitir_administrador(contexto)


@given("un presupuesto en borrador para el periodo solicitado")
def borrador(contexto):
    contexto["cid"] = contexto["run"](preparar(contexto["factory"], estado="BORRADOR"))


@when('el administrador emite el periodo "2026-10"')
def emitir_administrador(contexto):
    contexto["respuesta"] = contexto["run"](emitir(contexto["factory"], contexto["cid"]))


@when("se emite nuevamente el mismo condominio y periodo")
@when("se intenta emitir el lote")
def emision_rechazada(contexto):
    with pytest.raises(APIError) as error:
        emitir_administrador(contexto)
    contexto["error"] = error.value


@when("falla la emisión después de aplicar el primer crédito")
def fallo(contexto, monkeypatch):
    original = SaldosFavorService.aplicar_a_cuota_emitida

    async def fallar(self, cuota, actor):
        await original(self, cuota, actor)
        raise RuntimeError("Fallo intermedio")

    monkeypatch.setattr(SaldosFavorService, "aplicar_a_cuota_emitida", fallar)
    with pytest.raises(RuntimeError):
        emitir_administrador(contexto)


@then('se persisten tres cuotas cuyo bruto suma "100.00"')
def total(contexto):
    respuesta = contexto["respuesta"]
    assert respuesta.total_cuotas_emitidas == 3
    assert respuesta.monto_total_facturado == Decimal("100.00")


@then("la primera cuota queda pagada conservando el crédito restante")
@then("existe un único evento de lote y una cadena de auditoría válida")
def persistencia(contexto):
    contexto["run"](verificar_lote(contexto["factory"], contexto["cid"]))


@then('se rechaza con "LOTE_YA_EMITIDO" sin consumir crédito ni duplicar eventos')
def duplicado(contexto):
    assert contexto["error"].error_code == "LOTE_YA_EMITIDO"
    persistencia(contexto)


@then("no persiste ninguna cuota, aplicación, auditoría, lote ni evento")
def sin_escrituras(contexto):
    async def verificar():
        async with contexto["factory"]() as session:
            for model in (
                CuotaMantenimiento,
                AplicacionSaldoFavor,
                AuditoriaLogORM,
                LoteCuotas,
                EventoLoteOutbox,
            ):
                assert await session.scalar(select(func.count()).select_from(model)) == 0

    contexto["run"](verificar())


@then("se conserva íntegro el saldo original")
def saldo_original(contexto):
    credito(contexto)


@then('se rechaza con "PRESUPUESTO_NO_APROBADO" sin escrituras')
def no_aprobado(contexto):
    assert contexto["error"].error_code == "PRESUPUESTO_NO_APROBADO"
    sin_escrituras(contexto)
