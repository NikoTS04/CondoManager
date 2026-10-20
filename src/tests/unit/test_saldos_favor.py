"""CON-13: cálculo, atomicidad e idempotencia con bloqueo simulado."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from importlib import import_module
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, MetaData, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

from src.modules.condominios.models import Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.saldos.exceptions import (
    AccesoSaldoDenegadoError,
    CuotaNoAplicableError,
    DatosSaldoInvalidosError,
)
from src.modules.cuotas.saldos.repository import SQLAlchemySaldoFavorRepository
from src.modules.cuotas.saldos.service import (
    ActorSaldoFavor,
    SaldosFavorService,
    aplicar_saldo_a_favor,
)
from src.modules.cuotas.schemas import EmitirLoteCuotasRequest
from src.modules.cuotas.service import CuotasService


class FakeSaldoFavorRepository:
    def __init__(self, saldo="150.00"):
        self.departamento = Departamento(
            id=uuid4(),
            edificio=Edificio(id=uuid4(), condominio_id=uuid4()),
            numero="101",
            saldo_a_favor=Decimal(saldo),
        )
        self.cuotas = {}
        self.departamentos = {self.departamento.id: self.departamento}
        self.aplicaciones = {}
        self.auditorias = []
        self.locks_condominio = {}
        self.bloqueos = []
        self.fallar = False
        self.espera = asyncio.Event()
        self.continuar = asyncio.Event()
        self.competidor_esperando = asyncio.Event()
        self.pausar = False

    @asynccontextmanager
    async def unidad_de_trabajo(self, condominio_id):
        # Simula SELECT FOR UPDATE del condominio hasta el cierre y rollback.
        lock = self.locks_condominio.setdefault(condominio_id, asyncio.Lock())
        if lock.locked():
            self.competidor_esperando.set()
        async with lock:
            self.bloqueos.append("condominio")
            departamentos = {
                id_: d.saldo_a_favor
                for id_, d in self.departamentos.items()
                if d.edificio.condominio_id == condominio_id
            }
            cuotas = {
                id_: (c.estado, c.monto_pagado)
                for id_, c in self.cuotas.items()
                if c.departamento_id in departamentos
            }
            aplicaciones = {id_: a for id_, a in self.aplicaciones.items() if id_ in cuotas}
            auditorias = [a for a in self.auditorias if a.condominio_id == condominio_id]
            try:
                yield
            except Exception:
                for id_, saldo in departamentos.items():
                    self.departamentos[id_].saldo_a_favor = saldo
                for id_, (estado, pagado) in cuotas.items():
                    self.cuotas[id_].estado = estado
                    self.cuotas[id_].monto_pagado = pagado
                    self.aplicaciones.pop(id_, None)
                self.aplicaciones.update(aplicaciones)
                self.auditorias = [
                    a for a in self.auditorias if a.condominio_id != condominio_id
                ] + auditorias
                raise

    async def bloquear_departamento(self, departamento_id, condominio_id):
        assert self.locks_condominio[condominio_id].locked()
        self.bloqueos.append("departamento")
        if self.pausar:
            self.pausar = False
            self.espera.set()
            await self.continuar.wait()
        departamento = self.departamentos.get(departamento_id)
        if departamento and departamento.edificio.condominio_id == condominio_id:
            return departamento
        return None

    async def bloquear_cuota(self, cuota_id, departamento_id):
        departamento = self.departamentos[departamento_id]
        assert self.locks_condominio[departamento.edificio.condominio_id].locked()
        self.bloqueos.append("cuota")
        cuota = self.cuotas.get(cuota_id)
        return cuota if cuota and cuota.departamento_id == departamento_id else None

    async def obtener_aplicacion(self, cuota_id):
        return self.aplicaciones.get(cuota_id)

    async def obtener_ultimo_hash_auditoria(self, condominio_id):
        assert self.locks_condominio[condominio_id].locked()
        auditorias = [a for a in self.auditorias if a.condominio_id == condominio_id]
        return auditorias[-1].hash_actual if auditorias else None

    async def guardar(self, cuota, departamento, aplicacion, auditoria):
        assert cuota.id not in self.aplicaciones
        self.aplicaciones[cuota.id] = aplicacion
        self.auditorias.append(auditoria)
        if self.fallar:
            raise RuntimeError("Fallo simulado de persistencia de auditoría")

    def crear_cuota(self, monto="100.00", periodo="2026-10", departamento=None):
        cuota = CuotaMantenimiento(
            id=uuid4(),
            departamento_id=(departamento or self.departamento).id,
            periodo=periodo,
            monto_ordinario=Decimal(monto),
            monto_total_exigible=Decimal(monto),
            monto_pagado=Decimal("0.00"),
            monto_descuento=Decimal("0.00"),
            estado="EMITIDA",
        )
        self.cuotas[cuota.id] = cuota
        return cuota

    def actor(self):
        return ActorSaldoFavor(
            "CON11_WORKER", "SISTEMA_AUTOMATICO", self.departamento.edificio.condominio_id
        )


@pytest.mark.parametrize(
    ("saldo", "aplicado", "pendiente", "restante", "estado"),
    [
        ("200.00", "150.00", "0.00", "50.00", "PAGADA"),
        ("50.00", "50.00", "100.00", "0.00", "PENDIENTE"),
        ("0.00", "0.00", "150.00", "0.00", "PENDIENTE"),
        ("150.00", "150.00", "0.00", "0.00", "PAGADA"),
    ],
)
def test_calculo_puro(saldo, aplicado, pendiente, restante, estado):
    resultado = aplicar_saldo_a_favor(Decimal("150.00"), Decimal(saldo))
    assert resultado.monto_aplicado == Decimal(aplicado)
    assert resultado.monto_pendiente == Decimal(pendiente)
    assert resultado.saldo_restante == Decimal(restante)
    assert resultado.estado == estado
    assert resultado == aplicar_saldo_a_favor(Decimal("150.00"), Decimal(saldo))


@pytest.mark.parametrize(
    "invalido",
    [
        Decimal("-0.001"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("10000000000.00"),
        "10.00",
        10,
        None,
    ],
)
@pytest.mark.parametrize("campo", ["cuota", "saldo"])
def test_rechaza_importes_invalidos(invalido, campo):
    with pytest.raises(DatosSaldoInvalidosError):
        aplicar_saldo_a_favor(
            invalido if campo == "cuota" else Decimal("100.00"),
            invalido if campo == "saldo" else Decimal("100.00"),
        )


def test_round_half_up_y_cuota_cero():
    resultado = aplicar_saldo_a_favor(Decimal("1.005"), Decimal("1.004"))
    assert resultado.monto_aplicado == Decimal("1.00")
    assert resultado.monto_pendiente == Decimal("0.01")
    cero = aplicar_saldo_a_favor(Decimal("0.00"), Decimal("5.00"))
    assert cero.estado == "PAGADA"
    assert cero.saldo_restante == Decimal("5.00")


@pytest.mark.asyncio
@pytest.mark.parametrize("saldo", ["200.00", "50.00", "0.00", "150.00"])
async def test_aplicacion_atomica_auditable_e_idempotente(saldo):
    repo = FakeSaldoFavorRepository(saldo)
    cuota = repo.crear_cuota("150.00")
    service = SaldosFavorService(repo)
    aplicacion = await service.aplicar_a_cuota_emitida(cuota, repo.actor())
    resultado = aplicar_saldo_a_favor(Decimal("150.00"), Decimal(saldo))
    assert cuota.monto_pagado == resultado.monto_aplicado
    assert cuota.monto_total_exigible == Decimal("150.00")
    assert cuota.monto_descuento == 0
    assert cuota.monto_pendiente == resultado.monto_pendiente
    assert cuota.estado == resultado.estado
    assert repo.departamento.saldo_a_favor == resultado.saldo_restante
    assert repo.bloqueos == ["condominio", "departamento", "cuota"]
    auditoria = repo.auditorias[0]
    for campo in (
        "departamento_id",
        "timestamp",
        "accion_ejecutada",
        "motivo",
        "resultado",
        "estado_anterior",
        "estado_posterior",
    ):
        assert getattr(auditoria, campo)
    assert auditoria.actor_id == "CON11_WORKER"
    assert auditoria.estado_anterior["saldo_a_favor_previo"] == saldo
    assert auditoria.estado_posterior["monto_aplicado"] == f"{resultado.monto_aplicado:.2f}"
    assert auditoria.hash_actual
    # El reintento no consume crédito recibido después, ni siquiera si aplicó cero.
    repo.departamento.saldo_a_favor += Decimal("10.00")
    saldo_reintento = repo.departamento.saldo_a_favor
    assert await service.aplicar_a_cuota_emitida(cuota, repo.actor()) is aplicacion
    assert repo.departamento.saldo_a_favor == saldo_reintento
    assert len(repo.auditorias) == len(repo.aplicaciones) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("misma_cuota", [False, True])
async def test_lock_por_condominio_serializa_cuotas_del_mismo_departamento(misma_cuota):
    repo = FakeSaldoFavorRepository()
    primera = repo.crear_cuota()
    segunda = primera if misma_cuota else repo.crear_cuota(periodo="2026-11")
    service = SaldosFavorService(repo)
    repo.pausar = True
    tarea1 = asyncio.create_task(service.aplicar_a_cuota_emitida(primera, repo.actor()))
    await repo.espera.wait()
    tarea2 = asyncio.create_task(service.aplicar_a_cuota_emitida(segunda, repo.actor()))
    await repo.competidor_esperando.wait()
    assert not tarea2.done()
    repo.continuar.set()
    resultados = await asyncio.gather(tarea1, tarea2)
    assert primera.monto_pagado == Decimal("100.00")
    if misma_cuota:
        assert resultados[0] is resultados[1]
        assert repo.departamento.saldo_a_favor == Decimal("50.00")
        assert len(repo.auditorias) == 1
    else:
        assert segunda.monto_pagado == Decimal("50.00")
        assert segunda.estado == "PENDIENTE"
        assert repo.departamento.saldo_a_favor == 0
        assert len(repo.auditorias) == 2
        assert repo.auditorias[1].hash_previo == repo.auditorias[0].hash_actual
    assert repo.bloqueos == ["condominio", "departamento", "cuota"] * 2


@pytest.mark.asyncio
async def test_lock_por_condominio_conserva_cadena_lineal_entre_departamentos():
    repo = FakeSaldoFavorRepository()
    otro = Departamento(
        id=uuid4(),
        edificio=repo.departamento.edificio,
        numero="102",
        saldo_a_favor=Decimal("200.00"),
    )
    repo.departamentos[otro.id] = otro
    primera = repo.crear_cuota()
    segunda = repo.crear_cuota(departamento=otro)
    service = SaldosFavorService(repo)
    repo.pausar = True
    tarea1 = asyncio.create_task(service.aplicar_a_cuota_emitida(primera, repo.actor()))
    await repo.espera.wait()
    tarea2 = asyncio.create_task(service.aplicar_a_cuota_emitida(segunda, repo.actor()))
    await repo.competidor_esperando.wait()
    assert not tarea2.done()
    repo.continuar.set()
    await asyncio.gather(tarea1, tarea2)
    assert len(repo.locks_condominio) == 1
    assert repo.bloqueos == ["condominio", "departamento", "cuota"] * 2
    assert repo.departamento.saldo_a_favor == Decimal("50.00")
    assert otro.saldo_a_favor == Decimal("100.00")
    assert len(repo.auditorias) == 2
    assert repo.auditorias[0].departamento_id != repo.auditorias[1].departamento_id
    assert repo.auditorias[0].hash_previo is None
    for anterior, posterior in zip(repo.auditorias, repo.auditorias[1:]):
        assert posterior.hash_previo == anterior.hash_actual


@pytest.mark.asyncio
async def test_fallo_revierte_cuota_saldo_aplicacion_y_auditoria():
    repo = FakeSaldoFavorRepository()
    cuota = repo.crear_cuota()
    repo.fallar = True
    with pytest.raises(RuntimeError):
        await SaldosFavorService(repo).aplicar_a_cuota_emitida(cuota, repo.actor())
    assert cuota.estado == "EMITIDA" and cuota.monto_pagado == 0
    assert repo.departamento.saldo_a_favor == Decimal("150.00")
    assert not repo.aplicaciones and not repo.auditorias


@pytest.mark.asyncio
async def test_rechaza_cuota_ya_pagada_sin_aplicacion_y_contexto_ajeno():
    repo = FakeSaldoFavorRepository()
    cuota = repo.crear_cuota()
    cuota.monto_pagado = Decimal("1.00")
    with pytest.raises(CuotaNoAplicableError):
        await SaldosFavorService(repo).aplicar_a_cuota_emitida(cuota, repo.actor())
    with pytest.raises(AccesoSaldoDenegadoError):
        await SaldosFavorService(repo).aplicar_a_cuota_emitida(
            cuota, ActorSaldoFavor("otro", "ADMIN_JUNTA", uuid4())
        )
    assert not repo.aplicaciones and not repo.auditorias


@pytest.mark.parametrize(
    "presupuesto, saldo, cubiertas",
    [
        ("100.00", "33.33", 2),  # Ajuste positivo: primera cuota acaba en 33.34.
        ("100.01", "33.33", 1),  # Ajuste negativo: primera cuota acaba en 33.33.
    ],
)
def test_saldo_despues_del_ajuste_conserva_total_bruto(presupuesto, saldo, cubiertas, monkeypatch):
    resultados = []
    calcular = CuotasService.calcular_emision_departamento

    def capturar(**kwargs):
        resultado = calcular(**kwargs)
        resultados.append(resultado)
        return resultado

    monkeypatch.setattr(CuotasService, "calcular_emision_departamento", staticmethod(capturar))
    departamentos = [
        {
            "id": uuid4(),
            "numero": str(i),
            "coeficiente": Decimal("33.3333"),
            "saldo_a_favor": Decimal(saldo),
        }
        for i in range(3)
    ]
    request = EmitirLoteCuotasRequest(
        condominio_id=uuid4(),
        periodo="2026-10",
        presupuesto_total=Decimal(presupuesto),
        fecha_vencimiento=date(2026, 10, 20),
    )
    response = CuotasService.emitir_lote_en_memoria(request, departamentos)
    assert response.monto_total_facturado == Decimal(presupuesto)
    assert response.cuotas_cubiertas_saldo_favor == cubiertas
    assert sum(r["monto_total_exigible"] for r in resultados) == Decimal(presupuesto)
    for resultado in resultados:
        assert resultado["monto_ordinario"] == resultado["monto_total_exigible"]
        assert 0 <= resultado["monto_pagado"] <= resultado["monto_total_exigible"]
        assert resultado["audit_log"].estado_posterior["monto_ordinario"] == str(
            resultado["monto_ordinario"]
        )


@pytest.mark.asyncio
async def test_repositorio_sql_bloquea_condominio_departamento_y_cuota():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.begin_nested.return_value = MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=False)
    )
    repo = SQLAlchemySaldoFavorRepository(session)
    departamento_id, condominio_id, cuota_id = uuid4(), uuid4(), uuid4()
    async with repo.unidad_de_trabajo(condominio_id):
        await repo.bloquear_departamento(departamento_id, condominio_id)
        await repo.bloquear_cuota(cuota_id, departamento_id)
    consultas = [llamada.args[0] for llamada in session.execute.call_args_list]
    for consulta in consultas:
        sql = str(consulta.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql
        assert consulta.get_execution_options()["populate_existing"] is True
    assert "condominios.id" in str(consultas[0])
    assert "edificios.condominio_id" in str(consultas[1])
    assert "cuotas_mantenimiento.departamento_id" in str(consultas[2])


@pytest.mark.asyncio
async def test_repositorio_exige_transaccion_externa():
    session = MagicMock()
    session.in_transaction.return_value = False
    repo = SQLAlchemySaldoFavorRepository(session)
    with pytest.raises(RuntimeError, match="transacción externa"):
        async with repo.unidad_de_trabajo(uuid4()):
            pytest.fail("No debe permitir aplicaciones fuera de la transacción de CON-11.")
    session.begin_nested.assert_not_called()


def test_migracion_no_depende_de_cuotas_conserva_unicidad_y_checks(monkeypatch):
    migracion = import_module("migrations.versions.20261014_0004_crear_aplicaciones_saldo_favor")
    crear_tabla = MagicMock()
    monkeypatch.setattr(migracion.op, "create_table", crear_tabla)
    migracion.upgrade()
    nombre, *elementos = crear_tabla.call_args.args
    assert nombre == "aplicaciones_saldo_favor"
    assert migracion.down_revision == "20261014_0003"
    tabla = Table(nombre, MetaData(), *elementos)
    cuota_id = tabla.c.cuota_id
    assert not cuota_id.nullable and not cuota_id.foreign_keys
    unico = next(e for e in elementos if isinstance(e, UniqueConstraint))
    assert unico.name == "uq_aplicacion_saldo_cuota"
    assert list(unico.columns.keys()) == ["cuota_id"]
    assert {e.name for e in elementos if isinstance(e, CheckConstraint)} == {
        "ck_aplicacion_saldo_importes",
        "ck_aplicacion_saldo_estados",
    }
