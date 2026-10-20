"""API contextual de estructura inmobiliaria y CSV (CON-3)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import decode_access_token, security_scheme
from src.modules.condominios.estructura.importacion import MAX_BYTES
from src.modules.condominios.estructura.repository import EstructuraRepository
from src.modules.condominios.estructura.schemas import (
    CrearDepartamentoRequest,
    CrearEdificioRequest,
    DepartamentoResponse,
    EdificioResponse,
    EstadoDepartamentoRequest,
    ImportacionResponse,
)
from src.modules.condominios.estructura.service import ActorEstructura, EstructuraService

router = APIRouter(prefix="/condominios/{condominio_id}", tags=["Estructura inmobiliaria"])


async def require_estructura_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> ActorEstructura:
    if auth is None or not auth.credentials:
        raise APIError(401, "NO_AUTENTICADO", "Se requiere un Bearer Token válido.")
    try:
        claims = decode_access_token(auth.credentials)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        raise APIError(
            exc.status_code,
            detail.get("error_code", "TOKEN_INVALIDO"),
            detail.get("mensaje", "Token inválido."),
        ) from exc
    if not claims.get("sub") or not claims.get("rol"):
        raise APIError(401, "TOKEN_INVALIDO", "El token debe contener identidad y rol.")
    contexto = None
    if claims["rol"] != "SUPERADMIN":
        try:
            contexto = UUID(str(claims.get("condominio_id")))
        except ValueError as exc:
            raise APIError(
                403, "ESTRUCTURA_ACCESO_DENEGADO", "El token no tiene un condominio válido."
            ) from exc
    return ActorEstructura(str(claims["sub"]), str(claims["rol"]), contexto)


def get_estructura_service(session: Annotated[AsyncSession, Depends(get_db_session)]):
    return EstructuraService(EstructuraRepository(session))


Actor = Annotated[ActorEstructura, Depends(require_estructura_user)]
Servicio = Annotated[EstructuraService, Depends(get_estructura_service)]


@router.get("/edificios", response_model=list[EdificioResponse])
async def listar_edificios(condominio_id: UUID, actor: Actor, servicio: Servicio):
    return await servicio.listar_edificios(condominio_id, actor)


@router.post("/edificios", response_model=EdificioResponse, status_code=201)
async def crear_edificio(
    condominio_id: UUID, request: CrearEdificioRequest, actor: Actor, servicio: Servicio
):
    return await servicio.crear_edificio(condominio_id, request, actor)


@router.get("/departamentos", response_model=list[DepartamentoResponse])
async def listar_departamentos(
    condominio_id: UUID,
    actor: Actor,
    servicio: Servicio,
    edificio_id: UUID | None = None,
    activo: bool | None = None,
):
    return await servicio.listar_departamentos(condominio_id, actor, edificio_id, activo)


@router.post(
    "/edificios/{edificio_id}/departamentos", response_model=DepartamentoResponse, status_code=201
)
async def crear_departamento(
    condominio_id: UUID,
    edificio_id: UUID,
    request: CrearDepartamentoRequest,
    actor: Actor,
    servicio: Servicio,
):
    return await servicio.crear_departamento(condominio_id, edificio_id, request, actor)


@router.patch("/departamentos/{departamento_id}/estado", response_model=DepartamentoResponse)
async def cambiar_estado(
    condominio_id: UUID,
    departamento_id: UUID,
    request: EstadoDepartamentoRequest,
    actor: Actor,
    servicio: Servicio,
):
    return await servicio.cambiar_estado(condominio_id, departamento_id, request.activo, actor)


async def importar(condominio_id, actor, servicio, archivo, confirmar):
    try:
        contenido = await archivo.read(MAX_BYTES + 1)
    finally:
        await archivo.close()
    return await servicio.importar(condominio_id, contenido, actor, confirmar)


@router.post("/importaciones/previsualizar", response_model=ImportacionResponse)
async def previsualizar(
    condominio_id: UUID, actor: Actor, servicio: Servicio, archivo: Annotated[UploadFile, File()]
):
    return await importar(condominio_id, actor, servicio, archivo, False)


@router.post("/importaciones/confirmar", response_model=ImportacionResponse)
async def confirmar(
    condominio_id: UUID, actor: Actor, servicio: Servicio, archivo: Annotated[UploadFile, File()]
):
    return await importar(condominio_id, actor, servicio, archivo, True)
