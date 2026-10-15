"""Contratos de configuración de la distribución."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MetodoDistribucion(StrEnum):
    POR_ALICUOTA = "POR_ALICUOTA"
    EQUITATIVA = "EQUITATIVA"


class ConfigurarDistribucionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metodo: MetodoDistribucion


class DistribucionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    metodo: MetodoDistribucion
    actualizado_por: str
    actualizado_en: datetime
