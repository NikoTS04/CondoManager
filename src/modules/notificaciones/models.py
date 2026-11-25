"""Cola durable, historial de intentos y consumo idempotente de CON-73."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Notificacion(Base):
    __tablename__ = "notificaciones_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    departamento_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
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
    finalidad: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPERATIVA", server_default="OPERATIVA"
    )
    contenido_cifrado: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="EN_COLA")
    transporte: Mapped[str] = mapped_column(String(20), nullable=False, default="SIMULADO")
    ciclo: Mapped[int] = mapped_column(nullable=False, default=1)
    intentos: Mapped[int] = mapped_column(nullable=False, default=0)
    proximo_reintento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proveedor_message_id: Mapped[str | None] = mapped_column(Text)
    error_mensaje: Mapped[str | None] = mapped_column(Text)
    recordatorio_vencimiento: Mapped[date | None] = mapped_column(Date)
    recordatorio_dias: Mapped[int | None] = mapped_column()
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint(
            "(finalidad = 'OPERATIVA' AND departamento_id IS NOT NULL AND contenido_cifrado IS NULL) OR finalidad IN ('INVITACION','SEGURIDAD')",
            name="ck_notificacion_finalidad",
        ),
        UniqueConstraint(
            "evento_id",
            "operacion_id",
            "usuario_destinatario_id",
            "canal",
            name="uq_notificacion_logica",
        ),
        CheckConstraint("intentos BETWEEN 0 AND 4 AND ciclo >= 1", name="ck_notificacion_intentos"),
        CheckConstraint(
            "estado IN ('EN_COLA','ENVIADO','ENTREGADO','REINTENTANDO','FALLIDO_PERMANENTE','OMITIDO')",
            name="ck_notificacion_estado",
        ),
        CheckConstraint(
            "transporte IN ('SIMULADO','PROVEEDOR')", name="ck_notificacion_transporte"
        ),
        CheckConstraint("canal IN ('EMAIL','WHATSAPP','SMS','PUSH')", name="ck_notificacion_canal"),
        Index("idx_notificacion_contexto_usuario", "condominio_id", "usuario_destinatario_id"),
        Index("idx_notificacion_pendiente", "estado", "proximo_reintento"),
    )


class Comunicado(Base):
    __tablename__ = "comunicados"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id"), index=True)
    contenido: Mapped[dict] = mapped_column(JSONB)
    audiencia: Mapped[list] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PoliticaNotificaciones(Base):
    __tablename__ = "politicas_notificaciones"
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id"), primary_key=True)
    dias: Mapped[list] = mapped_column(JSONB, default=lambda: [3, 0])
    hora: Mapped[int] = mapped_column(default=8)
    habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_fecha: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (CheckConstraint("hora BETWEEN 0 AND 23", name="ck_notificaciones_hora"),)


class ContactoBloqueado(Base):
    __tablename__ = "contactos_bloqueados"
    condominio_id: Mapped[UUID] = mapped_column(ForeignKey("condominios.id"), primary_key=True)
    email: Mapped[str] = mapped_column(Text, primary_key=True)
    motivo: Mapped[str] = mapped_column(String(30))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventoSolvenciaOutbox(Base):
    __tablename__ = "eventos_solvencia_outbox"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    comprobante_id: Mapped[UUID] = mapped_column(ForeignKey("comprobantes_pago.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class EstadoJobNotificaciones(Base):
    __tablename__ = "estado_job_notificaciones"
    nombre: Mapped[str] = mapped_column(String(30), primary_key=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))


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


TIPOS_ALERTA = (
    "ERROR_DEFINITIVO",
    "INTENTOS_AGOTADOS",
    "ACEPTACION_INCIERTA",
    "DESTINATARIO_INVALIDO",
    "PROVEEDOR_NO_CONFIGURADO",
    "JOB_FALLO_DEFINITIVO",
)
ORIGENES_ALERTA = ("CORREO", "JOB")


class AlertaNotificacion(Base):
    __tablename__ = "notificaciones_alertas"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    notificacion_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notificaciones_logs.id", ondelete="RESTRICT"), nullable=True
    )
    condominio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )
    origen_tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    origen_id: Mapped[str] = mapped_column(String(100), nullable=False)
    referencia_correlacion: Mapped[str | None] = mapped_column(String(64))
    ciclo: Mapped[int] = mapped_column(nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    atendida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    atendida_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        UniqueConstraint("origen_tipo", "origen_id", "ciclo", "tipo", name="uq_alerta_origen_tipo"),
        CheckConstraint("tipo IN ('" + "','".join(TIPOS_ALERTA) + "')", name="ck_alerta_tipo"),
        CheckConstraint(
            "origen_tipo IN ('" + "','".join(ORIGENES_ALERTA) + "')", name="ck_alerta_origen_tipo"
        ),
        CheckConstraint(
            "origen_tipo <> 'CORREO' OR (notificacion_id IS NOT NULL AND condominio_id IS NOT NULL)",
            name="ck_alerta_origen",
        ),
        CheckConstraint(
            "(atendida_en IS NULL) = (atendida_por IS NULL)", name="ck_alerta_atencion"
        ),
        Index(
            "idx_alerta_abierta",
            "condominio_id",
            "creada_en",
            postgresql_where=text("atendida_en IS NULL"),
        ),
    )
