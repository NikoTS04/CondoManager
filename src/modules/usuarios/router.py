"""Autenticación SQL y administración de cuentas inactivas (CON-04)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.core.config import settings
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.usuarios.repository import get_usuarios_repository
from src.modules.usuarios.schemas import (
    AsignacionRolResponse,
    AsignarRolRequest,
    CambiarEstadoUsuarioRequest,
    CrearUsuarioRequest,
    CuentaUsuarioConRolResponse,
    CuentaUsuarioResponse,
    LoginRequest,
    TokenResponse,
    UserContextResponse,
    UsuarioDTO,
)
from src.modules.usuarios.service import UsuariosService

router = APIRouter(tags=["Autenticación y RBAC"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, repository=Depends(get_usuarios_repository)):
    return await UsuariosService(repository).autenticar(request)


@router.get("/auth/me", response_model=UserContextResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserContextResponse(
        id=current_user["sub"],
        **{
            k: current_user[k]
            for k in ("email", "nombre", "apellido", "rol", "condominio_id", "departamentos")
        },
    )


@router.get("/auth/demo-users", response_model=list[UsuarioDTO])
async def get_demo_users(repository=Depends(get_usuarios_repository)):
    if not settings.DEMO_MODE:
        raise APIError(404, "RECURSO_NO_ENCONTRADO", "El modo demo está deshabilitado.")
    from src.modules.usuarios.demo import DEMO_CUENTAS

    perfiles = []
    for cuenta in DEMO_CUENTAS:
        usuario = await repository.por_email(cuenta["email"])
        if usuario is not None and usuario.esta_activo:
            contextos = await repository.contextos(usuario.id)
            perfil = await repository.perfil(usuario, contextos[0]["id"] if contextos else None)
            if perfil is not None:
                perfiles.append(perfil)
    return perfiles


@router.post(
    "/condominios/{condominio_id}/usuarios", response_model=CuentaUsuarioResponse, status_code=201
)
async def crear_usuario(
    condominio_id: UUID,
    request: CrearUsuarioRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).crear(condominio_id, request, actor)


@router.get(
    "/condominios/{condominio_id}/usuarios", response_model=list[CuentaUsuarioConRolResponse]
)
async def listar_usuarios(
    condominio_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).listar(condominio_id, actor, limit, offset)


@router.get(
    "/condominios/{condominio_id}/usuarios/{usuario_id}/rol", response_model=AsignacionRolResponse
)
async def consultar_rol_usuario(
    condominio_id: UUID,
    usuario_id: UUID,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).consultar_rol(condominio_id, usuario_id, actor)


@router.put(
    "/condominios/{condominio_id}/usuarios/{usuario_id}/rol", response_model=AsignacionRolResponse
)
async def asignar_rol_usuario(
    condominio_id: UUID,
    usuario_id: UUID,
    request: AsignarRolRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).gestionar_rol(
        condominio_id, usuario_id, request.rol, actor
    )


@router.delete(
    "/condominios/{condominio_id}/usuarios/{usuario_id}/rol", response_model=AsignacionRolResponse
)
async def revocar_rol_usuario(
    condominio_id: UUID,
    usuario_id: UUID,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).gestionar_rol(condominio_id, usuario_id, None, actor)


@router.patch("/usuarios/{usuario_id}/estado", response_model=CuentaUsuarioResponse)
async def cambiar_estado_usuario(
    usuario_id: UUID,
    condominio_id: UUID,
    request: CambiarEstadoUsuarioRequest,
    actor: dict = Depends(get_current_user),
    repository=Depends(get_usuarios_repository),
):
    return await UsuariosService(repository).cambiar_estado(
        condominio_id, usuario_id, request.esta_activo, actor
    )
