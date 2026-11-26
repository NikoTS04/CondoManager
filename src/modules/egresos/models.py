"""Modelos persistentes para CON-51/52.

Las referencias a proveedores/contratos son UUID sin FK física durante la etapa
de integración. Una migración descendiente añadirá las FKs tras incorporar
CON-48/49; no se definen modelos sustitutos de proveedor.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.modules.cuotas.presupuestos.models import ConceptoPresupuestal


class Egreso(Base):
    """Gasto administrativo solicitado; su creación no constituye un pago."""

    __tablename__ = "egresos"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    concepto_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conceptos_presupuestales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # UUID sin FK hasta integrar las tablas reales de CON-48/49.
    proveedor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    contrato_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    presupuesto_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presupuestos_mensuales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Los ítems del presupuesto viven en JSONB, no existe una tabla a la cual FK.
    item_presupuesto_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    justificacion: Mapped[str] = mapped_column(Text, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    fecha_gasto: Mapped[date] = mapped_column(Date, nullable=False)
    monto_pactado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    monto_solicitado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_aprobado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Caché transaccional; pagos y reversos son la fuente auditable del neto.
    monto_pagado: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BORRADOR", server_default="BORRADOR"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    creado_por: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    concepto: Mapped[ConceptoPresupuestal] = relationship()
    documentos: Mapped[list["DocumentoFinanciero"]] = relationship(
        back_populates="egreso", foreign_keys="DocumentoFinanciero.egreso_id"
    )
    aprobaciones: Mapped[list["AprobacionEgreso"]] = relationship(
        back_populates="egreso", order_by="AprobacionEgreso.creado_en"
    )
    historial: Mapped[list["HistorialEgreso"]] = relationship(
        back_populates="egreso", order_by="HistorialEgreso.creado_en"
    )
    pagos: Mapped[list["PagoEgreso"]] = relationship(
        back_populates="egreso", order_by="PagoEgreso.creado_en"
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", "id", name="uq_egreso_condominio_id"),
        CheckConstraint("moneda IN ('PEN', 'USD')", name="ck_egreso_moneda"),
        CheckConstraint(
            "monto_solicitado > 0 AND (monto_pactado IS NULL OR monto_pactado > 0)",
            name="ck_egreso_importes_solicitud",
        ),
        CheckConstraint(
            "monto_aprobado IS NULL OR monto_aprobado > 0", name="ck_egreso_monto_aprobado"
        ),
        CheckConstraint(
            "monto_pagado >= 0 AND (monto_aprobado IS NULL OR monto_pagado <= monto_aprobado)",
            name="ck_egreso_monto_pagado",
        ),
        CheckConstraint(
            "(presupuesto_id IS NULL) = (item_presupuesto_id IS NULL)",
            name="ck_egreso_presupuesto_item_par",
        ),
        CheckConstraint(
            "contrato_id IS NULL OR proveedor_id IS NOT NULL",
            name="ck_egreso_contrato_requiere_proveedor",
        ),
        CheckConstraint("version > 0", name="ck_egreso_version"),
        CheckConstraint(
            "estado IN ('BORRADOR','PENDIENTE_APROBACION','APROBADO','RECHAZADO',"
            "'PAGO_PARCIAL','PAGADO','CANCELADO')",
            name="ck_egreso_estado",
        ),
        Index("ix_egreso_contexto_fecha", "condominio_id", "fecha_gasto", "id"),
        Index("ix_egreso_contexto_estado", "condominio_id", "estado", "creado_en"),
        Index("ix_egreso_proveedor", "condominio_id", "proveedor_id"),
        Index("ix_egreso_concepto", "condominio_id", "concepto_id"),
    )


class DocumentoFinanciero(Base):
    """Metadatos de documentos privados; el binario vive en el storage adapter."""

    __tablename__ = "documentos_financieros"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    egreso_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    archivo_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Clave opaca del storage, nunca URL pública ni ruta proporcionada por el cliente.
    storage_key: Mapped[str] = mapped_column(String(160), nullable=False)
    creado_por: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    egreso: Mapped[Egreso | None] = relationship(back_populates="documentos")

    __table_args__ = (
        UniqueConstraint("condominio_id", "id", name="uq_documento_financiero_condominio_id"),
        UniqueConstraint("storage_key", name="uq_documento_financiero_storage_key"),
        ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_documento_egreso_contexto",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(tipo IN ('SUSTENTO','EVIDENCIA_PAGO') AND egreso_id IS NOT NULL) OR "
            "(tipo = 'APERTURA_CAJA' AND egreso_id IS NULL)",
            name="ck_documento_financiero_contexto",
        ),
        CheckConstraint(
            "position('/' in archivo_nombre) = 0 AND position(chr(92) in archivo_nombre) = 0 "
            "AND archivo_nombre !~ '[[:cntrl:]]' AND archivo_nombre NOT IN ('.','..')",
            name="ck_documento_financiero_nombre_seguro",
        ),
        CheckConstraint("tamano_bytes > 0", name="ck_documento_financiero_tamano"),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_documento_financiero_sha256"),
        CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9._-]{1,160}$' AND storage_key NOT IN ('.','..')",
            name="ck_documento_financiero_storage_key_segura",
        ),
        Index("ix_documento_financiero_contexto", "condominio_id", "egreso_id", "creado_en"),
    )


class AprobacionEgreso(Base):
    """Decisión inmutable ligada exactamente a una versión e importe."""

    __tablename__ = "aprobaciones_egreso"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    egreso_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_egreso: Mapped[int] = mapped_column(Integer, nullable=False)
    monto_revisado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_anterior: Mapped[str] = mapped_column(String(30), nullable=False)
    estado_nuevo: Mapped[str] = mapped_column(String(30), nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    egreso: Mapped[Egreso] = relationship(back_populates="aprobaciones")

    __table_args__ = (
        ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_aprobacion_egreso_contexto",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "egreso_id", "version_egreso", "actor_id", name="uq_aprobacion_egreso_version_actor"
        ),
        CheckConstraint("version_egreso > 0", name="ck_aprobacion_egreso_version"),
        CheckConstraint("monto_revisado > 0", name="ck_aprobacion_egreso_monto"),
        CheckConstraint("decision IN ('APROBAR','RECHAZAR')", name="ck_aprobacion_egreso_decision"),
        CheckConstraint(
            "resultado IN ('EXITOSO','FALLIDO')", name="ck_aprobacion_egreso_resultado"
        ),
        Index("ix_aprobacion_egreso_historial", "condominio_id", "egreso_id", "creado_en"),
    )


class HistorialEgreso(Base):
    """Bitácora append-only de transiciones y mutaciones de CON-51/52."""

    __tablename__ = "historial_egreso"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    egreso_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    accion: Mapped[str] = mapped_column(String(40), nullable=False)
    estado_anterior: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(30), nullable=False)
    monto_revisado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    version_egreso: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    estado_anterior_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estado_posterior_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    egreso: Mapped[Egreso] = relationship(back_populates="historial")

    __table_args__ = (
        ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_historial_egreso_contexto",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_egreso > 0", name="ck_historial_egreso_version"),
        CheckConstraint(
            "monto_revisado IS NULL OR monto_revisado > 0", name="ck_historial_egreso_monto"
        ),
        CheckConstraint("resultado IN ('EXITOSO','FALLIDO')", name="ck_historial_egreso_resultado"),
        Index("ix_historial_egreso_timeline", "condominio_id", "egreso_id", "creado_en"),
    )


class ConfiguracionAprobacionEgreso(Base):
    """Política escalonada; ausencia de fila significa no configurada."""

    __tablename__ = "configuracion_aprobacion_egreso"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    umbral: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    politica: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UMBRAL_ESCALONADO", server_default="UMBRAL_ESCALONADO"
    )
    aprobaciones_hasta_umbral: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    aprobaciones_sobre_umbral: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default="2"
    )
    pagos_parciales_habilitados: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    actualizado_por: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", name="uq_config_aprobacion_condominio"),
        CheckConstraint("umbral >= 0", name="ck_config_aprobacion_umbral"),
        CheckConstraint("politica = 'UMBRAL_ESCALONADO'", name="ck_config_aprobacion_politica"),
        CheckConstraint(
            "aprobaciones_hasta_umbral = 1 AND aprobaciones_sobre_umbral = 2",
            name="ck_config_aprobacion_conteo_escalonado",
        ),
        CheckConstraint("version > 0", name="ck_config_aprobacion_version"),
    )


class CuentaCaja(Base):
    """Cuenta lógica operativa identificada por alias no sensible y moneda."""

    __tablename__ = "cuentas_caja"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    cuenta_referencia: Mapped[str] = mapped_column(String(100), nullable=False)
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    aperturas: Mapped[list["AperturaCaja"]] = relationship(back_populates="cuenta")
    movimientos: Mapped[list["MovimientoCaja"]] = relationship(
        back_populates="cuenta", viewonly=True
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", "id", name="uq_cuenta_caja_condominio_id"),
        UniqueConstraint(
            "condominio_id", "moneda", "cuenta_referencia", name="uq_cuenta_caja_alias_moneda"
        ),
        CheckConstraint("moneda IN ('PEN','USD')", name="ck_cuenta_caja_moneda"),
    )


class AperturaCaja(Base):
    """Saldo de apertura conciliado; jamás se crea automáticamente."""

    __tablename__ = "aperturas_caja"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cuenta_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    documento_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    saldo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_corte: Mapped[date] = mapped_column(Date, nullable=False)
    referencia: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    cuenta: Mapped[CuentaCaja] = relationship(back_populates="aperturas")
    movimientos: Mapped[list["MovimientoCaja"]] = relationship(
        back_populates="apertura", viewonly=True
    )

    __table_args__ = (
        UniqueConstraint("condominio_id", "id", name="uq_apertura_caja_condominio_id"),
        ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_apertura_caja_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "documento_id"],
            ["documentos_financieros.condominio_id", "documentos_financieros.id"],
            name="fk_apertura_caja_documento_contexto",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("cuenta_id", name="uq_apertura_caja_cuenta"),
        UniqueConstraint("documento_id", name="uq_apertura_caja_documento"),
        UniqueConstraint("condominio_id", "idempotency_key", name="uq_apertura_caja_idempotency"),
        CheckConstraint("saldo >= 0", name="ck_apertura_caja_saldo"),
        CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_apertura_caja_hash"),
        Index("ix_apertura_caja_condominio_fecha", "condominio_id", "fecha_corte"),
    )


class PagoEgreso(Base):
    """Registro de pago ejecutado o intento fallido; solo confirmado mueve caja."""

    __tablename__ = "pagos_egreso"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    egreso_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    cuenta_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    documento_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    referencia: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    egreso: Mapped[Egreso] = relationship(back_populates="pagos")
    movimientos: Mapped[list["MovimientoCaja"]] = relationship(back_populates="pago", viewonly=True)
    reverso: Mapped["ReversoPago | None"] = relationship(back_populates="pago", uselist=False)

    __table_args__ = (
        UniqueConstraint("condominio_id", "id", name="uq_pago_egreso_condominio_id"),
        ForeignKeyConstraint(
            ["condominio_id", "egreso_id"],
            ["egresos.condominio_id", "egresos.id"],
            name="fk_pago_egreso_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_pago_cuenta_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "documento_id"],
            ["documentos_financieros.condominio_id", "documentos_financieros.id"],
            name="fk_pago_egreso_documento_contexto",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "condominio_id",
            "idempotency_scope",
            "idempotency_key",
            name="uq_pago_egreso_idempotency",
        ),
        CheckConstraint("monto > 0", name="ck_pago_egreso_monto"),
        CheckConstraint("moneda IN ('PEN','USD')", name="ck_pago_egreso_moneda"),
        CheckConstraint(
            "estado IN ('CONFIRMADO','FALLIDO','REVERSADO')", name="ck_pago_egreso_estado"
        ),
        CheckConstraint(
            "idempotency_scope IN ('CONFIRMAR','FALLIDO')", name="ck_pago_egreso_idem_scope"
        ),
        CheckConstraint(
            "(estado = 'CONFIRMADO' AND idempotency_scope = 'CONFIRMAR' AND documento_id IS NOT NULL) "
            "OR (estado = 'FALLIDO' AND idempotency_scope = 'FALLIDO') "
            "OR (estado = 'REVERSADO' AND idempotency_scope = 'CONFIRMAR' AND documento_id IS NOT NULL)",
            name="ck_pago_egreso_documento_scope",
        ),
        CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_pago_egreso_request_hash"),
        Index("ix_pago_egreso_contexto_fecha", "condominio_id", "egreso_id", "fecha_pago"),
    )


class ReversoPago(Base):
    """Reverso total append-only, respaldado por movimiento positivo compensatorio."""

    __tablename__ = "reversos_pago_egreso"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pago_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    pago: Mapped[PagoEgreso] = relationship(back_populates="reverso")
    movimientos: Mapped[list["MovimientoCaja"]] = relationship(
        back_populates="reverso", viewonly=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["condominio_id", "pago_id"],
            ["pagos_egreso.condominio_id", "pagos_egreso.id"],
            name="fk_reverso_pago_contexto",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("pago_id", name="uq_reverso_pago_unico"),
        UniqueConstraint("condominio_id", "id", name="uq_reverso_pago_contexto_id"),
        UniqueConstraint("condominio_id", "idempotency_key", name="uq_reverso_pago_idempotency"),
        CheckConstraint("monto > 0", name="ck_reverso_pago_monto"),
        CheckConstraint("request_hash ~ '^[a-f0-9]{64}$'", name="ck_reverso_pago_request_hash"),
        Index("ix_reverso_pago_contexto_fecha", "condominio_id", "creado_en"),
    )


class MovimientoCaja(Base):
    """Ledger operativo append-only. El saldo es SUM(importe), no un campo mutable."""

    __tablename__ = "movimientos_caja"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cuenta_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    apertura_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    pago_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reverso_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    importe: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_operacion: Mapped[date] = mapped_column(Date, nullable=False)
    reconocido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    cuenta: Mapped[CuentaCaja] = relationship(back_populates="movimientos", viewonly=True)
    apertura: Mapped[AperturaCaja | None] = relationship(
        back_populates="movimientos", viewonly=True
    )
    pago: Mapped[PagoEgreso | None] = relationship(back_populates="movimientos", viewonly=True)
    reverso: Mapped[ReversoPago | None] = relationship(back_populates="movimientos", viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["condominio_id", "cuenta_id"],
            ["cuentas_caja.condominio_id", "cuentas_caja.id"],
            name="fk_movimiento_caja_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "apertura_id"],
            ["aperturas_caja.condominio_id", "aperturas_caja.id"],
            name="fk_movimiento_caja_apertura_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "pago_id"],
            ["pagos_egreso.condominio_id", "pagos_egreso.id"],
            name="fk_movimiento_caja_pago_contexto",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["condominio_id", "reverso_id"],
            ["reversos_pago_egreso.condominio_id", "reversos_pago_egreso.id"],
            name="fk_movimiento_caja_reverso_contexto",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("apertura_id", name="uq_movimiento_caja_apertura"),
        UniqueConstraint("pago_id", name="uq_movimiento_caja_pago"),
        UniqueConstraint("reverso_id", name="uq_movimiento_caja_reverso"),
        CheckConstraint(
            "(tipo = 'APERTURA' AND apertura_id IS NOT NULL AND pago_id IS NULL "
            "AND reverso_id IS NULL AND importe >= 0) OR "
            "(tipo = 'PAGO_EGRESO' AND apertura_id IS NULL AND pago_id IS NOT NULL "
            "AND reverso_id IS NULL AND importe < 0) OR "
            "(tipo = 'REVERSO_PAGO' AND apertura_id IS NULL AND pago_id IS NULL "
            "AND reverso_id IS NOT NULL AND importe > 0)",
            name="ck_movimiento_caja_origen_importe",
        ),
        Index("ix_movimiento_caja_contexto_fecha", "condominio_id", "cuenta_id", "reconocido_en"),
    )
