"""Contratos públicos de CON-3; los coeficientes viajan como texto decimal."""

import re
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator


class CrearEdificioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre_bloque: str = Field(min_length=1, max_length=100)
    total_pisos: int = Field(strict=True, ge=1, le=32767)

    @field_validator("nombre_bloque", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        if isinstance(valor, str) and "\x00" in valor:
            raise ValueError("El nombre no puede contener caracteres nulos.")
        return valor.strip() if isinstance(valor, str) else valor


class CrearDepartamentoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero: str = Field(min_length=1, max_length=20)
    piso: int = Field(strict=True, ge=1, le=32767)
    coeficiente_participacion: Decimal = Field(
        gt=Decimal("0"), le=Decimal("100"), max_digits=7, decimal_places=4
    )

    @field_validator("numero", mode="before")
    @classmethod
    def limpiar_numero(cls, valor):
        if isinstance(valor, str) and "\x00" in valor:
            raise ValueError("El número no puede contener caracteres nulos.")
        return valor.strip().upper() if isinstance(valor, str) else valor

    @field_validator("coeficiente_participacion", mode="before")
    @classmethod
    def exigir_cadena(cls, valor):
        if not isinstance(valor, str) or not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,4})?", valor):
            raise ValueError("Use una cadena decimal positiva con hasta cuatro decimales.")
        return Decimal(valor)


class EstadoDepartamentoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activo: StrictBool


class EdificioResponse(CrearEdificioRequest):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    condominio_id: UUID


class DepartamentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    edificio_id: UUID
    numero: str
    piso: int
    coeficiente_participacion: Decimal
    saldo_a_favor: Decimal
    estado_financiero: str
    activo: bool

    @field_serializer("coeficiente_participacion")
    def coeficiente_texto(self, valor):
        return f"{valor:.4f}"

    @field_serializer("saldo_a_favor")
    def saldo_texto(self, valor):
        return f"{valor:.2f}"


class FilaImportacion(BaseModel):
    fila: int
    numero: str = ""
    piso: int | None = None
    edificio: str = ""
    coeficiente: str = ""
    total_pisos: int | None = None
    estado: Literal["NUEVA", "YA_EXISTENTE", "ERROR", "CREADA"] = "NUEVA"
    errores: list[str] = Field(default_factory=list)


class ImportacionResponse(BaseModel):
    total_filas: int
    nuevas: int
    creadas: int
    ya_existentes: int
    rechazadas: int
    filas: list[FilaImportacion]
