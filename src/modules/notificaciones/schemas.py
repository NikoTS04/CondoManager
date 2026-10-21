"""Esquemas Pydantic v2 para el Dominio de Notificaciones (Alejandro - PROC-03).

Define los contratos DTO, enums de canales, estados, orígenes, historial de
intentos y alertas administrativas.
"""

import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PATRON_SENSIBLE = re.compile(
    r"(password|secret|token|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def sanitizar_error_publico(valor: str | None) -> str | None:
    """Limpia credenciales o secretos accidentales antes de exponer errores por API."""
    if valor is None:
        return None
    limpio = _PATRON_SENSIBLE.sub("[REDACTED]", str(valor).strip())
    return limpio[:500] if limpio else None


class CanalNotificacionEnum(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    PUSH = "PUSH"


class EstadoNotificacionEnum(str, Enum):
    EN_COLA = "EN_COLA"
    REINTENTANDO = "REINTENTANDO"
    ENVIADO = "ENVIADO"
    ENTREGADO = "ENTREGADO"
    FALLIDO_PERMANENTE = "FALLIDO_PERMANENTE"


class OrigenNotificacionEnum(str, Enum):
    CUOTA = "CUOTA"
    COMPROBANTE = "COMPROBANTE"
    RESERVA = "RESERVA"
    COMUNICADO = "COMUNICADO"
    USUARIO = "USUARIO"


class ResultadoIntentoEnum(str, Enum):
    ACEPTADO = "ACEPTADO"
    FALLO_TEMPORAL = "FALLO_TEMPORAL"
    FALLO_DEFINITIVO = "FALLO_DEFINITIVO"


class SeveridadAlertaEnum(str, Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class NotificacionIntentoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notificacion_id: uuid.UUID
    ciclo: int = Field(default=1, ge=1)
    numero: int = Field(ge=1, le=4)
    worker_id: str
    transporte: str
    transporte_simulado: bool
    resultado: ResultadoIntentoEnum
    codigo: str | None = None
    detalle: str | None = None
    proveedor_message_id: str | None = None
    iniciado_en: datetime
    finalizado_en: datetime

    @field_validator("detalle", mode="before")
    @classmethod
    def _limpiar_detalle(cls, v: Any) -> str | None:
        return sanitizar_error_publico(v)


class NotificacionLogDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    condominio_id: str
    departamento_id: str | None = None
    usuario_id: str | None = None
    evento_id: str | None = None
    tipo_evento: str
    plantilla: str | None = None
    origen_tipo: str | None = None
    origen_id: str | None = None
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    destinatario: str
    asunto: str | None = None
    cuerpo: str
    estado: EstadoNotificacionEnum = EstadoNotificacionEnum.EN_COLA
    intentos: int = Field(default=0, ge=0, le=4)
    ciclo: int = Field(default=1, ge=1)
    proximo_intento_en: datetime | None = None
    transporte: str | None = None
    transporte_simulado: bool | None = None
    proveedor_message_id: str | None = None
    error_codigo: str | None = None
    error_mensaje: str | None = None
    aceptado_en: datetime | None = None
    entregado_en: datetime | None = None
    creado_en: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actualizado_en: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "condominio_id",
        "departamento_id",
        "usuario_id",
        "evento_id",
        "origen_id",
        mode="before",
    )
    @classmethod
    def _uuid_a_str(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)

    @field_validator("error_mensaje", mode="before")
    @classmethod
    def _limpiar_error(cls, v: Any) -> str | None:
        return sanitizar_error_publico(v)


class NotificacionDetalleDTO(NotificacionLogDTO):
    historial_intentos: list[NotificacionIntentoDTO] = Field(default_factory=list)


class AlertaAdministrativaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condominio_id: str
    notificacion_id: uuid.UUID
    tipo: str
    severidad: SeveridadAlertaEnum
    mensaje: str
    creado_en: datetime
    atendida_en: datetime | None = None
    atendida_por: str | None = None

    @field_validator("condominio_id", "atendida_por", mode="before")
    @classmethod
    def _uuid_a_str(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)


class EnviarComunicadoMasivoRequest(BaseModel):
    id: uuid.UUID | None = Field(
        default=None,
        description="Identificador opcional del comunicado para garantizar idempotencia",
    )
    comunicado_id: uuid.UUID | None = Field(
        default=None,
        description="Alias opcional del identificador del comunicado para idempotencia",
    )
    condominio_id: str
    titulo: str = Field(..., min_length=5, max_length=150)
    mensaje: str = Field(..., min_length=10)
    canal: CanalNotificacionEnum = CanalNotificacionEnum.EMAIL
    remitente: str = Field(default="Junta Directiva Villa Bonita 3")


class EnviarComunicadoMasivoResponse(BaseModel):
    comunicado_id: uuid.UUID | None = None
    condominio_id: str
    total_destinatarios: int
    notificaciones_generadas: int
    estado_general: str = "EN_COLA"


class ReenviarNotificacionRequest(BaseModel):
    nuevo_destinatario: str | None = Field(
        None,
        description="Nuevo correo o teléfono si el anterior era erróneo o rebotó",
    )
