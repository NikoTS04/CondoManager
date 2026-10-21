"""Cola durable, historial de intentos y consumo idempotente de CON-73."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Notificacion(Base):
    __tablename__ = "notificaciones_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    departamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_destinatario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    evento_id: Mapped[UUID] = mapped_column(nullable=False)
    operacion_id: Mapped[UUID] = mapped_column(nullable=False)
    tipo_evento: Mapped[str] = mapped_column(Text, nullable=False)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    destinatario: Mapped[str] = mapped_column(Text, nullable=False)
    asunto: Mapped[str | None] = mapped_column(Text)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="EN_COLA")
    transporte: Mapped[str] = mapped_column(String(20), nullable=False, default="SIMULADO")
    ciclo: Mapped[int] = mapped_column(nullable=False, default=1)
    intentos: Mapped[int] = mapped_column(nullable=False, default=0)
    proximo_reintento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proveedor_message_id: Mapped[str | None] = mapped_column(Text)
    error_mensaje: Mapped[str | None] = mapped_column(Text)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint(
            "evento_id",
            "operacion_id",
            "usuario_destinatario_id",
            "canal",
            name="uq_notificacion_logica",
        ),
        CheckConstraint("intentos BETWEEN 0 AND 4 AND ciclo >= 1", name="ck_notificacion_intentos"),
        CheckConstraint(
            "estado IN ('EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE')",
            name="ck_notificacion_estado",
        ),
        CheckConstraint(
            "transporte IN ('SIMULADO','PROVEEDOR')", name="ck_notificacion_transporte"
        ),
        CheckConstraint("canal IN ('EMAIL','WHATSAPP','SMS','PUSH')", name="ck_notificacion_canal"),
        Index("idx_notificacion_contexto_usuario", "condominio_id", "usuario_destinatario_id"),
        Index("idx_notificacion_pendiente", "estado", "proximo_reintento"),
    )


class IntentoNotificacion(Base):
    __tablename__ = "notificaciones_intentos"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    notificacion_id: Mapped[UUID] = mapped_column(
        ForeignKey("notificaciones_logs.id", ondelete="RESTRICT"), nullable=False
    )
    ciclo: Mapped[int] = mapped_column(nullable=False)
    numero: Mapped[int] = mapped_column(nullable=False)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    proveedor_message_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("notificacion_id", "ciclo", "numero", name="uq_notificacion_intento"),
        CheckConstraint("numero BETWEEN 1 AND 4 AND ciclo >= 1", name="ck_intento_numero"),
    )


class EventoConsumido(Base):
    __tablename__ = "notificaciones_eventos"

    consumidor: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncidenciaEvento(Base):
    __tablename__ = "notificaciones_incidencias"

    clave: Mapped[str] = mapped_column(Text, primary_key=True)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
