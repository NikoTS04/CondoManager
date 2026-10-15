"""Reglas y contrato puro de CON-10, exclusivamente con Decimal."""

from datetime import timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable

from src.modules.cuotas.distribucion.exceptions import (
    AccesoDistribucionDenegadoError,
    CoeficientesInvalidosError,
    CondominioNoEncontradoError,
    DatosDistribucionInvalidosError,
    DistribucionNoEncontradaError,
    SinDepartamentosError,
)
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
from src.modules.cuotas.distribucion.repository import (
    DepartamentoDistribucion,
    SQLAlchemyDistribucionRepository,
)
from src.modules.cuotas.distribucion.schemas import (
    ConfigurarDistribucionRequest,
    MetodoDistribucion,
)
from src.modules.cuotas.distribucion.service import (
    ActorDistribucion,
    DistribucionService,
    calcular_distribucion,
)
from src.shared.decimal_types import calcular_cuota_alicuota, calcular_cuota_fija, redondear_moneda


class FakeDistribucionRepository:
    def __init__(self):
        self.condominio_id = uuid4()
        self.condominios = {self.condominio_id: object()}
        self.departamentos = {
            self.condominio_id: [
                DepartamentoDistribucion(UUID(int=1), Decimal("60.0000")),
                DepartamentoDistribucion(UUID(int=2), Decimal("40.0000")),
            ]
        }
        self.configuraciones = {}
        self.auditorias = []
        self.bloqueos = []

    async def obtener_condominio(self, condominio_id, *, bloquear=False):
        if bloquear:
            self.bloqueos.append(condominio_id)
        return self.condominios.get(condominio_id)

    async def obtener_configuracion(self, condominio_id):
        return self.configuraciones.get(condominio_id)

    async def listar_departamentos_para_distribucion(self, condominio_id):
        return self.departamentos.get(condominio_id, [])

    async def obtener_ultimo_hash_auditoria(self, condominio_id):
        registros = [a for a in self.auditorias if a.condominio_id == condominio_id]
        return registros[-1].hash_actual if registros else None

    async def guardar_cambio(self, configuracion, auditoria):
        self.configuraciones[configuracion.condominio_id] = configuracion
        self.auditorias.append(auditoria)
        return configuracion


def departamentos(*coeficientes):
    return [
        DepartamentoDistribucion(UUID(int=i), Decimal(coeficiente))
        for i, coeficiente in enumerate(coeficientes, start=1)
    ]


def test_calculo_alicuota_determinista_y_half_up():
    unidades = departamentos("50.0000", "50.0000")
    with localcontext() as contexto:
        contexto.prec = 4
        contexto.rounding = ROUND_DOWN
        resultado = calcular_distribucion(
            Decimal("100.01"), list(reversed(unidades)), MetodoDistribucion.POR_ALICUOTA
        )
    assert list(resultado) == [UUID(int=1), UUID(int=2)]
    assert list(resultado.values()) == [Decimal("50.01"), Decimal("50.01")]
    assert resultado == calcular_distribucion(
        Decimal("100.01"), unidades, MetodoDistribucion.POR_ALICUOTA
    )
    assert unidades == departamentos("50.0000", "50.0000")


def test_calculo_equitativo_no_ajusta_residuos_ni_valida_coeficientes():
    resultado = calcular_distribucion(
        Decimal("100.00"), departamentos("0", "0", "0"), MetodoDistribucion.EQUITATIVA
    )
    assert list(resultado.values()) == [Decimal("33.33")] * 3
    assert sum(resultado.values(), Decimal(0)) == Decimal("99.99")


@pytest.mark.parametrize("suma", ["99.9999", "100.0001"])
def test_rechaza_suma_inexacta(suma):
    with pytest.raises(CoeficientesInvalidosError) as error:
        calcular_distribucion(
            Decimal("100.00"),
            departamentos("50", str(Decimal(suma) - Decimal(50))),
            MetodoDistribucion.POR_ALICUOTA,
        )
    assert error.value.detalles["suma_coeficientes"] == suma


@pytest.mark.parametrize("metodo", list(MetodoDistribucion))
def test_rechaza_sin_departamentos(metodo):
    with pytest.raises(SinDepartamentosError):
        calcular_distribucion(Decimal(100), [], metodo)


@pytest.mark.parametrize(
    "presupuesto", [1.5, "100", 100, True, Decimal("NaN"), Decimal("Infinity"), Decimal(-1)]
)
def test_presupuesto_exige_decimal_finito_no_negativo(presupuesto):
    with pytest.raises(DatosDistribucionInvalidosError):
        calcular_distribucion(presupuesto, departamentos("100"), MetodoDistribucion.POR_ALICUOTA)


@pytest.mark.parametrize(
    "coeficiente",
    [
        50.0,
        "50",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal(-1),
        Decimal(101),
        Decimal("50.00001"),
    ],
)
def test_coeficiente_invalido(coeficiente):
    unidades = [DepartamentoDistribucion(uuid4(), coeficiente)]
    with pytest.raises(CoeficientesInvalidosError):
        calcular_distribucion(Decimal(100), unidades, MetodoDistribucion.POR_ALICUOTA)


def test_rechaza_coeficiente_cero_aunque_la_suma_sea_cien():
    with pytest.raises(CoeficientesInvalidosError) as error:
        calcular_distribucion(
            Decimal(100), departamentos("0.0000", "100.0000"), MetodoDistribucion.POR_ALICUOTA
        )
    assert error.value.detalles == {"departamento_id": str(UUID(int=1))}


def test_rechaza_departamentos_duplicados_y_metodo_desconocido():
    unidad = departamentos("50")[0]
    with pytest.raises(DatosDistribucionInvalidosError):
        calcular_distribucion(Decimal(100), [unidad, unidad], MetodoDistribucion.EQUITATIVA)
    with pytest.raises(DatosDistribucionInvalidosError):
        calcular_distribucion(Decimal(100), [unidad], "FIJA")


def test_utilidades_compartidas_no_aceptan_float():
    with pytest.raises(TypeError):
        redondear_moneda(1.5)
    with pytest.raises(TypeError):
        calcular_cuota_alicuota(1.5, Decimal(100))
    with pytest.raises(TypeError):
        calcular_cuota_alicuota(Decimal(100), 1.5)
    with pytest.raises(TypeError):
        calcular_cuota_fija(1.5, 2)
    with pytest.raises(TypeError):
        calcular_cuota_fija(Decimal(100), 2.0)
    assert redondear_moneda("1.005") == Decimal("1.01")
    assert redondear_moneda(1) == Decimal("1.00")


@pytest.mark.asyncio
async def test_configuracion_idempotente_y_auditoria_de_cada_cambio():
    repo = FakeDistribucionRepository()
    service = DistribucionService(repo)
    actor = ActorDistribucion(str(uuid4()), "ADMIN_JUNTA", repo.condominio_id)
    request = ConfigurarDistribucionRequest(metodo="POR_ALICUOTA")
    primero = await service.configurar(repo.condominio_id, request, actor)
    fecha = primero.actualizado_en
    segundo = await service.configurar(
        repo.condominio_id, request, ActorDistribucion("otro", "ADMIN_JUNTA", repo.condominio_id)
    )
    assert primero.id == segundo.id
    assert segundo.actualizado_por == actor.id
    assert segundo.actualizado_en == fecha
    assert len(repo.auditorias) == 1
    assert repo.bloqueos == [repo.condominio_id] * 2
    cambiado = await service.configurar(
        repo.condominio_id, ConfigurarDistribucionRequest(metodo="EQUITATIVA"), actor
    )
    assert cambiado.id == primero.id
    assert len(repo.configuraciones) == 1
    assert len(repo.auditorias) == 2
    inicial, auditoria = repo.auditorias
    assert inicial.estado_anterior == {}
    assert auditoria.estado_anterior["metodo"] == "POR_ALICUOTA"
    assert auditoria.estado_posterior["metodo"] == "EQUITATIVA"
    assert auditoria.hash_previo == inicial.hash_actual
    assert auditoria.hash_actual != inicial.hash_actual
    assert auditoria.timestamp.utcoffset() == timedelta(0)
    assert auditoria.accion_ejecutada == "DISTRIBUCION_CONFIGURADA"
    assert auditoria.motivo == "CONFIGURACION_METODO_DISTRIBUCION"
    assert auditoria.resultado == "EXITOSO"
    assert auditoria.actor_tipo == actor.rol
    assert auditoria.actor_id == actor.id
    assert auditoria.condominio_id == repo.condominio_id
    assert auditoria.departamento_id is None


@pytest.mark.asyncio
async def test_con11_revalida_departamentos_y_put_repetido_tambien():
    repo = FakeDistribucionRepository()
    service = DistribucionService(repo)
    actor = ActorDistribucion("admin", "ADMIN_JUNTA", repo.condominio_id)
    request = ConfigurarDistribucionRequest(metodo="POR_ALICUOTA")
    with pytest.raises(DistribucionNoEncontradaError):
        await service.obtener_para_emision(repo.condominio_id)
    await service.configurar(repo.condominio_id, request, actor)
    emision = await service.obtener_para_emision(repo.condominio_id)
    assert emision.metodo == MetodoDistribucion.POR_ALICUOTA
    assert emision.departamentos == tuple(repo.departamentos[repo.condominio_id])
    repo.departamentos[repo.condominio_id] = departamentos("99.9999")
    with pytest.raises(CoeficientesInvalidosError):
        await service.obtener_para_emision(repo.condominio_id)
    with pytest.raises(CoeficientesInvalidosError):
        await service.configurar(repo.condominio_id, request, actor)
    assert len(repo.auditorias) == 1


@pytest.mark.asyncio
async def test_acceso_se_valida_antes_de_consultar_y_condominio_debe_existir():
    repo = FakeDistribucionRepository()
    service = DistribucionService(repo)
    with pytest.raises(AccesoDistribucionDenegadoError):
        await service.obtener(
            repo.condominio_id, ActorDistribucion("admin", "ADMIN_JUNTA", uuid4())
        )
    with pytest.raises(CondominioNoEncontradoError):
        await service.configurar(
            uuid4(),
            ConfigurarDistribucionRequest(metodo="EQUITATIVA"),
            ActorDistribucion("super", "SUPERADMIN", None),
        )
    assert repo.configuraciones == {}
    assert repo.auditorias == []


@pytest.mark.asyncio
async def test_repositorio_sql_aisla_departamentos_y_conserva_decimal():
    sesion = Mock(spec=AsyncSession)
    coeficiente = Decimal("100.0000")
    departamento_id, condominio_id = uuid4(), uuid4()
    sesion.execute = AsyncMock(return_value=[(departamento_id, coeficiente)])
    repo = SQLAlchemyDistribucionRepository(sesion)
    resultado = await repo.listar_departamentos_para_distribucion(condominio_id)
    assert resultado == [DepartamentoDistribucion(departamento_id, coeficiente)]
    assert resultado[0].coeficiente is coeficiente
    consulta = sesion.execute.call_args.args[0]
    sql = str(consulta.compile(dialect=postgresql.dialect()))
    assert "departamentos.condominio_id =" in sql
    assert "ORDER BY departamentos.id" in sql
    assert condominio_id in consulta.compile().params.values()


@pytest.mark.asyncio
async def test_repositorio_sql_bloquea_raiz_y_consulta_configuracion_por_condominio():
    sesion = Mock(spec=AsyncSession)
    sesion.execute = AsyncMock(return_value=Mock())
    repo = SQLAlchemyDistribucionRepository(sesion)
    condominio_id = uuid4()
    await repo.obtener_condominio(condominio_id, bloquear=True)
    consulta = sesion.execute.call_args.args[0]
    sql = str(consulta.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert condominio_id in consulta.compile().params.values()
    await repo.obtener_configuracion(condominio_id)
    consulta = sesion.execute.call_args.args[0]
    assert "configuraciones_distribucion.condominio_id =" in str(consulta)
    assert condominio_id in consulta.compile().params.values()


@pytest.mark.asyncio
async def test_repositorio_guarda_configuracion_y_auditoria_sin_commit_propio():
    sesion = Mock(spec=AsyncSession)
    sesion.flush = AsyncMock()
    sesion.commit = AsyncMock()
    sesion.rollback = AsyncMock()
    repo = SQLAlchemyDistribucionRepository(sesion)
    configuracion, auditoria = Mock(), Mock()
    assert await repo.guardar_cambio(configuracion, auditoria) is configuracion
    sesion.add_all.assert_called_once_with([configuracion, auditoria])
    sesion.flush.assert_awaited_once()
    sesion.commit.assert_not_awaited()
    sesion.rollback.assert_not_awaited()
    sesion.flush.side_effect = RuntimeError("fallo de persistencia")
    with pytest.raises(RuntimeError, match="fallo de persistencia"):
        await repo.guardar_cambio(configuracion, auditoria)


def test_tabla_tiene_unicidad_fk_y_check_de_metodo():
    sql = str(
        CreateTable(ConfiguracionDistribucion.__table__).compile(dialect=postgresql.dialect())
    )
    assert "uq_distribucion_condominio UNIQUE (condominio_id)" in sql
    assert "REFERENCES condominios (id) ON DELETE RESTRICT" in sql
    assert "ck_distribucion_metodo CHECK (metodo IN ('POR_ALICUOTA', 'EQUITATIVA'))" in sql
