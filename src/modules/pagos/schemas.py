"""Esquemas Pydantic para el Dominio de Pagos, Conciliación y Moras (Tarqui - PROC-02).

Alineados formalmente con OpenAPI 3.1: specs/03-contracts/openapi/condomanager.openapi.yaml
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import UploadFile
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class ReportarPagoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    departamento_id: uuid.UUID
    banco: str = Field(..., min_length=1, max_length=50, json_schema_extra={"example": "YAPE"})
    numero_operacion: str = Field(
        ..., min_length=1, max_length=50, json_schema_extra={"example": "098412"}
    )
    fecha_operacion: date = Field(..., json_schema_extra={"example": "2026-10-15"})
    monto: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        json_schema_extra={"example": "150.00"},
    )

    @field_validator("monto", mode="before")
    @classmethod
    def monto_decimal(cls, valor):
        import re

        if isinstance(valor, str) and not re.fullmatch(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}", valor):
            raise ValueError("Use un importe de dos decimales sin notación exponencial")
        if not isinstance(valor, (str, Decimal)):
            raise ValueError("Use una cadena decimal")
        return valor

    @field_validator("banco")
    @classmethod
    def banco_canonico(cls, valor: str) -> str:
        banco = "".join(valor.split()).upper()
        if banco not in {"YAPE", "PLIN", "BCP", "INTERBANK", "BBVA", "SCOTIABANK"}:
            raise ValueError("Banco no permitido")
        return banco

    @field_validator("numero_operacion")
    @classmethod
    def operacion_no_vacia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("Indique el número de operación")
        return "".join(valor.split()).lstrip("0") or "0"


class ReportarPagoFormulario(ReportarPagoRequest):
    archivo_voucher: UploadFile


class SubsanarVoucherRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archivo_voucher: UploadFile


class RespuestaMonetaria(BaseModel):
    @field_serializer(
        "monto",
        "monto_imputado",
        "nuevo_saldo_departamento",
        "saldo_a_favor_generado",
        check_fields=False,
        when_used="json",
    )
    def dinero(self, valor: Decimal):
        return f"{valor:.2f}"


class ComprobanteRecibidoResponse(BaseModel):
    comprobante_id: uuid.UUID
    estado: Literal["EN_REVISION"] = "EN_REVISION"
    mensaje: str = "Comprobante recibido. En proceso de conciliación por la Junta Directiva."
    idempotency_hash: str
    codigo: Literal["COMPROBANTE_RECIBIDO", "VOUCHER_EN_EVALUACION"] = "COMPROBANTE_RECIBIDO"


class ComprobantePagoDTO(RespuestaMonetaria):
    id: uuid.UUID
    departamento_id: uuid.UUID
    banco: str
    numero_operacion: str
    fecha_operacion: date
    monto: Decimal
    estado: Literal["EN_REVISION", "APROBADO", "OBSERVADO", "RECHAZADO"]
    idempotency_hash: str
    url_voucher: str
    motivo_rechazo: Optional[str] = None


class ConciliarPagoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(
        ..., pattern=r"^(APROBADO|RECHAZADO|OBSERVADO)$", json_schema_extra={"example": "APROBADO"}
    )
    motivo_rechazo: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    notas_internas: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def motivo_publico(self):
        if self.decision != "APROBADO" and not (self.motivo_rechazo or "").strip():
            raise ValueError("Indique el motivo público de observación o rechazo")
        return self


class ConciliacionResultResponse(RespuestaMonetaria):
    comprobante_id: uuid.UUID
    estado_final: str
    monto_imputado: Decimal
    nuevo_saldo_departamento: Decimal
    saldo_a_favor_generado: Decimal
    departamento_habilitado_reservas: bool
    motivo_rechazo: Optional[str] = None


class SolvenciaResponse(BaseModel):
    departamento_id: uuid.UUID
    saldo_vencido: Decimal
    habilitado_reservas: bool


class EvaluarMorasRequest(BaseModel):
    condominio_id: uuid.UUID
    fecha_corte: date = Field(default_factory=date.today)


class EvaluarMorasResponse(BaseModel):
    cuotas_evaluadas: int
    moras_aplicadas: int
    cuotas_postergadas_por_revision: int
    monto_total_moras: Decimal
