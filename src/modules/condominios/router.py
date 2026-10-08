"""Endpoints de configuración de condominios (CON-2)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import decode_access_token, security_scheme
from src.modules.condominios.repository import (
    CondominioRepository,
    SQLAlchemyCondominioRepository,
)
from src.modules.condominios.schemas import CondominioResponse, CrearCondominioRequest
from src.modules.condominios.service import CondominiosService

router = APIRouter(prefix="/condominios", tags=["Condominios"])


async def require_superadmin(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> dict[str, Any]:
    if auth is None or not auth.credentials:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            "NO_AUTENTICADO",
            "Se requiere un Bearer Token válido.",
        )
    try:
        current_user = decode_access_token(auth.credentials)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        raise APIError(
            exc.status_code,
            str(detail.get("error_code", "TOKEN_INVALIDO")),
            str(detail.get("mensaje", "Token de autenticación inválido.")),
        ) from exc
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
