"""Modelos ORM persistentes de notificaciones (Alejandro - CON-32/34/36/37).

Distingue registro persistido (`EN_COLA`), envío aceptado por el proveedor
(`ACEPTADO`) y entrega confirmada (`ENTREGADO`). La deduplicación lógica se
apoya en `clave_deduplicacion`; la coordinación entre workers en el arrendamiento
`bloqueado_hasta`/`bloqueado_por` tomado con `FOR UPDATE SKIP LOCKED`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base

ESTADOS_NOTIFICACION = (
    "EN_COLA",
    "REINTENTANDO",
    "ACEPTADO",
    "ENTREGADO",
    "FALLIDO_PERMANENTE",
)
ESTADOS_PENDIENTES = ("EN_COLA", "REINTENTANDO")
CANALES = ("EMAIL", "WHATSAPP", "SMS", "PUSH")
ORIGENES = ("CUOTA", "COMPROBANTE", "RESERVA", "COMUNICADO", "USUARIO")
RESULTADOS_INTENTO = ("ACEPTADO", "FALLO_TEMPORAL", "FALLO_DEFINITIVO")
MAX_INTENTOS = 4  # Un intento inicial y tres reintentos (delivery-policy.md).


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    evento_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String(60), nullable=False)
    plantilla: Mapped[str] = mapped_column(String(50), nullable=False)
    origen_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    origen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    clave_deduplicacion: Mapped[str] = mapped_column(String(255), nullable=False)
    canal: Mapped[str] = mapped_column(String(10), nullable=False, default="EMAIL")
    destinatario: Mapped[str] = mapped_column(String(150), nullable=False)
    asunto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    contexto: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="EN_COLA")
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Un reenvío manual abre un ciclo nuevo de hasta 4 intentos sin borrar el historial.
    ciclo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proximo_intento_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bloqueado_por: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transporte: Mapped[str | None] = mapped_column(String(40), nullable=True)
    transporte_simulado: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    proveedor_message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    error_codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    aceptado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entregado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("clave_deduplicacion", name="uq_notificacion_entrega_logica"),
        CheckConstraint(
            "estado IN ('EN_COLA', 'REINTENTANDO', 'ACEPTADO', 'ENTREGADO', 'FALLIDO_PERMANENTE')",
            name="ck_notificacion_estado",
        ),
        CheckConstraint(
            "canal IN ('EMAIL', 'WHATSAPP', 'SMS', 'PUSH')", name="ck_notificacion_canal"
        ),
        CheckConstraint(
            "origen_tipo IN ('CUOTA', 'COMPROBANTE', 'RESERVA', 'COMUNICADO', 'USUARIO')",
            name="ck_notificacion_origen",
        ),
        CheckConstraint("intentos BETWEEN 0 AND 4", name="ck_notificacion_intentos"),
        CheckConstraint("ciclo >= 1", name="ck_notificacion_ciclo"),
        Index(
            "idx_notificaciones_pendientes",
            "proximo_intento_en",
            postgresql_where=text("estado IN ('EN_COLA', 'REINTENTANDO')"),
        ),
        Index("idx_notificaciones_condominio", "condominio_id", "creado_en"),
        Index("idx_notificaciones_departamento", "departamento_id", "creado_en"),
        Index("idx_notificaciones_origen", "origen_tipo", "origen_id"),
    )


class NotificacionIntento(Base):
    __tablename__ = "notificacion_intentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notificacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notificaciones.id", ondelete="CASCADE"), nullable=False
    )
    ciclo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(80), nullable=False)
    transporte: Mapped[str] = mapped_column(String(40), nullable=False)
    transporte_simulado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    proveedor_message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("notificacion_id", "ciclo", "numero", name="uq_intento_numero"),
        CheckConstraint("numero BETWEEN 1 AND 4", name="ck_intento_numero"),
        CheckConstraint(
            "resultado IN ('ACEPTADO', 'FALLO_TEMPORAL', 'FALLO_DEFINITIVO')",
            name="ck_intento_resultado",
        ),
    )


class EventoConsumido(Base):
    """Idempotencia de consumo: un evento se procesa una vez por consumidor."""

    __tablename__ = "eventos_consumidos"

    consumidor: Mapped[str] = mapped_column(String(60), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    notificaciones_creadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (PrimaryKeyConstraint("consumidor", "event_id", name="pk_eventos_consumidos"),)


class AlertaAdministrativa(Base):
    __tablename__ = "alertas_administrativas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condominio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("condominios.id", ondelete="RESTRICT"), nullable=False
    )
    notificacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notificaciones.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, default="NOTIFICACION_FALLIDA")
    severidad: Mapped[str] = mapped_column(String(10), nullable=False, default="BAJA")
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atendida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    atendida_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("notificacion_id", "tipo", name="uq_alerta_notificacion_tipo"),
        CheckConstraint("severidad IN ('BAJA', 'MEDIA', 'ALTA')", name="ck_alerta_severidad"),
        Index(
            "idx_alertas_abiertas",
            "condominio_id",
            "creado_en",
            postgresql_where=text("atendida_en IS NULL"),
        ),
    )
