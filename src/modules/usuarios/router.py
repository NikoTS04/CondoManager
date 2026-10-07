"""Router FastAPI para el Dominio de Usuarios y RBAC (Junta Directiva - PROC-05)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.usuarios.schemas import (
    AsignarRolRequest,
    CrearUsuarioRequest,
    UsuarioDTO,
    UsuarioRolDTO,
)
from src.modules.usuarios.service import (
    CondominioNoExisteException,
    EmailYaRegistradoException,
    RolYaAsignadoException,
    UsuarioNoEncontradoException,
    UsuariosService,
)

router = APIRouter(prefix="/usuario", tags=["Usuarios y Roles (RBAC)"])


@router.post(
    "/crear",
    response_model=UsuarioDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de usuario en el directorio (PROC-05)",
)
async def crear_usuario(
    request: CrearUsuarioRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Crea un usuario validando la unicidad del correo y almacenando la contraseña como hash."""
    try:
        usuario, _ = await UsuariosService.crear_usuario(session=session, request=request)
    except EmailYaRegistradoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "EMAIL_YA_REGISTRADO",
                "mensaje": str(exc),
                "detalles": {"email": exc.email},
            },
        )
    return usuario


@router.post(
    "/roles",
    response_model=UsuarioRolDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Asignación de rol RBAC a un usuario dentro de un condominio",
)
async def asignar_rol(
    request: AsignarRolRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Asigna un rol (SUPERADMIN, ADMIN_JUNTA, AUDITOR o RESIDENTE) a un usuario en un condominio."""
    try:
        usuario_rol, _ = await UsuariosService.asignar_rol(session=session, request=request)
    except UsuarioNoEncontradoException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "USUARIO_NO_ENCONTRADO",
                "mensaje": str(exc),
                "detalles": {"usuario_id": str(exc.usuario_id)},
            },
        )
    except CondominioNoExisteException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "CONDOMINIO_NO_ENCONTRADO",
                "mensaje": str(exc),
                "detalles": {"condominio_id": str(exc.condominio_id)},
            },
        )
    except RolYaAsignadoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "ROL_YA_ASIGNADO",
                "mensaje": str(exc),
                "detalles": {
                    "usuario_id": str(exc.usuario_id),
                    "condominio_id": str(exc.condominio_id),
                },
            },
        )
    return usuario_rol
