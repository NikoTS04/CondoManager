"""Cálculo puro y aplicación atómica del crédito para CON-13."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from src.core.audit import AuditoriaPayload
from src.core.models_audit import AuditoriaLogORM
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.saldos.exceptions import (
    AccesoSaldoDenegadoError,
    CuotaNoAplicableError,
    DatosSaldoInvalidosError,
)
from src.modules.cuotas.saldos.models import AplicacionSaldoFavor
from src.modules.cuotas.saldos.repository import SaldoFavorRepository
from src.modules.cuotas.saldos.schemas import ResultadoSaldoFavor
from src.shared.decimal_types import redondear_moneda


def _validar_importe(valor: Decimal) -> Decimal:
    if not isinstance(valor, Decimal) or not valor.is_finite() or valor < 0:
        raise DatosSaldoInvalidosError("Los importes deben ser Decimal finitos y no negativos.")
    try:
        importe = redondear_moneda(valor)
    except InvalidOperation as exc:
        raise DatosSaldoInvalidosError("El importe excede la precisión contable.") from exc
    if importe > Decimal("9999999999.99"):
        raise DatosSaldoInvalidosError("El importe excede NUMERIC(12,2).")
    return importe


def aplicar_saldo_a_favor(monto_cuota: Decimal, saldo_disponible: Decimal) -> ResultadoSaldoFavor:
    """Amortiza sin mutar entradas ni reducir el bruto de la obligación."""
    cuota = _validar_importe(monto_cuota)
    saldo = _validar_importe(saldo_disponible)
    aplicado = min(cuota, saldo)
    pendiente = cuota - aplicado
    return ResultadoSaldoFavor(
        monto_aplicado=aplicado,
        monto_pendiente=pendiente,
        saldo_restante=saldo - aplicado,
        estado="PAGADA" if pendiente == 0 else "PENDIENTE",
    )


@dataclass(frozen=True)
class ActorSaldoFavor:
    id: str
    rol: str
    condominio_id: UUID


class SaldosFavorService:
    def __init__(self, repository: SaldoFavorRepository) -> None:
        self._repository = repository

    async def aplicar_a_cuota_emitida(
        self,
        cuota: CuotaMantenimiento,
        actor: ActorSaldoFavor,
    ) -> AplicacionSaldoFavor:
        """CON-11: cuota ya flusheada con bruto final en la misma transacción.

        No hace commit. El llamador revierte todo el lote ante cualquier fallo.
        El resultado persistido es histórico: un reintento no recalcula crédito.
        Orden de bloqueo: condominio (cadena de auditoría), departamento y cuota.
        """
        if actor.rol not in {"SISTEMA_AUTOMATICO", "ADMIN_JUNTA", "SUPERADMIN"} or not actor.id:
            raise AccesoSaldoDenegadoError("El actor no puede aplicar saldos a favor.")
        async with self._repository.unidad_de_trabajo(actor.condominio_id):
            departamento = await self._repository.bloquear_departamento(
                cuota.departamento_id, actor.condominio_id
            )
            if departamento is None:
                raise AccesoSaldoDenegadoError(
                    "El departamento no pertenece al contexto autorizado."
                )
            bloqueada = await self._repository.bloquear_cuota(cuota.id, departamento.id)
            if bloqueada is None:
                raise CuotaNoAplicableError("La cuota no existe en el departamento solicitado.")
            existente = await self._repository.obtener_aplicacion(bloqueada.id)
            if existente is not None:
                return existente
            if (
                bloqueada.estado != "EMITIDA"
                or bloqueada.monto_pagado != Decimal("0.00")
                or bloqueada.monto_descuento != Decimal("0.00")
            ):
                raise CuotaNoAplicableError(
                    "Solo se amortizan cuotas recién emitidas sin pagos ni descuentos."
                )
            saldo_previo = _validar_importe(departamento.saldo_a_favor)
            resultado = aplicar_saldo_a_favor(bloqueada.monto_total_exigible, saldo_previo)
            aplicacion = AplicacionSaldoFavor(
                id=uuid4(),
                cuota_id=bloqueada.id,
                saldo_previo=saldo_previo,
                monto_aplicado=resultado.monto_aplicado,
                monto_pendiente=resultado.monto_pendiente,
                saldo_restante=resultado.saldo_restante,
                estado_anterior=bloqueada.estado,
                estado_posterior=resultado.estado,
            )
            hash_previo = await self._repository.obtener_ultimo_hash_auditoria(actor.condominio_id)
            payload = AuditoriaPayload(
                condominio_id=str(actor.condominio_id),
                departamento_id=str(departamento.id),
                accion_ejecutada="SALDO_FAVOR_APLICADO",
                motivo="AMORTIZACION_CUOTA_RECIEN_EMITIDA",
                resultado="EXITOSO",
                actor_tipo=actor.rol,
                actor_id=actor.id,
                estado_anterior={
                    "cuota_id": str(bloqueada.id),
                    "estado_cuota": bloqueada.estado,
                    "saldo_a_favor_previo": f"{saldo_previo:.2f}",
                    "monto_pagado": "0.00",
                },
                estado_posterior={
                    "cuota_id": str(bloqueada.id),
                    "estado_cuota": resultado.estado,
                    "monto_aplicado": f"{resultado.monto_aplicado:.2f}",
                    "monto_total_exigible": f"{bloqueada.monto_total_exigible:.2f}",
                    "monto_pendiente": f"{resultado.monto_pendiente:.2f}",
                    "saldo_a_favor_restante": f"{resultado.saldo_restante:.2f}",
                },
                hash_previo=hash_previo,
            )
            auditoria = AuditoriaLogORM(
                condominio_id=actor.condominio_id,
                departamento_id=departamento.id,
                timestamp=payload.timestamp,
                accion_ejecutada=payload.accion_ejecutada,
                motivo=payload.motivo,
                resultado=payload.resultado,
                actor_tipo=actor.rol,
                actor_id=actor.id,
                estado_anterior=payload.estado_anterior,
                estado_posterior=payload.estado_posterior,
                hash_previo=hash_previo,
                hash_actual=payload.calcular_hash(),
            )
            bloqueada.monto_pagado = resultado.monto_aplicado
            bloqueada.estado = resultado.estado
            departamento.saldo_a_favor = resultado.saldo_restante
            await self._repository.guardar(bloqueada, departamento, aplicacion, auditoria)
            return aplicacion
