from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.security import require_role
from src.modules.excepciones.service import (
    DetalleExcepcionDTO,
    ExcepcionesService,
    PaginaExcepcionesDTO,
    ResolucionDTO,
    SolicitudResolucion,
)

router = APIRouter(prefix="/excepciones", tags=["Excepciones"])
UsuarioJunta = Annotated[dict, Depends(require_role(["ADMIN_JUNTA"]))]
Sesion = Annotated[AsyncSession, Depends(get_db_session, use_cache=False)]


@router.get("", response_model=PaginaExcepcionesDTO)
async def listar_excepciones(
    response: Response,
    usuario: UsuarioJunta,
    session: Sesion,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await ExcepcionesService(session).listar(usuario, offset, limit)


@router.get("/{id}", response_model=DetalleExcepcionDTO)
async def consultar_excepcion(id: UUID, response: Response, usuario: UsuarioJunta, session: Sesion):
    response.headers["Cache-Control"] = "private, no-store"
    return await ExcepcionesService(session).detalle(usuario, id)


@router.post("/{id}/resoluciones", response_model=ResolucionDTO)
async def resolver_excepcion(
    id: UUID,
    solicitud: SolicitudResolucion,
    clave: Annotated[UUID, Header(alias="Idempotency-Key")],
    response: Response,
    usuario: UsuarioJunta,
    session: Sesion,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await ExcepcionesService(session).resolver(usuario, id, clave, solicitud)
