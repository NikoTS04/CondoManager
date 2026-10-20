"""Reglas de aplicación del presupuesto mensual de CON-9."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.core.audit import AuditoriaPayload
from src.core.models_audit import AuditoriaLogORM
from src.modules.cuotas.presupuestos.exceptions import (
    AccesoPresupuestoDenegadoError,
    CondominioNoEncontradoError,
    DatosPresupuestoInvalidosError,
    PresupuestoNoEditableError,
    PresupuestoNoEncontradoError,
    PresupuestoPeriodoDuplicadoError,
)
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.presupuestos.repository import PresupuestoRepository
from src.modules.cuotas.presupuestos.schemas import (
    ActualizarPresupuestoRequest,
    CrearPresupuestoRequest,
    EstadoPresupuesto,
)


@dataclass(frozen=True)
class ActorPresupuesto:
    id: str
    rol: str
    condominio_id: UUID | None


class PresupuestosService:
    ROLES_LECTURA = {"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"}
    ROLES_ESCRITURA = {"SUPERADMIN", "ADMIN_JUNTA"}

    def __init__(self, repository: PresupuestoRepository) -> None:
        self._repository = repository

    async def crear(
        self,
        request: CrearPresupuestoRequest,
        actor: ActorPresupuesto,
    ) -> PresupuestoMensual:
        self._asegurar_acceso(actor, request.condominio_id, escritura=True)
        condominio = await self._repository.obtener_condominio(request.condominio_id)
        if condominio is None:
            raise CondominioNoEncontradoError(request.condominio_id)
        self._validar_moneda(request.moneda.value, condominio.moneda)

        existente = await self._repository.obtener_por_condominio_periodo(
            request.condominio_id,
            request.periodo,
        )
        if existente is not None:
            raise PresupuestoPeriodoDuplicadoError(
                "Ya existe un presupuesto para el condominio y periodo indicados."
            )

        ahora = datetime.now(UTC)
        presupuesto = PresupuestoMensual(
            id=uuid4(),
            condominio_id=request.condominio_id,
            periodo=request.periodo,
            moneda=request.moneda.value,
            monto_total=request.monto_total,
            fecha_vencimiento=request.fecha_vencimiento,
            estado=EstadoPresupuesto.BORRADOR.value,
            creado_por=actor.id,
            creado_en=ahora,
            aprobado_por=None,
            aprobado_en=None,
            actualizado_en=ahora,
        )
        auditoria = await self._crear_auditoria(
            presupuesto=presupuesto,
            actor=actor,
            accion="PRESUPUESTO_CREADO",
            motivo="REGISTRO_PRESUPUESTO_MENSUAL",
            estado_anterior={},
            estado_posterior=self._serializar(presupuesto),
        )
        return await self._repository.agregar(presupuesto, auditoria)

    async def actualizar(
        self,
        presupuesto_id: UUID,
        request: ActualizarPresupuestoRequest,
        actor: ActorPresupuesto,
    ) -> PresupuestoMensual:
        self._asegurar_rol(actor, escritura=True)
        presupuesto = await self._obtener_por_id(presupuesto_id, actor)
        self._asegurar_acceso(actor, presupuesto.condominio_id, escritura=True)
        if presupuesto.estado != EstadoPresupuesto.BORRADOR.value:
            raise PresupuestoNoEditableError(
                "Un presupuesto aprobado no puede modificarse ni aprobarse nuevamente.",
                {"presupuesto_id": str(presupuesto_id), "estado": presupuesto.estado},
            )

        condominio = await self._repository.obtener_condominio(presupuesto.condominio_id)
        if condominio is None:
            raise CondominioNoEncontradoError(presupuesto.condominio_id)
        self._validar_moneda(request.moneda.value, condominio.moneda)

        existente = await self._repository.obtener_por_condominio_periodo(
            presupuesto.condominio_id,
            request.periodo,
        )
        if existente is not None and existente.id != presupuesto.id:
            raise PresupuestoPeriodoDuplicadoError(
                "Ya existe un presupuesto para el condominio y periodo indicados."
            )

        estado_anterior = self._serializar(presupuesto)
        presupuesto.periodo = request.periodo
        presupuesto.moneda = request.moneda.value
        presupuesto.monto_total = request.monto_total
        presupuesto.fecha_vencimiento = request.fecha_vencimiento
        presupuesto.actualizado_en = datetime.now(UTC)

        auditoria = await self._crear_auditoria(
            presupuesto=presupuesto,
            actor=actor,
            accion="PRESUPUESTO_MODIFICADO",
            motivo="ACTUALIZACION_BORRADOR_PRESUPUESTO",
            estado_anterior=estado_anterior,
            estado_posterior=self._serializar(presupuesto),
        )
        return await self._repository.guardar_cambio(presupuesto, auditoria)

    async def aprobar(
        self,
        presupuesto_id: UUID,
        actor: ActorPresupuesto,
    ) -> PresupuestoMensual:
        self._asegurar_rol(actor, escritura=True)
        presupuesto = await self._obtener_por_id(presupuesto_id, actor)
        self._asegurar_acceso(actor, presupuesto.condominio_id, escritura=True)
        if presupuesto.estado != EstadoPresupuesto.BORRADOR.value:
            raise PresupuestoNoEditableError(
                "Un presupuesto aprobado no puede modificarse ni aprobarse nuevamente.",
                {"presupuesto_id": str(presupuesto_id), "estado": presupuesto.estado},
            )

        estado_anterior = self._serializar(presupuesto)
        ahora = datetime.now(UTC)
        presupuesto.estado = EstadoPresupuesto.APROBADO.value
        presupuesto.aprobado_por = actor.id
        presupuesto.aprobado_en = ahora
        presupuesto.actualizado_en = ahora

        auditoria = await self._crear_auditoria(
            presupuesto=presupuesto,
            actor=actor,
            accion="PRESUPUESTO_APROBADO",
            motivo="APROBACION_PRESUPUESTO_MENSUAL",
            estado_anterior=estado_anterior,
            estado_posterior=self._serializar(presupuesto),
        )
        return await self._repository.guardar_cambio(presupuesto, auditoria)

    async def obtener_por_periodo(
        self,
        condominio_id: UUID,
        periodo: str,
        actor: ActorPresupuesto,
    ) -> PresupuestoMensual:
        self._asegurar_acceso(actor, condominio_id, escritura=False)
        condominio = await self._repository.obtener_condominio(condominio_id)
        if condominio is None:
            raise CondominioNoEncontradoError(condominio_id)

        presupuesto = await self._repository.obtener_por_condominio_periodo(
            condominio_id,
            periodo,
        )
        if presupuesto is None:
            raise PresupuestoNoEncontradoError(
                "No existe un presupuesto para el condominio y periodo solicitados.",
                {"condominio_id": str(condominio_id), "periodo": periodo},
            )
        return presupuesto

    async def obtener_aprobado_para_emision(
        self,
        condominio_id: UUID,
        periodo: str,
    ) -> PresupuestoMensual | None:
        """Contrato interno para CON-11: nunca devuelve borradores."""

        return await self._repository.obtener_aprobado_por_periodo(condominio_id, periodo)

    async def _obtener_por_id(
        self,
        presupuesto_id: UUID,
        actor: ActorPresupuesto,
    ) -> PresupuestoMensual:
        contexto = None if actor.rol == "SUPERADMIN" else actor.condominio_id
        presupuesto = await self._repository.obtener_por_id(
            presupuesto_id,
            contexto,
            bloquear=True,
        )
        if presupuesto is None:
            raise PresupuestoNoEncontradoError(
                "No existe un presupuesto con el identificador solicitado.",
                {"presupuesto_id": str(presupuesto_id)},
            )
        return presupuesto

    def _asegurar_acceso(
        self,
        actor: ActorPresupuesto,
        condominio_id: UUID,
        *,
        escritura: bool,
    ) -> None:
        self._asegurar_rol(actor, escritura=escritura)
        if actor.rol != "SUPERADMIN" and actor.condominio_id != condominio_id:
            raise AccesoPresupuestoDenegadoError(
                "No tiene permisos sobre los presupuestos del condominio solicitado."
            )

    def _asegurar_rol(self, actor: ActorPresupuesto, *, escritura: bool) -> None:
        roles_permitidos = self.ROLES_ESCRITURA if escritura else self.ROLES_LECTURA
        if actor.rol not in roles_permitidos:
            raise AccesoPresupuestoDenegadoError(
                "No tiene permisos para realizar esta operación sobre presupuestos."
            )
        if actor.rol != "SUPERADMIN" and actor.condominio_id is None:
            raise AccesoPresupuestoDenegadoError(
                "El usuario no tiene un contexto de condominio autorizado."
            )

    @staticmethod
    def _validar_moneda(moneda_presupuesto: str, moneda_condominio: str) -> None:
        if moneda_presupuesto != moneda_condominio:
            raise DatosPresupuestoInvalidosError(
                "La moneda del presupuesto debe coincidir con la moneda del condominio.",
                {
                    "moneda_presupuesto": moneda_presupuesto,
                    "moneda_condominio": moneda_condominio,
                },
            )

    async def _crear_auditoria(
        self,
        presupuesto: PresupuestoMensual,
        actor: ActorPresupuesto,
        accion: str,
        motivo: str,
        estado_anterior: dict[str, Any],
        estado_posterior: dict[str, Any],
    ) -> AuditoriaLogORM:
        hash_previo = await self._repository.obtener_ultimo_hash_auditoria(
            presupuesto.condominio_id
        )
        payload = AuditoriaPayload(
            condominio_id=str(presupuesto.condominio_id),
            departamento_id=None,
            accion_ejecutada=accion,
            motivo=motivo,
            resultado="EXITOSO",
            actor_tipo=actor.rol,
            actor_id=actor.id,
            estado_anterior=estado_anterior,
            estado_posterior=estado_posterior,
            hash_previo=hash_previo,
        )
        return AuditoriaLogORM(
            condominio_id=presupuesto.condominio_id,
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

    @staticmethod
    def _serializar(presupuesto: PresupuestoMensual) -> dict[str, Any]:
        return {
            "id": str(presupuesto.id),
            "condominio_id": str(presupuesto.condominio_id),
            "periodo": presupuesto.periodo,
            "moneda": presupuesto.moneda,
            "monto_total": f"{presupuesto.monto_total:.2f}",
            "fecha_vencimiento": presupuesto.fecha_vencimiento.isoformat(),
            "estado": presupuesto.estado,
            "creado_por": presupuesto.creado_por,
            "creado_en": presupuesto.creado_en.isoformat(),
            "aprobado_por": presupuesto.aprobado_por,
            "aprobado_en": (
                presupuesto.aprobado_en.isoformat()
                if presupuesto.aprobado_en is not None
                else None
            ),
            "actualizado_en": presupuesto.actualizado_en.isoformat(),
        }
