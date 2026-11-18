"""Estado de onboarding e idempotencia durables; nunca tokens en claro."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class InvitacionUsuario(Base):
    __tablename__ = "invitaciones_usuario"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id", ondelete="RESTRICT"))
    creador_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    revision_cuenta: Mapped[int]
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utilizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "expira_en > creado_en AND revision_cuenta >= 1", name="ck_invitacion_fechas"
        ),
        Index("idx_invitacion_usuario", "usuario_id"),
    )


class OperacionIdentidad(Base):
    __tablename__ = "operaciones_identidad"

    condominio_id: Mapped[UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), primary_key=True
    )
    clave: Mapped[UUID] = mapped_column(primary_key=True)
    huella: Mapped[str] = mapped_column(String(64))
    respuesta: Mapped[dict] = mapped_column(JSONB)
