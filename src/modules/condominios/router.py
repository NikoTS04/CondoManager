"""Endpoints de configuración de condominios (CON-2)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.condominios.repository import (
    CondominioRepository,
    SQLAlchemyCondominioRepository,
)
from src.modules.condominios.schemas import (
    ActualizarPoliticaMoraRequest,
    CondominioResponse,
    CrearCondominioRequest,
)
from src.modules.condominios.service import CondominiosService, actualizar_politica_mora

router = APIRouter(prefix="/condominios", tags=["Condominios"])


@router.put("/{condominio_id}/politica-mora", response_model=CondominioResponse)
async def editar_politica_mora(
    condominio_id: UUID,
    request: ActualizarPoliticaMoraRequest,
    usuario: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    return await actualizar_politica_mora(session, condominio_id, request, usuario)


async def require_superadmin(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    if current_user.get("rol") != "SUPERADMIN":
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            "ACCESO_DENEGADO",
            "La operación requiere el rol SUPERADMIN.",
        )
    return current_user


def get_condominio_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CondominioRepository:
    return SQLAlchemyCondominioRepository(session)


@router.get(
    "",
    response_model=list[CondominioResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar condominios activos",
)
async def listar_condominios(
    _current_user: Annotated[dict[str, Any], Depends(require_superadmin)],
    repository: Annotated[CondominioRepository, Depends(get_condominio_repository)],
) -> list[CondominioResponse]:
    condominios = await CondominiosService(repository).listar_activos()
    return [CondominioResponse.model_validate(condominio) for condominio in condominios]


@router.post(
    "",
    response_model=CondominioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear y configurar un condominio",
)
async def crear_condominio(
    request: CrearCondominioRequest,
    current_user: Annotated[dict[str, Any], Depends(require_superadmin)],
    repository: Annotated[CondominioRepository, Depends(get_condominio_repository)],
) -> CondominioResponse:
    condominio = await CondominiosService(repository).crear(
        request, actor_id=str(current_user["sub"])
    )
    return CondominioResponse.model_validate(condominio)


@router.get(
    "/{condominio_id}",
    response_model=CondominioResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar un condominio por UUID",
)
async def obtener_condominio(
    condominio_id: UUID,
    _current_user: Annotated[dict[str, Any], Depends(require_superadmin)],
    repository: Annotated[CondominioRepository, Depends(get_condominio_repository)],
) -> CondominioResponse:
    condominio = await CondominiosService(repository).obtener(condominio_id)
    if condominio is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "CONDOMINIO_NO_ENCONTRADO",
            "No existe un condominio con el identificador solicitado.",
            {"condominio_id": str(condominio_id)},
        )
    return CondominioResponse.model_validate(condominio)
