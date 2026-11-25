"""Modelos SQLAlchemy para Proveedores y Contratos (CON-48, CON-49)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class Proveedor(Base):
    """Directorio de proveedores de bienes y servicios por condominio (CON-48)."""

    __tablename__ = "proveedores"
    __table_args__ = (
        UniqueConstraint(
            "condominio_id", "ruc", name="uq_proveedor_condominio_ruc"
        ),
        CheckConstraint("length(ruc) = 11", name="ck_proveedor_ruc_longitud"),
        CheckConstraint("version >= 1", name="ck_proveedor_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), index=True
    )
    ruc: Mapped[str] = mapped_column(String(11), index=True)
    razon_social: Mapped[str] = mapped_column(String(200))
    nombre_comercial: Mapped[str | None] = mapped_column(String(200), default=None)
    rubro: Mapped[str] = mapped_column(String(100))  # Ej: SEGURIDAD, LIMPIEZA, ASCENSORES, etc.
    contacto_nombre: Mapped[str] = mapped_column(String(150))
    contacto_telefono: Mapped[str] = mapped_column(String(50))
    contacto_email: Mapped[str] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(Text, default=None)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notas: Mapped[str | None] = mapped_column(Text, default=None)

    # Auditoría inmutable
    creado_por: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)

    # Relaciones
    contratos = relationship(
        "ContratoProveedor",
        back_populates="proveedor",
        cascade="all, delete-orphan",
        order_by="desc(ContratoProveedor.fecha_fin)",
    )


class ContratoProveedor(Base):
    """Contratos de servicio y pólizas de seguro con vigencia y versiones (CON-49)."""

    __tablename__ = "contratos_proveedor"
    __table_args__ = (
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_contrato_fechas"),
        CheckConstraint(
            "tipo_documento IN ('CONTRATO_SERVICIO', 'POLIZA_SEGURO', 'ADDENDA', 'ACTA_CONFORMIDAD')",
            name="ck_contrato_tipo_documento",
        ),
        CheckConstraint(
            "estado IN ('VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'CANCELADO')",
            name="ck_contrato_estado",
        ),
        CheckConstraint("version_actual >= 1", name="ck_contrato_version_actual"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), index=True
    )
    proveedor_id: Mapped[UUID] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    numero_contrato: Mapped[str] = mapped_column(String(100))
    tipo_documento: Mapped[str] = mapped_column(
        String(50), default="CONTRATO_SERVICIO"
    )
    descripcion: Mapped[str] = mapped_column(Text)
    monto_mensual: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None
    )
    moneda: Mapped[str] = mapped_column(String(3), server_default="PEN", default="PEN")
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date, index=True)
    contacto_emergencia: Mapped[str | None] = mapped_column(String(150), default=None)
    contacto_emergencia_telefono: Mapped[str | None] = mapped_column(String(50), default=None)
    estado: Mapped[str] = mapped_column(
        String(30), server_default="VIGENTE", default="VIGENTE"
    )
    version_actual: Mapped[int] = mapped_column(Integer, server_default="1", default=1)

    # Auditoría
    creado_por: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    proveedor = relationship("Proveedor", back_populates="contratos")
    versiones = relationship(
        "DocumentoContratoVersion",
        back_populates="contrato",
        cascade="all, delete-orphan",
        order_by="desc(DocumentoContratoVersion.version)",
    )


class DocumentoContratoVersion(Base):
    """Almacén privado y versionado de documentos PDF de contratos y pólizas (CON-49)."""

    __tablename__ = "documentos_contrato_version"
    __table_args__ = (
        UniqueConstraint(
            "contrato_id", "version", name="uq_documento_contrato_version"
        ),
        CheckConstraint("version >= 1", name="ck_doc_version_positiva"),
        CheckConstraint("archivo_tamano_bytes > 0", name="ck_doc_tamano_positivo"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    contrato_id: Mapped[UUID] = mapped_column(
        ForeignKey("contratos_proveedor.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    archivo_nombre: Mapped[str] = mapped_column(String(255))
    archivo_mime: Mapped[str] = mapped_column(String(100), default="application/pdf")
    archivo_tamano_bytes: Mapped[int] = mapped_column(Integer)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    archivo_binario: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    motivo_reemplazo: Mapped[str | None] = mapped_column(Text, default=None)

    subido_por: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    subido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    contrato = relationship("ContratoProveedor", back_populates="versiones")
