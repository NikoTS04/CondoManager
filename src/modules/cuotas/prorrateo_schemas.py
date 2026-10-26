"""Entradas del catálogo y del detalle mensual, sin totales editables calculados."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


def dinero_cadena(value):
    import re

    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}", value):
        raise ValueError("Envíe dinero como cadena decimal no negativa de dos posiciones.")
    return value


Dinero = Annotated[Decimal, BeforeValidator(dinero_cadena), Field(ge=0, max_digits=12, decimal_places=2)]
Categoria = Literal["SERVICIOS_BASICOS", "MANTENIMIENTO_PREVENTIVO", "SEGURIDAD_Y_VIGILANCIA",
                    "LIMPIEZA_Y_JARDINERIA", "GASTOS_ADMINISTRATIVOS", "IMPREVISTOS_Y_CONTINGENCIAS",
                    "OBLIGACIONES_FINANCIADAS"]


def texto_admitido(value):
    if isinstance(value, str) and any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValueError("No se admiten caracteres de control en el reporte.")
    return value


class ConceptoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(pattern=r"^[A-Z][A-Z0-9-]{1,29}$")
    categoria: Categoria
    descripcion: str = Field(min_length=1, max_length=500)

    @field_validator("*", mode="before")
    @classmethod
    def validar_texto(cls, value):
        return texto_admitido(value)

    @field_validator("descripcion")
    @classmethod
    def descripcion_no_vacia(cls, value):
        if not value.strip():
            raise ValueError("La descripción no puede estar vacía.")
        return value.strip()


class ConceptoResponse(ConceptoRequest):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    condominio_id: UUID
    activo: bool


class ItemPresupuesto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    concepto_id: UUID
    descripcion: str = Field(default="", max_length=1000)
    seccion: Literal["AACC", "EDIFICIO", "CRONOGRAMA_AACC"]
    tipo_movimiento: Literal["CARGO", "ABONO"] = "CARGO"
    monto_periodo: Dinero
    monto_cubierto_moras: Dinero = Decimal("0.00")
    metodo_asignacion: Literal["POR_PISOS", "DIRECTO_EDIFICIO", "ASIGNACION_EXPLICITA"] = "POR_PISOS"
    metodo_unitario: Literal["EQUITATIVA", "POR_ALICUOTA"] = "EQUITATIVA"
    edificio_id: UUID | None = None
    asignaciones_explicitas: dict[UUID, Dinero] = Field(default_factory=dict)
    motivo_asignacion: str = Field(default="", max_length=1000)
    codigo_origen: str = Field(default="", max_length=40)
    observacion_origen: str = Field(default="", max_length=1000)
    referencia_servicio: str = Field(default="", max_length=200)
    referencia_documento: str = Field(default="", max_length=500)
    monto_origen_condominio: str | None = Field(default=None, max_length=40)
    monto_origen_edificio: str | None = Field(default=None, max_length=40)
    monto_unitario_origen: str | None = Field(default=None, max_length=40)
    obligacion_referencia: str = Field(default="", max_length=500)
    numero_cuota: int | None = Field(default=None, ge=1, strict=True)
    total_cuotas: int | None = Field(default=None, ge=1, strict=True)
    monto_total_obligacion: Dinero | None = None

    @field_validator("*", mode="before")
    @classmethod
    def validar_texto(cls, value):
        return texto_admitido(value)

    @model_validator(mode="after")
    def validar_asignacion(self):
        if self.monto_cubierto_moras != 0:
            raise ValueError("La cobertura requiere fondos de moras conciliados aún no integrados.")
        if (self.metodo_asignacion == "DIRECTO_EDIFICIO") != (self.edificio_id is not None):
            raise ValueError("Solo DIRECTO_EDIFICIO exige edificio_id.")
        if self.metodo_asignacion == "ASIGNACION_EXPLICITA":
            if not self.asignaciones_explicitas or not self.motivo_asignacion.strip() or not self.referencia_documento.strip():
                raise ValueError("La asignación explícita requiere importes, motivo y documento.")
            if sum(self.asignaciones_explicitas.values()) != self.monto_periodo:
                raise ValueError("Las asignaciones deben sumar el importe del periodo.")
        elif self.asignaciones_explicitas:
            raise ValueError("No mezcle asignaciones explícitas con otros métodos.")
        financiacion = (self.numero_cuota, self.total_cuotas, self.monto_total_obligacion)
        if any(v is not None for v in financiacion):
            if any(v is None for v in financiacion) or not self.obligacion_referencia.strip():
                raise ValueError("Complete referencia, cuota, total de cuotas y obligación total.")
            if self.numero_cuota > self.total_cuotas or self.monto_periodo > self.monto_total_obligacion:
                raise ValueError("Cronograma de financiación inválido.")
        return self
