"""Contratos Pydantic de persistencia para CON-51/52 (aún sin endpoints)."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

MONTO_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,9})\.[0-9]{2}$")


def decimal_cadena(value: object) -> object:
    if not isinstance(value, str) or MONTO_PATTERN.fullmatch(value) is None:
        raise ValueError("El importe debe ser una cadena decimal con exactamente dos posiciones.")
    return value


DineroCadena = Annotated[
    Decimal, BeforeValidator(decimal_cadena), Field(max_digits=12, decimal_places=2)
]
DineroPositivo = Annotated[DineroCadena, Field(gt=Decimal("0.00"))]
DineroNoNegativo = Annotated[DineroCadena, Field(ge=Decimal("0.00"))]
TextoNoVacio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Moneda = Literal["PEN", "USD"]
EstadoEgreso = Literal[
    "BORRADOR",
    "PENDIENTE_APROBACION",
    "APROBADO",
    "RECHAZADO",
    "PAGO_PARCIAL",
    "PAGADO",
    "CANCELADO",
]
DecisionAprobacion = Literal["APROBAR", "RECHAZAR"]


class CrearEgresoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    concepto_id: UUID
    proveedor_id: UUID | None = None
    contrato_id: UUID | None = None
    presupuesto_id: UUID | None = None
    item_presupuesto_id: UUID | None = None
    descripcion: TextoNoVacio = Field(max_length=500)
    justificacion: TextoNoVacio = Field(max_length=2000)
    moneda: Moneda
    fecha_gasto: date
    monto_pactado: DineroPositivo | None = None
    monto_solicitado: DineroPositivo

    @model_validator(mode="after")
    def validar_referencias(self):
        if (self.presupuesto_id is None) != (self.item_presupuesto_id is None):
            raise ValueError("presupuesto_id e item_presupuesto_id deben enviarse juntos.")
        return self


class ActualizarEgresoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version_esperada: int = Field(ge=1, strict=True)
    concepto_id: UUID | None = None
    proveedor_id: UUID | None = None
    contrato_id: UUID | None = None
    presupuesto_id: UUID | None = None
    item_presupuesto_id: UUID | None = None
    descripcion: TextoNoVacio | None = Field(default=None, max_length=500)
    justificacion: TextoNoVacio | None = Field(default=None, max_length=2000)
    fecha_gasto: date | None = None
    monto_pactado: DineroPositivo | None = None
    monto_solicitado: DineroPositivo | None = None

    @model_validator(mode="after")
    def validar_parcial_referencias(self):
        campos = self.model_fields_set
        if (
            "contrato_id" in campos
            and self.contrato_id is not None
            and "proveedor_id" in campos
            and self.proveedor_id is None
        ):
            raise ValueError("Un contrato asociado requiere proveedor_id en la actualización.")
        presupuesto_cambiado = "presupuesto_id" in campos
        item_cambiado = "item_presupuesto_id" in campos
        if presupuesto_cambiado != item_cambiado or (
            presupuesto_cambiado
            and (self.presupuesto_id is None) != (self.item_presupuesto_id is None)
        ):
            raise ValueError("presupuesto_id e item_presupuesto_id deben enviarse juntos.")
        return self


class RegistrarAprobacionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: DecisionAprobacion
    version_esperada: int = Field(ge=1, strict=True)
    motivo: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def motivo_obligatorio_al_rechazar(self):
        if self.decision == "RECHAZAR" and not (self.motivo or "").strip():
            raise ValueError("Rechazar un egreso requiere un motivo.")
        return self


class ConfigurarAprobacionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    umbral: DineroNoNegativo
    pagos_parciales_habilitados: bool = False
    version_esperada: int = Field(ge=1, strict=True)


class RegistrarAperturaCajaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cuenta_referencia: TextoNoVacio = Field(max_length=100)
    moneda: Moneda
    saldo: DineroNoNegativo
    fecha_corte: date
    referencia: TextoNoVacio = Field(max_length=200)
    documento_id: UUID


class ConfirmarPagoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cuenta_id: UUID
    monto: DineroPositivo
    fecha_pago: date
    referencia: TextoNoVacio = Field(max_length=200)
    documento_id: UUID


class RegistrarIntentoPagoFallidoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cuenta_id: UUID
    monto: DineroPositivo
    fecha_pago: date
    referencia: TextoNoVacio = Field(max_length=200)
    motivo: TextoNoVacio = Field(max_length=2000)
    documento_id: UUID | None = None


class RevertirPagoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: TextoNoVacio = Field(max_length=2000)


class DocumentoFinancieroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    egreso_id: UUID | None
    tipo: Literal["SUSTENTO", "EVIDENCIA_PAGO", "APERTURA_CAJA"]
    archivo_nombre: str
    mime: str
    tamano_bytes: int
    sha256: str
    creado_por: UUID
    creado_en: datetime


class ProveedorResumenResponse(BaseModel):
    """Proyección mínima del futuro adapter CON-48; no modela ni suplanta proveedor."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    condominio_id: UUID
    ruc: str
    razon_social: str
    activo: bool


class AprobacionEgresoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    egreso_id: UUID
    version_egreso: int
    monto_revisado: Decimal
    decision: DecisionAprobacion
    motivo: str | None
    vigente: bool
    actor_id: UUID
    creado_en: datetime


class PagoEgresoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    egreso_id: UUID
    cuenta_id: UUID
    monto: Decimal
    fecha_pago: date
    referencia: str
    documento_id: UUID | None
    estado: Literal["CONFIRMADO", "FALLIDO", "REVERSADO"]
    actor_id: UUID
    movimiento_caja_id: UUID | None
    creado_en: datetime


class EgresoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    condominio_id: UUID
    concepto_id: UUID
    concepto_codigo: str
    categoria: str
    proveedor_id: UUID | None
    contrato_id: UUID | None
    proveedor: ProveedorResumenResponse | None
    presupuesto_id: UUID | None
    item_presupuesto_id: UUID | None
    descripcion: str
    justificacion: str
    moneda: Moneda
    fecha_gasto: date
    monto_pactado: Decimal | None
    monto_solicitado: Decimal
    monto_aprobado: Decimal | None
    monto_pagado: Decimal
    estado: EstadoEgreso
    version: int
    creado_por: UUID
    creado_en: datetime
    actualizado_en: datetime
    documentos: list[DocumentoFinancieroResponse] = Field(default_factory=list)
    aprobaciones: list[AprobacionEgresoResponse] = Field(default_factory=list)
    pagos: list[PagoEgresoResponse] = Field(default_factory=list)


class EgresoListaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EgresoResponse]
    hay_mas: bool


class ErrorPersistenciaEgresos(BaseModel):
    """Forma estándar usada por routers futuros; no incluye detalles sensibles."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    mensaje: str
    detalles: dict | None = None
