"""Router FastAPI para Autenticación y RBAC (PROC-05)."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.security import get_current_user
from src.modules.usuarios.schemas import (
    LoginRequest,
    TokenResponse,
    UserContextResponse,
    UsuarioDTO,
)
from src.modules.usuarios.service import CredencialesInvalidasException, UsuariosService

router = APIRouter(prefix="/auth", tags=["Autenticación y RBAC"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Inicio de sesión y emisión de token JWT",
)
async def login(request: LoginRequest):
    """Valida credenciales de usuario y retorna un access token JWT con sus claims y permisos."""
    try:
        response = UsuariosService.autenticar(request)
        return response
    except CredencialesInvalidasException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "CREDENCIALES_INVALIDAS", "mensaje": str(exc)},
        )


@router.get(
    "/me",
    response_model=UserContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Contexto y perfil del usuario autenticado",
)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna la información del perfil y departamentos autorizados según el token Bearer."""
    return UserContextResponse(
        id=current_user["sub"],
        email=current_user["email"],
        nombre=current_user.get("nombre", "").split()[0] if current_user.get("nombre") else "",
        apellido=current_user.get("nombre", "").split()[-1] if current_user.get("nombre") else "",
        rol=current_user["rol"],
        condominio_id=current_user["condominio_id"],
        departamentos=current_user.get("departamentos", []),
        tipo_relacion=current_user.get("tipo_relacion"),
    )


@router.get(
    "/demo-users",
    response_model=List[UsuarioDTO],
    status_code=status.HTTP_200_OK,
    summary="Listado de perfiles demo para pruebas de campo",
)
async def get_demo_users():
    """Retorna los perfiles precargados para la demostración del piloto Villa Bonita 3."""
    return UsuariosService.listar_usuarios_demo()
