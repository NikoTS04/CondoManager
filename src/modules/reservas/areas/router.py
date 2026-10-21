"""Administración del catálogo de áreas por condominio (CON-39)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.core.security import get_current_user
from src.modules.reservas.areas.repository import get_areas_repository
from src.modules.reservas.areas.schemas import (
    AreaComunDTO,
    ConfigurarAreaRequest,
    EstadoAreaRequest,
)
from src.modules.reservas.areas.service import AreasService

router = APIRouter(prefix="/condominios/{condominio_id}/areas", tags=["Catálogo de áreas"])


@router.get("", response_model=list[AreaComunDTO])
async def listar_areas_administrativas(
    condominio_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    esta_activa: bool | None = None,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_areas_repository),
):
    return await AreasService(repository).listar(condominio_id, actor, limit, offset, esta_activa)


@router.post("", response_model=AreaComunDTO, status_code=201)
async def crear_area(
    condominio_id: UUID,
    request: ConfigurarAreaRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_areas_repository),
):
    return await AreasService(repository).crear(condominio_id, request, actor)


@router.get("/{area_id}", response_model=AreaComunDTO)
async def consultar_area(
    condominio_id: UUID,
    area_id: UUID,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_areas_repository),
):
    return await AreasService(repository).consultar(condominio_id, area_id, actor)


@router.put("/{area_id}", response_model=AreaComunDTO)
async def configurar_area(
    condominio_id: UUID,
    area_id: UUID,
    request: ConfigurarAreaRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_areas_repository),
):
    return await AreasService(repository).configurar(condominio_id, area_id, request, actor)


@router.patch("/{area_id}/estado", response_model=AreaComunDTO)
async def cambiar_estado_area(
    condominio_id: UUID,
    area_id: UUID,
    request: EstadoAreaRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_areas_repository),
):
    return await AreasService(repository).estado(condominio_id, area_id, request.esta_activa, actor)
