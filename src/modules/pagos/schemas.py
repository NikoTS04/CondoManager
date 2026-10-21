"""Esquemas Pydantic para el Dominio de Pagos, Conciliación y Moras (Tarqui - PROC-02).

Alineados formalmente con OpenAPI 3.1: specs/03-contracts/openapi/condomanager.openapi.yaml
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ReportarPagoRequest(BaseModel):
    departamento_id: uuid.UUID
    banco: str = Field(..., max_length=30, json_schema_extra={"example": "YAPE"})
    numero_operacion: str = Field(
        ..., min_length=4, max_length=50, json_schema_extra={"example": "098412"}
    )
    fecha_operacion: date = Field(..., json_schema_extra={"example": "2026-10-15"})
    monto: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        json_schema_extra={"example": "150.00"},
    )
    url_voucher: str = Field(
        ...,
        min_length=1,
        max_length=512,
        json_schema_extra={"example": "8ac169e4-3928-4e52-b75d-84a2781e44fa.jpg"},
    )

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
        return valor


class ComprobanteRecibidoResponse(BaseModel):
    comprobante_id: uuid.UUID
    estado: str = "EN_REVISION"
    mensaje: str = "Comprobante recibido. En proceso de conciliación por la Junta Directiva."
    idempotency_hash: str
    error_code: Optional[str] = None


class ComprobantePagoDTO(BaseModel):
    id: uuid.UUID
    departamento_id: uuid.UUID
    banco: str
    numero_operacion: str
    fecha_operacion: date
    monto: Decimal
    estado: str
    idempotency_hash: str
    url_voucher: str
    motivo_rechazo: Optional[str] = None


class ConciliarPagoRequest(BaseModel):
    decision: str = Field(
        ..., pattern=r"^(APROBADO|RECHAZADO|OBSERVADO)$", json_schema_extra={"example": "APROBADO"}
    )
    motivo_rechazo: Optional[str] = None
    notas_internas: Optional[str] = None


class ConciliacionResultResponse(BaseModel):
    comprobante_id: uuid.UUID
    estado_final: str
    monto_imputado: Decimal
    nuevo_saldo_departamento: Decimal
    saldo_a_favor_generado: Decimal
    departamento_habilitado_reservas: bool


class VoucherSubidoResponse(BaseModel):
    url_voucher: str
    content_type: str
    size_bytes: int


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
