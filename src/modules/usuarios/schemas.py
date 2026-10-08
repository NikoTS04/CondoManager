"""Esquemas Pydantic para el Dominio de Usuarios y Autenticación (PROC-05)."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Solicitud de inicio de sesión con credenciales."""
    email: str = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., description="Contraseña en texto plano")


class UsuarioDTO(BaseModel):
    """Información pública y contexto del usuario."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre: str
    apellido: str
    rol: str = Field(..., description="SUPERADMIN, ADMIN_JUNTA, AUDITOR, PROPIETARIO, INQUILINO")
    condominio_id: str
    departamentos: List[str] = Field(default_factory=list, description="Lista de números de departamentos vinculados")
    tipo_relacion: Optional[str] = Field(default=None, description="PROPIETARIO_TITULAR, INQUILINO, ADMINISTRADOR")


class TokenResponse(BaseModel):
    """Respuesta con token JWT de acceso emitido."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=86400, description="Segundos de validez del token")
    usuario: UsuarioDTO


class UserContextResponse(BaseModel):
    """Contexto de sesión activo para el usuario autenticado."""
    id: str
    email: str
    nombre: str
    apellido: str
    rol: str
    condominio_id: str
    departamentos: List[str]
    tipo_relacion: Optional[str] = None
