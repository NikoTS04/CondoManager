"""Esquemas Pydantic para el Dominio de Usuarios y Autenticación (PROC-05)."""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.roles import RolUsuario, TipoRelacion


class LoginRequest(BaseModel):
    """Solicitud de inicio de sesión con credenciales."""
    email: str = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., description="Contraseña en texto plano")


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
    numero: str
    piso: int
    coeficiente: Decimal
    saldo_a_favor: Decimal
    estado_financiero: str
    activo: bool
    deuda_vencida: Decimal


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
