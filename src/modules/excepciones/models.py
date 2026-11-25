"""Decisiones y resultados de excepciones globales desacoplados del condominio."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base

ESTADOS_REINTENTO = "'EN_COLA', 'EN_CURSO', 'COMPLETADO', 'FALLIDO', 'INCIERTO'"
FILTRO_REINTENTO = "accion = 'REINTENTAR_JOB'"
FILTRO_ACTIVO = f"{FILTRO_REINTENTO} AND resultado IN ('EN_COLA', 'EN_CURSO')"


class ResolucionJob(Base):
    __tablename__ = "excepciones_job_resoluciones"
    __table_args__ = (
        UniqueConstraint("alerta_id", "clave", name="uq_excepcion_job_clave"),
        Index(
            "uq_excepcion_job_reintento",
            "alerta_id",
            unique=True,
            postgresql_where=text(FILTRO_REINTENTO),
        ),
        Index(
            "uq_excepcion_job_activo",
            "nombre_job",
            unique=True,
            postgresql_where=text(FILTRO_ACTIVO),
        ),
        CheckConstraint(
            f"({FILTRO_REINTENTO} AND resultado IN ({ESTADOS_REINTENTO})) "
            "OR (accion = 'CERRAR_CON_MOTIVO' AND resultado = 'OMITIDO') "
            "OR (accion = 'SOLICITAR_INFORMACION' AND resultado = 'PENDIENTE_INFORMACION')",
            name="ck_excepcion_job_resultado",
        ),
        CheckConstraint(
            "(accion = 'SOLICITAR_INFORMACION') = (responsable IS NOT NULL)",
            name="ck_excepcion_job_responsable",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alerta_id: Mapped[UUID] = mapped_column(
        ForeignKey("notificaciones_alertas.id", ondelete="RESTRICT")
    )
    nombre_job: Mapped[str] = mapped_column(Text)
    clave: Mapped[UUID]
    huella: Mapped[str] = mapped_column(Text)
    accion: Mapped[str] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    responsable: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(Text)
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
