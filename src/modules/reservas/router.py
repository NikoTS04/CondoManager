"""API de reservas sobre PostgreSQL; sin calendarios locales al proceso."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends

from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.reservas.areas.repository import get_areas_repository
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.persistencia import get_reservas_service
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
    HorarioOcupado,
    ReservaConfirmadaResponse,
    ReservaResponseDTO,
)
from src.modules.reservas.service import (
    AreaInactivaException,
    CancelacionInvalidaException,
    ConflictoHorarioException,
    HorarioInvalidoException,
)

router = APIRouter(tags=["Reservas de Áreas Comunes"])


@router.get("/areas", response_model=list[AreaComunDTO])
async def listar_areas(
    user=Depends(get_current_user),
    condominio_id: UUID | None = None,
    areas_repository=Depends(get_areas_repository),
):
    return await AreasService(areas_repository).catalogo(user, condominio_id)


@router.get("/areas/{area_id}/disponibilidad", response_model=list[HorarioOcupado])
async def disponibilidad_area(
    area_id: UUID,
    fecha: date,
    user=Depends(get_current_user),
    service=Depends(get_reservas_service),
):
    return await service.disponibilidad(area_id, fecha, user)


@router.get("/reservas", response_model=list[ReservaResponseDTO])
async def listar_reservas(
    area_id: UUID | None = None,
    fecha: date | None = None,
    condominio_id: UUID | None = None,
    user=Depends(get_current_user),
    service=Depends(get_reservas_service),
):
    return await service.listar(user, condominio_id, area_id, fecha)


@router.post("/reservas", response_model=ReservaConfirmadaResponse, status_code=201)
async def crear_reserva(
    request: CrearReservaRequest,
    user=Depends(get_current_user),
    service=Depends(get_reservas_service),
):
    try:
        return await service.crear(request, user)
    except (ConflictoHorarioException, AreaInactivaException) as exc:
        raise APIError(409, exc.error_code, exc.mensaje) from exc
    except HorarioInvalidoException as exc:
        raise APIError(400, exc.error_code, exc.mensaje) from exc


@router.post("/reservas/{reserva_id}/cancelar", response_model=CancelarReservaResponse)
async def cancelar_reserva(
    reserva_id: UUID,
    request: CancelarReservaRequest | None = None,
    user=Depends(get_current_user),
    service=Depends(get_reservas_service),
):
    try:
        return await service.cancelar(reserva_id, request, user)
    except CancelacionInvalidaException as exc:
        raise APIError(422, exc.error_code, exc.mensaje) from exc
