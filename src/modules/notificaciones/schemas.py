"""Esquemas Pydantic v2 para el Dominio de Notificaciones (Alejandro - PROC-03).

Define los contratos DTO, enums de canales y estados, y modelos de bitácora de envíos.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CanalNotificacionEnum(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    PUSH = "PUSH"


class EstadoNotificacionEnum(str, Enum):
    EN_COLA = "EN_COLA"
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
    estado: EstadoNotificacionEnum = EstadoNotificacionEnum.EN_COLA
    intentos: int = Field(default=1, ge=1, le=4)
    proximo_reintento: Optional[datetime] = None
    proveedor_message_id: Optional[str] = None
    error_mensaje: Optional[str] = None
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_actualizacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DespacharNotificacionRequest(BaseModel):
    condominio_id: str
    departamento_id: str
    tipo_evento: str
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    destinatario: str
    contexto: Dict[str, Any]


class EnviarComunicadoMasivoRequest(BaseModel):
    condominio_id: str
    titulo: str = Field(..., min_length=5, max_length=150)
    mensaje: str = Field(..., min_length=10)
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    remitente: str = Field(default="Junta Directiva Villa Bonita 3")


class EnviarComunicadoMasivoResponse(BaseModel):
    condominio_id: str
    total_destinatarios: int
    notificaciones_generadas: int
    estado_general: str = "EN_COLA"


class ReenviarNotificacionRequest(BaseModel):
    nuevo_destinatario: Optional[str] = Field(
        None, description="Nuevo correo o teléfono si el anterior era erróneo o rebotó"
    )
