"""Reglas y cálculo determinista de distribución; no emite cuotas ni ajusta residuos."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from src.core.audit import AuditoriaPayload
from src.core.models_audit import AuditoriaLogORM
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
    DistribucionRepository,
)
from src.modules.cuotas.distribucion.schemas import (
    ConfigurarDistribucionRequest,
    DistribucionResponse,
    MetodoDistribucion,
)
from src.shared.decimal_types import (
    calcular_cuota_alicuota,
    calcular_cuota_fija,
    exigir_decimal_finito,
)


def cerrar_centavos(montos: dict[UUID, Decimal], total: Decimal) -> dict[UUID, Decimal]:
    """Cierre determinista sin float ni cargos negativos; requiere importes redondeados."""
    resultado = dict(montos)
    diferencia = total - sum(resultado.values(), Decimal("0.00"))
    orden = sorted(resultado, key=lambda id: (-resultado[id], id.int))
    paso = Decimal("0.01") if diferencia > 0 else Decimal("-0.01")
    while diferencia:
        for id in orden:
            if paso < 0 and resultado[id] == 0:
                continue
            resultado[id] += paso
            diferencia -= paso
            if not diferencia:
                break
    return resultado


@dataclass(frozen=True)
class ActorDistribucion:
    id: str
    rol: str
    condominio_id: UUID | None


@dataclass(frozen=True)
class DistribucionParaEmision:
    configuracion_id: UUID
    metodo: MetodoDistribucion
    departamentos: tuple[DepartamentoDistribucion, ...]


def validar_departamentos(
    departamentos: Sequence[DepartamentoDistribucion], metodo: MetodoDistribucion
) -> None:
    if metodo not in (MetodoDistribucion.POR_ALICUOTA, MetodoDistribucion.EQUITATIVA):
        raise DatosDistribucionInvalidosError("El método de distribución no es válido.")
    if not departamentos:
        raise SinDepartamentosError(
            "Debe registrar al menos un departamento para utilizar la distribución."
        )
    if any(not isinstance(d.id, UUID) for d in departamentos):
        raise DatosDistribucionInvalidosError("Los identificadores deben ser UUID.")
    if len({d.id for d in departamentos}) != len(departamentos):
        raise DatosDistribucionInvalidosError("Los departamentos no pueden repetirse.")
    if metodo == MetodoDistribucion.EQUITATIVA:
        return

    with localcontext() as contexto:
        contexto.prec = max(50, len(str(len(departamentos))) + 10)
        for departamento in departamentos:
            coeficiente = departamento.coeficiente
            if (
                not isinstance(coeficiente, Decimal)
                or not coeficiente.is_finite()
                or not Decimal(0) < coeficiente <= Decimal(100)
                or coeficiente != coeficiente.quantize(Decimal("0.0001"))
            ):
                raise CoeficientesInvalidosError(
                    "Los coeficientes deben ser Decimal finitos mayores que 0 "
                    "y menores o iguales a 100, "
                    "con un máximo de cuatro decimales.",
                    {"departamento_id": str(departamento.id)},
                )
        suma = sum((d.coeficiente for d in departamentos), Decimal("0.0000"))
    if suma != Decimal("100.0000"):
        raise CoeficientesInvalidosError(
            "Los coeficientes de todos los departamentos deben sumar exactamente 100.0000 %.",
            {"suma_coeficientes": f"{suma:.4f}", "suma_requerida": "100.0000"},
        )


def calcular_distribucion(
    presupuesto: Decimal,
    departamentos: Sequence[DepartamentoDistribucion],
    metodo: MetodoDistribucion,
) -> dict[UUID, Decimal]:
    """Contrato puro para CON-11, ordenado por UUID y redondeado con ROUND_HALF_UP.

    La suma puede diferir del presupuesto por centavos. El ajuste residual del
    lote corresponde a CON-11; aquí no se emiten cuotas ni se aplican saldos.
    """
    try:
        exigir_decimal_finito(presupuesto)
    except (TypeError, ValueError) as exc:
        raise DatosDistribucionInvalidosError(str(exc)) from exc
    if presupuesto < Decimal(0):
        raise DatosDistribucionInvalidosError("El presupuesto no puede ser negativo.")
    validar_departamentos(departamentos, metodo)
    with localcontext() as contexto:
        # No depender de la precisión global del proceso llamante.
        contexto.prec = max(
            50, len(presupuesto.as_tuple().digits) + abs(presupuesto.adjusted()) + 20
        )
        return {
            departamento.id: (
                calcular_cuota_alicuota(presupuesto, departamento.coeficiente)
                if metodo == MetodoDistribucion.POR_ALICUOTA
                else calcular_cuota_fija(presupuesto, len(departamentos))
            )
            for departamento in sorted(departamentos, key=lambda d: d.id.int)
        }


class DistribucionService:
    ROLES_LECTURA = frozenset({"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"})
    ROLES_ESCRITURA = frozenset({"SUPERADMIN", "ADMIN_JUNTA"})

    def __init__(self, repository: DistribucionRepository) -> None:
        self._repository = repository

    async def configurar(
        self,
        condominio_id: UUID,
        request: ConfigurarDistribucionRequest,
        actor: ActorDistribucion,
    ) -> ConfiguracionDistribucion:
        self._asegurar_acceso(actor, condominio_id, escritura=True)
        await self._asegurar_condominio(condominio_id, bloquear=True)
        departamentos = await self._repository.listar_departamentos_para_distribucion(condominio_id)
        validar_departamentos(departamentos, request.metodo)
        configuracion = await self._repository.obtener_configuracion(condominio_id)
        if configuracion is not None and configuracion.metodo == request.metodo.value:
            return configuracion

        anterior = self._serializar(configuracion) if configuracion is not None else {}
        if configuracion is None:
            configuracion = ConfiguracionDistribucion(id=uuid4(), condominio_id=condominio_id)
        configuracion.metodo = request.metodo.value
        configuracion.actualizado_por = actor.id
        configuracion.actualizado_en = datetime.now(UTC)
        hash_previo = await self._repository.obtener_ultimo_hash_auditoria(condominio_id)
        payload = AuditoriaPayload(
            condominio_id=str(condominio_id),
            departamento_id=None,
            accion_ejecutada="DISTRIBUCION_CONFIGURADA",
            motivo="CONFIGURACION_METODO_DISTRIBUCION",
            resultado="EXITOSO",
            actor_tipo=actor.rol,
            actor_id=actor.id,
            estado_anterior=anterior,
            estado_posterior=self._serializar(configuracion),
            hash_previo=hash_previo,
        )
        auditoria = AuditoriaLogORM(
            condominio_id=condominio_id,
            departamento_id=None,
            timestamp=payload.timestamp,
            accion_ejecutada=payload.accion_ejecutada,
            motivo=payload.motivo,
            resultado=payload.resultado,
            actor_tipo=payload.actor_tipo,
            actor_id=payload.actor_id,
            estado_anterior=payload.estado_anterior,
            estado_posterior=payload.estado_posterior,
            hash_previo=hash_previo,
            hash_actual=payload.calcular_hash(),
        )
        return await self._repository.guardar_cambio(configuracion, auditoria)

    async def obtener(
        self, condominio_id: UUID, actor: ActorDistribucion
    ) -> ConfiguracionDistribucion:
        self._asegurar_acceso(actor, condominio_id, escritura=False)
        await self._asegurar_condominio(condominio_id)
        return await self._obtener_configuracion(condominio_id)

    async def obtener_para_emision(self, condominio_id: UUID) -> DistribucionParaEmision:
        """Contrato interno de CON-11: revalida y devuelve el conjunto usado para calcular.

        El emisor debe invocarlo dentro de su transacción; no sustituye su control
        de concurrencia ni su instantánea persistente del periodo emitido.
        """
        await self._asegurar_condominio(condominio_id, bloquear=True)
        configuracion = await self._obtener_configuracion(condominio_id)
        departamentos = await self._repository.listar_departamentos_para_distribucion(condominio_id)
        metodo = MetodoDistribucion(configuracion.metodo)
        validar_departamentos(departamentos, metodo)
        return DistribucionParaEmision(configuracion.id, metodo, tuple(departamentos))

    async def _asegurar_condominio(self, condominio_id: UUID, *, bloquear: bool = False) -> None:
        if await self._repository.obtener_condominio(condominio_id, bloquear=bloquear) is None:
            raise CondominioNoEncontradoError(
                "No existe el condominio solicitado.", {"condominio_id": str(condominio_id)}
            )

    async def _obtener_configuracion(self, condominio_id: UUID) -> ConfiguracionDistribucion:
        configuracion = await self._repository.obtener_configuracion(condominio_id)
        if configuracion is None:
            raise DistribucionNoEncontradaError(
                "Debe configurar el método de distribución antes de emitir cuotas.",
                {"condominio_id": str(condominio_id)},
            )
        return configuracion

    def _asegurar_acceso(
        self, actor: ActorDistribucion, condominio_id: UUID, *, escritura: bool
    ) -> None:
        roles = self.ROLES_ESCRITURA if escritura else self.ROLES_LECTURA
        if actor.rol not in roles or (
            actor.rol != "SUPERADMIN" and actor.condominio_id != condominio_id
        ):
            raise AccesoDistribucionDenegadoError(
                "No tiene permisos para esta operación en el condominio solicitado."
            )

    @staticmethod
    def _serializar(configuracion: ConfiguracionDistribucion) -> dict[str, Any]:
        return DistribucionResponse.model_validate(configuracion).model_dump(mode="json")
