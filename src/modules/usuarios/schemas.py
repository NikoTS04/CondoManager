"""Esquemas Pydantic v2 para el Dominio de Usuarios y RBAC (Junta Directiva - PROC-05).

Define los contratos DTO de alta de usuario y asignación de roles contextuales por condominio,
alineados con specs/05-api/api-contracts.md y specs/03-contracts/openapi/condomanager.openapi.yaml.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RolEnum(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN_JUNTA = "ADMIN_JUNTA"
    AUDITOR = "AUDITOR"
    RESIDENTE = "RESIDENTE"


class CrearUsuarioRequest(BaseModel):
    email: str = Field(
        ...,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        json_schema_extra={"example": "residente101@gmail.com"},
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Contraseña en texto plano; se persiste únicamente como hash irreversible.",
    )
    nombre: str = Field(..., min_length=2, max_length=80)
    apellido: str = Field(..., min_length=2, max_length=80)
    documento_identidad: str = Field(
        ...,
        min_length=6,
        max_length=20,
        description="DNI o Carnet de Extranjería del solicitante (PROC-05, regla 4.1).",
        json_schema_extra={"example": "74125896"},
    )
    telefono: str | None = Field(None, max_length=20)


class UsuarioDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    apellido: str
    telefono: str | None = None
    documento_identidad: str
    esta_activo: bool = True
    creado_en: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AsignarRolRequest(BaseModel):
    usuario_id: uuid.UUID
    condominio_id: uuid.UUID
    rol: RolEnum = Field(
        default=RolEnum.RESIDENTE,
        description="Rol contextual del usuario dentro del condominio (matriz RBAC de DOM-05).",
    )


class UsuarioRolDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    condominio_id: uuid.UUID
    rol: RolEnum
