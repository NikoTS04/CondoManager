"""Reglas de aplicación para configurar y consultar condominios."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.core.audit import AuditoriaPayload
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio
from src.modules.condominios.repository import CondominioRepository
from src.modules.condominios.schemas import CrearCondominioRequest


class CondominiosService:
    def __init__(self, repository: CondominioRepository) -> None:
        self._repository = repository

    async def crear(self, request: CrearCondominioRequest, actor_id: str) -> Condominio:
        condominio = Condominio(
            id=uuid4(),
            nombre=request.nombre,
            direccion=request.direccion,
            moneda=request.moneda.value,
            regla_mora_tipo=request.regla_mora_tipo.value,
            monto_mora_fijo=request.monto_mora_fijo,
            tasa_mora_porcentaje=request.tasa_mora_porcentaje,
            dia_vencimiento=request.dia_vencimiento,
            dias_gracia=request.dias_gracia,
            activo=True,
            creado_en=datetime.now(UTC),
        )

        estado_posterior = {
            "id": str(condominio.id),
            "nombre": condominio.nombre,
            "direccion": condominio.direccion,
            "moneda": condominio.moneda,
            "regla_mora_tipo": condominio.regla_mora_tipo,
            "monto_mora_fijo": (
                f"{condominio.monto_mora_fijo:.2f}"
                if condominio.monto_mora_fijo is not None
                else None
            ),
            "tasa_mora_porcentaje": (
                f"{condominio.tasa_mora_porcentaje:.4f}"
                if condominio.tasa_mora_porcentaje is not None
                else None
            ),
            "dia_vencimiento": condominio.dia_vencimiento,
            "dias_gracia": condominio.dias_gracia,
            "activo": condominio.activo,
            "creado_en": condominio.creado_en.isoformat(),
        }
        payload = AuditoriaPayload(
            condominio_id=str(condominio.id),
            departamento_id=None,
            accion_ejecutada="CONDOMINIO_CREADO",
            motivo="CONFIGURACION_INICIAL_SUPERADMIN",
            resultado="EXITOSO",
            actor_tipo="SUPERADMIN",
            actor_id=actor_id,
            estado_anterior={},
            estado_posterior=estado_posterior,
        )
        hash_actual = payload.calcular_hash()
        auditoria = AuditoriaLogORM(
            condominio_id=condominio.id,
            departamento_id=None,
            timestamp=payload.timestamp,
            accion_ejecutada=payload.accion_ejecutada,
            motivo=payload.motivo,
            resultado=payload.resultado,
            actor_tipo=payload.actor_tipo,
            actor_id=payload.actor_id,
            estado_anterior=payload.estado_anterior,
            estado_posterior=payload.estado_posterior,
            hash_previo=None,
            hash_actual=hash_actual,
        )
        return await self._repository.agregar(condominio, auditoria)

    async def obtener(self, condominio_id: UUID) -> Condominio | None:
        return await self._repository.obtener_por_id(condominio_id)
