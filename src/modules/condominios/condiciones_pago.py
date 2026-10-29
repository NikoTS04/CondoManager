"""Condiciones financieras por unidad; no son roles ni pagos del residente."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import autorizar_condominio
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.models import UsuarioDepartamento

router = APIRouter(tags=["Condiciones de pago"])


class CondicionesPagoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vinculo_responsable_id: UUID | None
    dias_gracia_override: int | None = Field(ge=0, le=30, strict=True)
    version_esperada: int = Field(gt=0, strict=True)
    motivo: str = Field(min_length=1, max_length=1000)

    @field_validator("motivo")
    @classmethod
    def motivo_no_vacio(cls, value):
        if not value.strip():
            raise ValueError("Indique el motivo del cambio.")
        return value.strip()

    @model_validator(mode="after")
    def sin_responsable_hereda(self):
        if self.vinculo_responsable_id is None and self.dias_gracia_override is not None:
            raise ValueError("Sin responsable debe heredarse la gracia global.")
        return self


class CondicionesPagoResponse(BaseModel):
    departamento_id: UUID
    version: int
    vinculo_responsable_id: UUID | None
    dias_gracia_override: int | None
    dias_gracia_efectivos: int


def gracia_efectiva(global_dias: int, vinculo: UsuarioDepartamento | None) -> int:
    if vinculo is not None and vinculo.es_activo and vinculo.dias_gracia_override is not None:
        return vinculo.dias_gracia_override
    return global_dias


def fotografiar_politica(condominio, vinculo):
    return {
        "version": condominio.politica_version,
        "modalidad": condominio.regla_mora_tipo,
        "monto_diario": str(condominio.monto_mora_diario)
        if condominio.monto_mora_diario is not None
        else None,
        "monto_fijo": str(condominio.monto_mora_fijo)
        if condominio.monto_mora_fijo is not None
        else None,
        "tasa_porcentaje": str(condominio.tasa_mora_porcentaje)
        if condominio.tasa_mora_porcentaje is not None
        else None,
        "dias_gracia": gracia_efectiva(condominio.dias_gracia, vinculo),
        "responsable_vinculo_id": str(vinculo.id)
        if vinculo is not None and vinculo.es_activo
        else None,
        "zona_horaria": "America/Lima",
    }


class CondicionesPagoService:
    def __init__(self, session):
        self.session = session
        self.repo = SQLAlchemyPagosRepository(session)

    async def _vinculo(self, id, did):
        if id is None:
            return None
        return await self.session.scalar(
            select(UsuarioDepartamento).where(
                UsuarioDepartamento.id == id,
                UsuarioDepartamento.departamento_id == did,
                UsuarioDepartamento.es_activo.is_(True),
            )
        )

    async def procesar(self, did, actor, request=None):
        if actor.get("rol") not in {"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"}:
            raise APIError(403, "ACCESO_DENEGADO", "Solo administración o auditoría.")
        async with self.session.begin():
            depto, condominio = await self.repo.departamento(
                did, actor, escritura=request is not None, bloquear=request is not None
            )
            autorizar_condominio(actor, condominio.id, escritura=request is not None)
            vinculo = await self._vinculo(depto.responsable_pago_id, did)

            def representar():
                return CondicionesPagoResponse(
                    departamento_id=did,
                    version=depto.condiciones_pago_version,
                    vinculo_responsable_id=vinculo.id if vinculo else None,
                    dias_gracia_override=vinculo.dias_gracia_override if vinculo else None,
                    dias_gracia_efectivos=gracia_efectiva(condominio.dias_gracia, vinculo),
                )

            if request is None:
                return representar()
            if request.version_esperada != depto.condiciones_pago_version:
                raise APIError(
                    409, "CONDICIONES_VERSION_OBSOLETA", "Recargue las condiciones de pago."
                )
            anterior = representar().model_dump(mode="json")
            nuevo = await self._vinculo(request.vinculo_responsable_id, did)
            if request.vinculo_responsable_id is not None and nuevo is None:
                raise APIError(
                    422, "RESPONSABLE_INVALIDO", "Seleccione un vínculo activo de esta unidad."
                )
            if (
                depto.responsable_pago_id == request.vinculo_responsable_id
                and (nuevo.dias_gracia_override if nuevo else None) == request.dias_gracia_override
            ):
                return representar()
            depto.responsable_pago_id = request.vinculo_responsable_id
            depto.condiciones_pago_version += 1
            if nuevo is not None:
                nuevo.dias_gracia_override = request.dias_gracia_override
            vinculo = nuevo
            posterior = representar()
            await self.repo.auditar(
                actor,
                condominio.id,
                did,
                "CONDICIONES_PAGO_MODIFICADAS",
                request.motivo,
                anterior,
                posterior.model_dump(mode="json"),
            )
            return posterior


@router.get(
    "/departamentos/{departamento_id}/condiciones-pago", response_model=CondicionesPagoResponse
)
async def consultar_condiciones_pago(
    departamento_id: UUID,
    actor: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    return await CondicionesPagoService(session).procesar(departamento_id, actor)


@router.put(
    "/departamentos/{departamento_id}/condiciones-pago", response_model=CondicionesPagoResponse
)
async def configurar_condiciones_pago(
    departamento_id: UUID,
    request: CondicionesPagoRequest,
    actor: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    return await CondicionesPagoService(session).procesar(departamento_id, actor, request)
