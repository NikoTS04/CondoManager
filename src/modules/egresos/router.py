"""Endpoints de registro y consulta de egresos CON-51."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.security import get_current_user
from src.modules.egresos.schemas import (
    ActualizarEgresoRequest,
    CrearEgresoRequest,
    DocumentoFinancieroResponse,
    EgresoListaResponse,
    EgresoResponse,
    EstadoEgreso,
)
from src.modules.egresos.service import EgresosService

router = APIRouter(tags=["Egresos y caja"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
UsuarioActual = Annotated[dict, Depends(get_current_user)]


@router.post(
    "/condominios/{condominio_id}/egresos",
    response_model=EgresoResponse,
    status_code=201,
)
async def registrar_egreso(
    condominio_id: UUID,
    request: CrearEgresoRequest,
    response: Response,
    actor: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await EgresosService(session).registrar(actor, condominio_id, request)


@router.get(
    "/condominios/{condominio_id}/egresos",
    response_model=EgresoListaResponse,
)
async def listar_egresos(
    condominio_id: UUID,
    response: Response,
    actor: UsuarioActual,
    session: Session,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    estado: EstadoEgreso | None = None,
    proveedor_id: UUID | None = None,
    concepto_id: UUID | None = None,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await EgresosService(session).listar(
        actor,
        condominio_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado,
        proveedor_id=proveedor_id,
        concepto_id=concepto_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/condominios/{condominio_id}/egresos/{egreso_id}",
    response_model=EgresoResponse,
)
async def consultar_egreso(
    condominio_id: UUID,
    egreso_id: UUID,
    response: Response,
    actor: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await EgresosService(session).consultar(actor, condominio_id, egreso_id)


@router.patch(
    "/condominios/{condominio_id}/egresos/{egreso_id}",
    response_model=EgresoResponse,
)
async def actualizar_egreso(
    condominio_id: UUID,
    egreso_id: UUID,
    request: ActualizarEgresoRequest,
    response: Response,
    actor: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await EgresosService(session).actualizar(actor, condominio_id, egreso_id, request)


@router.post(
    "/condominios/{condominio_id}/egresos/{egreso_id}/documentos",
    response_model=DocumentoFinancieroResponse,
    status_code=201,
)
async def adjuntar_documento_egreso(
    condominio_id: UUID,
    egreso_id: UUID,
    actor: UsuarioActual,
    session: Session,
    tipo: Annotated[Literal["SUSTENTO", "EVIDENCIA_PAGO"], Form(...)],
    archivo: UploadFile = File(...),
):
    return await EgresosService(session).adjuntar_documento(
        actor, condominio_id, egreso_id, archivo, tipo
    )


@router.get(
    "/condominios/{condominio_id}/egresos/{egreso_id}/documentos/{documento_id}",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("application/pdf", "image/jpeg", "image/png")
            }
        }
    },
)
async def consultar_documento_egreso(
    condominio_id: UUID,
    egreso_id: UUID,
    documento_id: UUID,
    actor: UsuarioActual,
    session: Session,
):
    contenido, mime, nombre = await EgresosService(session).consultar_documento(
        actor, condominio_id, egreso_id, documento_id
    )
    nombre_seguro = nombre.replace('"', "")
    return Response(
        content=contenido,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{nombre_seguro}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
