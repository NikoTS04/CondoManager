from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.incidencias.schemas import (
    BandejaIncidenciasDTO,
    CrearIncidencia,
    IncidenciaDTO,
    RegistroIncidenciaDTO,
    ReporteIncidenciaDTO,
    RevisarIncidencia,
)
from src.modules.incidencias.service import IncidenciasService

router = APIRouter(prefix="/incidencias", tags=["Incidencias"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
UsuarioActual = Annotated[dict, Depends(get_current_user)]


@router.post(
    "",
    status_code=201,
    response_model=RegistroIncidenciaDTO,
    responses={200: {"model": RegistroIncidenciaDTO}},
)
async def registrar_incidencia(
    formulario: Annotated[CrearIncidencia, Form(media_type="multipart/form-data")],
    clave: Annotated[UUID, Header(alias="Idempotency-Key")],
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    incidencia, advertencia, creada = await IncidenciasService(session).registrar(
        usuario, formulario, clave
    )
    response.status_code = 201 if creada else 200
    response.headers["Cache-Control"] = "private, no-store"
    return RegistroIncidenciaDTO(
        **ReporteIncidenciaDTO.model_validate(incidencia).model_dump(),
        advertencia_evidencia=advertencia,
    )


@router.get("", response_model=BandejaIncidenciasDTO)
async def listar_incidencias(
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).listar(usuario, offset=offset, limit=limit)


@router.get("/{incidencia_id}", response_model=IncidenciaDTO)
async def consultar_incidencia(
    incidencia_id: UUID, response: Response, usuario: UsuarioActual, session: Session
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).consultar(usuario, incidencia_id)


@router.patch("/{incidencia_id}/revision", response_model=IncidenciaDTO)
async def revisar_incidencia(
    incidencia_id: UUID,
    revision: RevisarIncidencia,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).revisar(usuario, incidencia_id, revision)


@router.get(
    "/{incidencia_id}/evidencia",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/jpeg", "image/png")
            }
        }
    },
)
async def consultar_evidencia(incidencia_id: UUID, usuario: UsuarioActual, session: Session):
    incidencia = await IncidenciasService(session).consultar(
        usuario, incidencia_id, incluir_evidencia=True
    )
    if not incidencia.tiene_evidencia:
        raise APIError(404, "EVIDENCIA_NO_ENCONTRADA", "La incidencia no tiene evidencia adjunta.")
    return Response(
        content=incidencia.evidencia,
        media_type=incidencia.evidencia_mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
