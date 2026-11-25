from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Urgencia(StrEnum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


Categoria = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00]+$"),
]


class CrearIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departamento_id: UUID
    ubicacion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    categoria: Categoria
    descripcion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    urgencia: Urgencia
    evidencia: UploadFile | None = None


class ReporteIncidenciaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    departamento_id: UUID
    ubicacion: str
    categoria: str
    descripcion: str
    urgencia: Urgencia
    creado_en: datetime
    tiene_evidencia: bool


class RegistroIncidenciaDTO(ReporteIncidenciaDTO):
    estado: Literal["REGISTRADO"] = "REGISTRADO"
    advertencia_evidencia: str | None = None


class IncidenciaDTO(ReporteIncidenciaDTO):
    estado: Literal["REGISTRADO", "RECHAZADO"]
    categoria_confirmada: str | None
    prioridad: Urgencia | None
    motivo_rechazo: str | None
    version: int


class BandejaIncidenciasDTO(BaseModel):
    items: list[IncidenciaDTO]
    hay_mas: bool


class RevisionIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]


class ClasificarIncidencia(RevisionIncidencia):
    accion: Literal["CLASIFICAR"]
    categoria: Categoria
    prioridad: Urgencia


class RechazarIncidencia(RevisionIncidencia):
    accion: Literal["RECHAZAR"]
    motivo: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]+$"
        ),
    ]


RevisarIncidencia = Annotated[
    ClasificarIncidencia | RechazarIncidencia, Field(discriminator="accion")
]
