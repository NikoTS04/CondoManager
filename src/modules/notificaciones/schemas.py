"""Esquemas Pydantic v2 para el Dominio de Notificaciones (Alejandro - PROC-03).

Define los contratos DTO, enums de canales y estados, y modelos de bitácora de envíos.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CanalNotificacionEnum(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    PUSH = "PUSH"


class EstadoNotificacionEnum(str, Enum):
    EN_COLA = "EN_COLA"
    ENVIADO = "ENVIADO"
    ENTREGADO = "ENTREGADO"
    REINTENTANDO = "REINTENTANDO"
    FALLIDO_PERMANENTE = "FALLIDO_PERMANENTE"


class NotificacionLogDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    condominio_id: str
    departamento_id: Optional[str] = None
    tipo_evento: str
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    destinatario: str
    asunto: Optional[str] = None
    cuerpo: str
    usuario_destinatario_id: Optional[uuid.UUID] = None
    evento_id: Optional[uuid.UUID] = None
    ciclo: int = Field(default=1, ge=1)
    transporte: Literal["SIMULADO", "PROVEEDOR"] = "SIMULADO"
    estado: EstadoNotificacionEnum = EstadoNotificacionEnum.EN_COLA
    intentos: int = Field(default=0, ge=0, le=4)
    proximo_reintento: Optional[datetime] = None
    proveedor_message_id: Optional[str] = None
    error_mensaje: Optional[str] = None
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_actualizacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DespacharNotificacionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condominio_id: str
    departamento_id: str
    tipo_evento: str
    canal: CanalNotificacionEnum
    destinatario: str = Field(min_length=1)
    contexto: Dict[str, Any]


class EnviarComunicadoMasivoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condominio_id: str
    titulo: str = Field(..., min_length=5, max_length=150)
    mensaje: str = Field(..., min_length=10)
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    remitente: str = Field(default="Junta Directiva", max_length=150)


class EnviarComunicadoMasivoResponse(BaseModel):
    condominio_id: str
    generadas: int = Field(ge=0)
    estado_general: Literal["EN_COLA"] = "EN_COLA"


class ReenviarNotificacionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nuevo_destinatario: Optional[str] = Field(
        None,
        min_length=1,
        description="Nuevo correo o teléfono si el anterior era erróneo o rebotó",
    )

    @field_validator("nuevo_destinatario")
    @classmethod
    def contacto_no_nulo(cls, valor):
        if valor is None:
            raise ValueError("Omita el campo o indique un contacto")
        return valor
