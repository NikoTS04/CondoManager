"""Reglas de aplicación para configurar y consultar condominios."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.core.authorization import autorizar_condominio
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio
from src.modules.condominios.repository import CondominioRepository
from src.modules.condominios.schemas import (
    ActualizarPoliticaMoraRequest,
    CondominioResponse,
    CrearCondominioRequest,
)


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
            monto_mora_diario=request.monto_mora_diario,
            politica_version=1,
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
            "monto_mora_diario": (
                str(condominio.monto_mora_diario)
                if condominio.monto_mora_diario is not None
                else None
            ),
            "politica_version": condominio.politica_version,
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

    async def listar_activos(self) -> list[Condominio]:
        return await self._repository.listar_activos()


async def actualizar_politica_mora(
    session: AsyncSession, cid: UUID, request: ActualizarPoliticaMoraRequest, usuario: dict
) -> Condominio:
    autorizar_condominio(usuario, cid, escritura=True)
    async with session.begin():
        condominio = await session.scalar(
            select(Condominio).where(Condominio.id == cid).with_for_update()
        )
        if condominio is None or not condominio.activo:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo.")
        if request.version_esperada != condominio.politica_version:
            raise APIError(
                409, "POLITICA_VERSION_OBSOLETA", "Recargue la política antes de editar."
            )
        # Reutilizar validación monetaria de alta, incluida la moneda persistida.
        from pydantic import ValidationError

        try:
            datos = CrearCondominioRequest(
                nombre=condominio.nombre,
                direccion=condominio.direccion,
                moneda=condominio.moneda,
                **request.model_dump(exclude={"motivo", "version_esperada"}),
            )
        except ValidationError as exc:
            raise APIError(422, "DATOS_CONDOMINIO_INVALIDOS", "Política de mora inválida.") from exc
        campos = (
            "regla_mora_tipo",
            "monto_mora_diario",
            "monto_mora_fijo",
            "tasa_mora_porcentaje",
            "dia_vencimiento",
            "dias_gracia",
        )
        if all(getattr(condominio, c) == getattr(datos, c) for c in campos):
            return condominio
        anterior = CondominioResponse.model_validate(condominio).model_dump(mode="json")
        for campo in campos:
            setattr(condominio, campo, getattr(datos, campo))
        condominio.politica_version += 1
        posterior = CondominioResponse.model_validate(condominio).model_dump(mode="json")
        previo = await session.scalar(
            select(AuditoriaLogORM.hash_actual)
            .where(AuditoriaLogORM.condominio_id == cid)
            .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            .limit(1)
        )
        payload = AuditoriaPayload(
            condominio_id=str(cid),
            departamento_id=None,
            accion_ejecutada="POLITICA_MORA_MODIFICADA",
            motivo=request.motivo,
            resultado="EXITOSO",
            actor_tipo=usuario["rol"],
            actor_id=str(usuario["sub"]),
            estado_anterior=anterior,
            estado_posterior=posterior,
            hash_previo=previo,
        )
        session.add(
            AuditoriaLogORM(
                condominio_id=cid,
                departamento_id=None,
                timestamp=payload.timestamp,
                accion_ejecutada=payload.accion_ejecutada,
                motivo=payload.motivo,
                resultado=payload.resultado,
                actor_tipo=payload.actor_tipo,
                actor_id=payload.actor_id,
                estado_anterior=anterior,
                estado_posterior=posterior,
                hash_previo=previo,
                hash_actual=payload.calcular_hash(),
            )
        )
        await session.flush()
        return condominio
