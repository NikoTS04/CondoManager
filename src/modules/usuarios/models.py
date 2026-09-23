"""Modelos ORM de Usuarios y RBAC (PROC-05)."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    apellido: Mapped[str] = mapped_column(String(80), nullable=False)
    telefono: Mapped[str] = mapped_column(String(20), nullable=True)
    documento_identidad: Mapped[str] = mapped_column(String(20), nullable=False)
    esta_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class UsuarioDepartamento(Base):
    __tablename__ = "usuario_departamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    departamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departamentos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_relacion: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PROPIETARIO_TITULAR"
    )
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("usuario_id", "departamento_id", name="uq_usuario_depto"),
        CheckConstraint(
            "tipo_relacion IN ('PROPIETARIO_TITULAR', 'INQUILINO', 'COPROPIETARIO')",
            name="ck_tipo_relacion",
        ),
    )


class UsuarioRol(Base):
    __tablename__ = "usuario_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condominios.id", ondelete="CASCADE"),
        nullable=False,
    )
    rol: Mapped[str] = mapped_column(
        String(30), nullable=False, default="RESIDENTE"
    )

    __table_args__ = (
        UniqueConstraint("usuario_id", "condominio_id", name="uq_usuario_condo_rol"),
        CheckConstraint(
            "rol IN ('SUPERADMIN', 'ADMIN_JUNTA', 'AUDITOR', 'RESIDENTE')",
            name="ck_rol_nombre",
        ),
    )
