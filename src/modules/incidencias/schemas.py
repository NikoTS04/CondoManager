from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, StringConstraints


class Urgencia(StrEnum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


class CrearIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departamento_id: UUID
    ubicacion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    categoria: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    descripcion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    urgencia: Urgencia
    evidencia: UploadFile | None = None


class IncidenciaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    departamento_id: UUID
    ubicacion: str
    categoria: str
    descripcion: str
    urgencia: Urgencia
    estado: str
    creado_en: datetime
    tiene_evidencia: bool


class RegistroIncidenciaDTO(IncidenciaDTO):
    advertencia_evidencia: str | None = None
