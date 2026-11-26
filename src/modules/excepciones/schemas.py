from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Accion = Literal["REENVIAR_CORREO", "CERRAR_CON_MOTIVO", "REINTENTAR_JOB", "SOLICITAR_INFORMACION"]
Estado = Literal["ABIERTA", "EN_PROCESO", "PENDIENTE_INFORMACION", "RESUELTA", "FALLIDA"]


class SolicitudResolucion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accion: Accion
    motivo: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\x00]+$"
        ),
    ]
    nuevo_destinatario: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, min_length=1, max_length=320, pattern=r"^[^\x00]+$"
            ),
        ]
        | None
    ) = None
    responsable: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\x00]+$"
            ),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def datos_segun_accion(self):
        if (self.accion == "REENVIAR_CORREO") != (self.nuevo_destinatario is not None):
            raise ValueError("El contacto corregido se requiere únicamente para reenviar.")
        if (self.accion == "SOLICITAR_INFORMACION") != (self.responsable is not None):
            raise ValueError("Indique a la persona o equipo responsable de responder.")
        return self


class ExcepcionDTO(BaseModel):
    id: UUID
    origen: Literal["CORREO", "JOB"]
    operacion_id: str
    causa: str
    prioridad: Literal["ALTA", "MEDIA"]
    estado: Estado
    creada_en: datetime


class EfectoCorreo(BaseModel):
    operacion_id: str
    ciclo: int
    estado_operacion: str


class EfectoJob(BaseModel):
    operacion_id: str
    intento_id: UUID | None
    estado_operacion: str
    responsable: str | None


class EfectoJobHistorico(BaseModel):
    nombre: str
    estado_proceso: str
    reintentado: bool


class EfectoCierre(BaseModel):
    operacion_id: str
    estado_operacion: str


class ResolucionDTO(BaseModel):
    id: UUID
    accion: Accion
    motivo: str
    actor_id: str
    fecha: datetime
    estado: Estado
    efecto: EfectoCorreo | EfectoJob | EfectoJobHistorico | EfectoCierre


class EvidenciaDTO(BaseModel):
    tipo_evento: str
    ciclo_fallido: int
    ciclo_actual: int
    estado_operacion: str
    origen: Literal["CORREO", "JOB"]
    operacion_id: str
    referencia_correlacion: str | None
    intento_id: UUID | None = None
    detalle: dict[str, Any]


class DetalleExcepcionDTO(ExcepcionDTO):
    evidencia: EvidenciaDTO
    historial: list[ResolucionDTO]
    acciones_permitidas: list[Accion]
    requiere_revision_correo: bool


class PaginaExcepcionesDTO(BaseModel):
    items: list[ExcepcionDTO]
    hay_mas: bool
