"""Esquemas Pydantic para Proveedores y Contratos (CON-48, CON-49)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TipoDocumentoContrato = Literal[
    "CONTRATO_SERVICIO", "POLIZA_SEGURO", "ADDENDA", "ACTA_CONFORMIDAD"
]

EstadoContrato = Literal[
    "VIGENTE", "POR_VENCER", "VENCIDO", "RENOVADO", "CANCELADO"
]

PATRON_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CrearProveedorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ruc: str = Field(..., pattern=r"^\d{11}$", description="RUC peruano de 11 dígitos")
    razon_social: str = Field(..., min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=200)
    rubro: str = Field(..., min_length=2, max_length=100)
    contacto_nombre: str = Field(..., min_length=2, max_length=150)
    contacto_telefono: str = Field(..., min_length=5, max_length=50)
    contacto_email: str = Field(..., max_length=120, pattern=PATRON_EMAIL)
    direccion: str | None = Field(default=None, max_length=300)
    notas: str | None = Field(default=None, max_length=1000)

    @field_validator("ruc")
    @classmethod
    def validar_ruc(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 11:
            raise ValueError("El RUC debe tener exactamente 11 dígitos numéricos.")
        return value


class ActualizarProveedorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    razon_social: str | None = Field(default=None, min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=200)
    rubro: str | None = Field(default=None, min_length=2, max_length=100)
    contacto_nombre: str | None = Field(default=None, min_length=2, max_length=150)
    contacto_telefono: str | None = Field(default=None, min_length=5, max_length=50)
    contacto_email: str | None = Field(default=None, max_length=120, pattern=PATRON_EMAIL)
    direccion: str | None = Field(default=None, max_length=300)
    activo: bool | None = Field(default=None)
    notas: str | None = Field(default=None, max_length=1000)


class ProveedorDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    ruc: str
    razon_social: str
    nombre_comercial: str | None
    rubro: str
    contacto_nombre: str
    contacto_telefono: str
    contacto_email: str
    direccion: str | None
    activo: bool
    notas: str | None
    version: int
    creado_en: datetime
    actualizado_en: datetime


class ProveedorDetalleDTO(ProveedorDTO):
    total_contratos: int = 0
    contratos_vigentes: int = 0
    egresos_vinculados: int = 0
    incidencias_vinculadas: int = 0


# CONTRATOS (CON-49)

class CrearContratoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    numero_contrato: str = Field(..., min_length=1, max_length=100)
    tipo_documento: TipoDocumentoContrato = Field(default="CONTRATO_SERVICIO")
    descripcion: str = Field(..., min_length=3, max_length=1000)
    monto_mensual: Decimal | None = Field(default=None, ge=Decimal("0.00"), decimal_places=2)
    moneda: Literal["PEN", "USD"] = Field(default="PEN")
    fecha_inicio: date = Field(...)
    fecha_fin: date = Field(...)
    contacto_emergencia: str | None = Field(default=None, max_length=150)
    contacto_emergencia_telefono: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio.")
        return self


class ActualizarContratoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    descripcion: str | None = Field(default=None, min_length=3, max_length=1000)
    monto_mensual: Decimal | None = Field(default=None, ge=Decimal("0.00"), decimal_places=2)
    fecha_fin: date | None = Field(default=None)
    contacto_emergencia: str | None = Field(default=None, max_length=150)
    contacto_emergencia_telefono: str | None = Field(default=None, max_length=50)
    estado: EstadoContrato | None = Field(default=None)


class DocumentoVersionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contrato_id: UUID
    version: int
    archivo_nombre: str
    archivo_mime: str
    archivo_tamano_bytes: int
    hash_sha256: str
    motivo_reemplazo: str | None
    subido_por: UUID
    subido_en: datetime


class ContratoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    proveedor_id: UUID
    numero_contrato: str
    tipo_documento: str
    descripcion: str
    monto_mensual: Decimal | None
    moneda: str
    fecha_inicio: date
    fecha_fin: date
    contacto_emergencia: str | None
    contacto_emergencia_telefono: str | None
    estado: str
    version_actual: int
    dias_restantes: int = 0
    tiene_documento: bool = False
    creado_en: datetime
    actualizado_en: datetime


class ContratoDetalleDTO(ContratoDTO):
    proveedor_ruc: str
    proveedor_razon_social: str
    versiones: list[DocumentoVersionDTO] = []
