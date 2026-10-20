"""Esquemas Pydantic para el Dominio de Usuarios y Autenticación (PROC-05)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.core.roles import RolUsuario, TipoRelacion


class LoginRequest(BaseModel):
    """Solicitud de inicio de sesión con credenciales."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., max_length=120, description="Correo electrónico registrado")
    password: SecretStr = Field(..., max_length=128, description="Contraseña")
    condominio_id: UUID | None = None


class CrearUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=8, max_length=128)
    nombre: str = Field(min_length=1, max_length=80)
    apellido: str = Field(min_length=1, max_length=80)
    documento_identidad: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{5,19}$")
    telefono: str | None = Field(default=None, max_length=20)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("documento_identidad")
    @classmethod
    def normalizar_documento(cls, value: str) -> str:
        return value.upper()


class CambiarEstadoUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    esta_activo: bool = Field(strict=True)


class CuentaUsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    nombre: str
    apellido: str
    telefono: str | None
    documento_identidad: str
    esta_activo: bool
    creado_en: datetime


RolContextual = Literal["ADMIN_JUNTA", "AUDITOR", "RESIDENTE"]


class AsignarRolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: RolContextual


class AsignacionRolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario_id: UUID
    condominio_id: UUID
    rol: RolUsuario
    es_activo: bool


class CuentaUsuarioConRolResponse(CuentaUsuarioResponse):
    rol: RolUsuario
    rol_activo: bool
    es_superadmin: bool


class VinculoDepartamentoDTO(BaseModel):
    """La tenencia se resuelve por UUID de unidad, no por rol ni número."""

    model_config = ConfigDict(extra="forbid")

    departamento_id: UUID
    numero: str = Field(min_length=1)
    tipo_relacion: TipoRelacion
    es_activo: bool = True


class DepartamentoPortalDTO(BaseModel):
    id: UUID
    condominio_id: UUID
    edificio_id: UUID
    edificio_nombre: str
    numero: str
    piso: int
    coeficiente: Decimal
    saldo_a_favor: Decimal
    estado_financiero: str
    activo: bool
    deuda_vencida: Decimal


class AsignarVinculoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_relacion: TipoRelacion


class VinculoUsuarioResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    condominio_id: UUID
    departamento_id: UUID
    numero: str
    edificio_id: UUID
    edificio_nombre: str
    tipo_relacion: TipoRelacion
    es_activo: bool
    departamento_activo: bool


class UsuarioDTO(BaseModel):
    """Información pública y contexto del usuario."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre: str
    apellido: str
    rol: RolUsuario
    condominio_id: Optional[str]
    departamentos: List[VinculoDepartamentoDTO] = Field(default_factory=list)


class TokenResponse(BaseModel):
    """Respuesta con token JWT de acceso emitido."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=86400, description="Segundos de validez del token")
    usuario: UsuarioDTO


class UserContextResponse(UsuarioDTO):
    """Contexto de sesión activo para el usuario autenticado."""
