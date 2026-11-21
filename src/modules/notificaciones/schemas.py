"""Esquemas Pydantic v2 para el Dominio de Notificaciones (Alejandro - PROC-03).

Define los contratos DTO, enums de canales y estados, y modelos de bitácora de envíos.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, Literal, Optional

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
    OMITIDO = "OMITIDO"


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


class PrevisualizarComunicado(EnviarComunicadoMasivoRequest):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    condominio_id: uuid.UUID
    canal: Literal["EMAIL"] = "EMAIL"
    edificio_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    departamento_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    usuario_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    mensaje: str = Field(min_length=10, max_length=20000)


class ConfiguracionNotificaciones(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dias: list[Annotated[int, Field(ge=0, le=30, strict=True)]] = Field(
        default_factory=lambda: [3, 0], min_length=1, max_length=10
    )
    hora: int = Field(default=8, ge=0, le=23, strict=True)
    habilitado: bool = True

    @field_validator("dias")
    @classmethod
    def dias_unicos(cls, dias):
        if len(set(dias)) != len(dias):
            raise ValueError("No repita días")
        return sorted(dias, reverse=True)


class ReactivarContacto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    motivo: str = Field(min_length=10, max_length=500)


class ResolverIncierto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    ciclo: int = Field(ge=1)
    intento: int = Field(ge=1, le=4)
    decision: Literal["ACEPTADO", "NO_ACEPTADO", "DESCARTAR"]
    referencia: str = Field(min_length=10, max_length=500)
    message_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,30}$")
    confirmar_no_aceptado: bool = False


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


class TipoAlertaEnum(str, Enum):
    ERROR_DEFINITIVO = "ERROR_DEFINITIVO"
    INTENTOS_AGOTADOS = "INTENTOS_AGOTADOS"
    ACEPTACION_INCIERTA = "ACEPTACION_INCIERTA"
    DESTINATARIO_INVALIDO = "DESTINATARIO_INVALIDO"
    PROVEEDOR_NO_CONFIGURADO = "PROVEEDOR_NO_CONFIGURADO"


class EstadoAlertaEnum(str, Enum):
    ABIERTA = "ABIERTA"
    ATENDIDA = "ATENDIDA"


class AlertaNotificacionDTO(BaseModel):
    id: uuid.UUID
    notificacion_id: uuid.UUID
    condominio_id: str
    departamento_id: str | None
    departamento_numero: str
    tipo_evento: str
    ciclo: int = Field(ge=1)
    tipo: TipoAlertaEnum
    mensaje: str
    estado: EstadoAlertaEnum
    creada_en: datetime
    atendida_en: Optional[datetime] = None
    atendida_por: Optional[uuid.UUID] = None
