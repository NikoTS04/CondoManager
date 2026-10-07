"""Servicio de Negocio del Dominio de Usuarios y RBAC (Junta Directiva - PROC-05).

Implementa la alta de usuarios con unicidad de correo, hash irreversible de contraseña y la
asignación de roles contextuales por condominio con control de unicidad (uq_usuario_condo_rol).
Toda mutación registra los 7 campos obligatorios de auditoría inmutable (src/core/audit.py).
"""

import uuid

from passlib.hash import pbkdf2_sha256
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.modules.condominios.models import Condominio
from src.modules.usuarios.models import Usuario, UsuarioRol
from src.modules.usuarios.schemas import (
    AsignarRolRequest,
    CrearUsuarioRequest,
    UsuarioDTO,
    UsuarioRolDTO,
)


class EmailYaRegistradoException(Exception):
    def __init__(self, email: str):
        super().__init__(
            f"El correo '{email}' ya se encuentra registrado en el directorio de usuarios."
        )
        self.email = email


class UsuarioNoEncontradoException(Exception):
    def __init__(self, usuario_id: uuid.UUID):
        super().__init__(f"El usuario '{usuario_id}' no existe en el directorio.")
        self.usuario_id = usuario_id


class CondominioNoExisteException(Exception):
    def __init__(self, condominio_id: uuid.UUID):
        super().__init__(f"El condominio '{condominio_id}' no existe en la plataforma.")
        self.condominio_id = condominio_id


class RolYaAsignadoException(Exception):
    def __init__(self, usuario_id: uuid.UUID, condominio_id: uuid.UUID):
        super().__init__(
            "El usuario ya posee un rol dentro de este condominio; "
            "la restricción uq_usuario_condo_rol impide roles duplicados."
        )
        self.usuario_id = usuario_id
        self.condominio_id = condominio_id


class UsuariosService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hashea la contraseña con PBKDF2-SHA256 (passlib), sin reversibilidad.

        Se evita passlib.hash.bcrypt por incompatibilidad declarativa con las versiones
        modernas de bcrypt (>=4.1); PBKDF2-SHA256 con 29000 iteraciones es un esquema
        soportado nativamente por passlib sin dependencias externas.
        """
        return pbkdf2_sha256.hash(password)

    @staticmethod
    async def crear_usuario(
        session: AsyncSession, request: CrearUsuarioRequest
    ) -> tuple[UsuarioDTO, AuditoriaPayload]:
        """Da de alta un usuario validando la unicidad de correo (ciclo PROC-05, paso 1)."""
        email_normalizado = request.email.strip().lower()

        resultado = await session.execute(select(Usuario).where(Usuario.email == email_normalizado))
        if resultado.scalar_one_or_none() is not None:
            raise EmailYaRegistradoException(email_normalizado)

        usuario = Usuario(
            email=email_normalizado,
            password_hash=UsuariosService.hash_password(request.password),
            nombre=request.nombre.strip(),
            apellido=request.apellido.strip(),
            telefono=request.telefono.strip() if request.telefono else None,
            documento_identidad=request.documento_identidad.strip(),
            esta_activo=True,
        )
        session.add(usuario)
        await session.flush()

        usuario_dto = UsuarioDTO.model_validate(usuario)

        # Auditoría inmutable con los 7 campos obligatorios (guardarraíl B)
        audit_log = AuditoriaPayload(
            condominio_id="CONDOMINIO_GENERAL",
            departamento_id="CONDOMINIO_GENERAL",
            accion_ejecutada="ALTA_USUARIO",
            motivo="Alta de usuario en el directorio según PROC-05 con verificación de unicidad de correo.",
            resultado="EXITOSO",
            actor_tipo="ADMINISTRADOR",
            actor_id=str(usuario_dto.id),
            estado_anterior={"usuario_id": None, "email": None, "esta_activo": None},
            estado_posterior={
                "usuario_id": str(usuario_dto.id),
                "email": usuario_dto.email,
                "nombre": f"{usuario_dto.nombre} {usuario_dto.apellido}",
                "esta_activo": True,
            },
        )

        return usuario_dto, audit_log

    @staticmethod
    async def asignar_rol(
        session: AsyncSession, request: AsignarRolRequest
    ) -> tuple[UsuarioRolDTO, AuditoriaPayload]:
        """Asigna un rol RBAC contextual verificando existencia y unicidad por condominio."""
        resultado_usuario = await session.execute(
            select(Usuario).where(Usuario.id == request.usuario_id)
        )
        usuario = resultado_usuario.scalar_one_or_none()
        if usuario is None:
            raise UsuarioNoEncontradoException(request.usuario_id)

        resultado_condominio = await session.execute(
            select(Condominio).where(Condominio.id == request.condominio_id)
        )
        condominio = resultado_condominio.scalar_one_or_none()
        if condominio is None:
            raise CondominioNoExisteException(request.condominio_id)

        resultado_rol = await session.execute(
            select(UsuarioRol).where(
                UsuarioRol.usuario_id == request.usuario_id,
                UsuarioRol.condominio_id == request.condominio_id,
            )
        )
        if resultado_rol.scalar_one_or_none() is not None:
            raise RolYaAsignadoException(request.usuario_id, request.condominio_id)

        usuario_rol = UsuarioRol(
            usuario_id=request.usuario_id,
            condominio_id=request.condominio_id,
            rol=request.rol.value,
        )
        session.add(usuario_rol)
        await session.flush()

        usuario_rol_dto = UsuarioRolDTO.model_validate(usuario_rol)

        audit_log = AuditoriaPayload(
            condominio_id=str(request.condominio_id),
            departamento_id="CONDOMINIO_GENERAL",
            accion_ejecutada="ASIGNACION_ROL_USUARIO",
            motivo=f"Asignación del rol '{request.rol.value}' en el condominio '{condominio.nombre}' (matriz RBAC DOM-05).",
            resultado="EXITOSO",
            actor_tipo="ADMINISTRADOR",
            actor_id=str(request.usuario_id),
            estado_anterior={"rol": None},
            estado_posterior={
                "usuario_rol_id": str(usuario_rol_dto.id),
                "rol": usuario_rol_dto.rol.value,
                "email": usuario.email,
                "condominio": condominio.nombre,
            },
        )

        return usuario_rol_dto, audit_log
