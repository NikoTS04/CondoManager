"""Motor persistente de despacho, arrendamiento, reintentos y alertas (CON-37).

Coordina workers concurrentes sobre PostgreSQL con `FOR UPDATE SKIP LOCKED`,
realiza el envío fuera de la transacción de base de datos, aplica la política
de backoff exponencial (2, 10 y 30 min; jitter ±15 s en el primer reintento)
y genera alertas administrativas ante fallos definitivos o agotamiento.
"""

import random
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.errors import APIError
from src.modules.condominios.models import Departamento
from src.modules.notificaciones.models import (
    ESTADOS_PENDIENTES,
    MAX_INTENTOS,
    AlertaAdministrativa,
    Notificacion,
    NotificacionIntento,
)
from src.modules.notificaciones.transportes import (
    ResultadoTransporte,
    TransporteNotificacion,
    clasificar_fallo,
    obtener_transporte,
    validar_destinatario,
)

# Espera tras el intento N fallido antes de ejecutar el intento N+1:
# Intento 1 fallido -> espera 120s (±15s jitter) para intento 2 (1er reintento)
# Intento 2 fallido -> espera 600s (10 min) para intento 3 (2do reintento)
# Intento 3 fallido -> espera 1800s (30 min) para intento 4 (3er reintento)
INTERVALOS_REINTENTO_SEGUNDOS: dict[int, int] = {
    1: 120,
    2: 600,
    3: 1800,
}
JITTER_MAX_SEGUNDOS = 15.0

_PATRON_DATOS_SENSIBLES = re.compile(
    r"(password|secret|token|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


@dataclass
class ResumenDespacho:
    """Resumen de una pasada de `despachar_pendientes`."""

    reclamadas: int = 0
    aceptadas: int = 0
    entregadas: int = 0
    reintentando: int = 0
    fallidas_permanentes: int = 0
    omitidas_arrendamiento: int = 0

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def sanitizar_detalle_error(detalle: str | None) -> str:
    """Elimina credenciales o secretos accidentales del mensaje de error."""
    if not detalle:
        return "Error de transporte no especificado."
    limpio = _PATRON_DATOS_SENSIBLES.sub("[REDACTED]", detalle.strip())
    return limpio[:500]


def calcular_proximo_intento(
    intentos_realizados: int,
    ahora: datetime,
    *,
    jitter_fn: Callable[[], float | int] | None = None,
) -> datetime | None:
    """Calcula `proximo_intento_en` según el número de intentos ya ejecutados (1..3)."""
    if intentos_realizados >= MAX_INTENTOS:
        return None
    base_segundos = INTERVALOS_REINTENTO_SEGUNDOS.get(intentos_realizados)
    if base_segundos is None:
        return None

    desplazamiento = float(base_segundos)
    if intentos_realizados == 1:
        jitter_raw = (
            float(jitter_fn())
            if jitter_fn is not None
            else random.uniform(-JITTER_MAX_SEGUNDOS, JITTER_MAX_SEGUNDOS)
        )
        jitter = max(-JITTER_MAX_SEGUNDOS, min(JITTER_MAX_SEGUNDOS, jitter_raw))
        desplazamiento += jitter

    return ahora + timedelta(seconds=desplazamiento)


async def construir_mensaje_alerta(session: AsyncSession, notificacion: Notificacion) -> str:
    """Construye el mensaje administrativo sin exponer datos sensibles."""
    dpto_num = None
    if isinstance(notificacion.contexto, dict):
        dpto_ctx = notificacion.contexto.get("dpto")
        if dpto_ctx and str(dpto_ctx).strip() not in {"", "-"}:
            dpto_num = str(dpto_ctx).strip()
    if not dpto_num and notificacion.departamento_id is not None:
        dpto_num = await session.scalar(
            select(Departamento.numero).where(Departamento.id == notificacion.departamento_id)
        )

    if dpto_num:
        if notificacion.canal == "EMAIL":
            return (
                f"El correo del residente del Dpto. {dpto_num} rebotó. "
                "Actualice los datos de contacto."
            )
        return (
            f"La notificación ({notificacion.canal}) del residente del Dpto. {dpto_num} "
            "no pudo entregarse. Actualice los datos de contacto."
        )
    return "El correo del destinatario rebotó. Actualice los datos de contacto."


async def _registrar_alerta_fallo(
    session: AsyncSession,
    notificacion: Notificacion,
    ahora: datetime,
) -> None:
    """Inserta o reactiva de forma idempotente la alerta administrativa por fallo permanente."""
    mensaje = await construir_mensaje_alerta(session, notificacion)
    stmt = (
        insert(AlertaAdministrativa)
        .values(
            id=uuid.uuid4(),
            condominio_id=notificacion.condominio_id,
            notificacion_id=notificacion.id,
            tipo="NOTIFICACION_FALLIDA",
            severidad="BAJA",
            mensaje=mensaje,
            creado_en=ahora,
        )
        .on_conflict_do_update(
            constraint="uq_alerta_notificacion_tipo",
            set_={
                "mensaje": mensaje,
                "creado_en": ahora,
                "atendida_en": None,
                "atendida_por": None,
            },
            where=AlertaAdministrativa.atendida_en.is_not(None),
        )
    )
    await session.execute(stmt)


def _normalizar_lease(lease: timedelta | int | float | None) -> timedelta:
    if lease is None:
        return timedelta(seconds=settings.NOTIFICACIONES_LEASE_SEGUNDOS)
    if isinstance(lease, timedelta):
        return lease
    return timedelta(seconds=float(lease))


async def reclamar_lote(
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    worker_id: str = "notificaciones-worker",
    ahora: datetime | None = None,
    limite: int | None = None,
    lease: timedelta | int | float | None = None,
) -> list[Notificacion]:
    """Reclama en transacción corta un lote elegible con `FOR UPDATE SKIP LOCKED`."""
    momento = ahora or datetime.now(UTC)
    max_filas = limite if limite is not None else settings.NOTIFICACIONES_LOTE_LIMITE
    bloqueado_hasta = momento + _normalizar_lease(lease)

    async with session_factory() as session, session.begin():
        stmt = (
            select(Notificacion)
            .where(
                Notificacion.estado.in_(ESTADOS_PENDIENTES),
                Notificacion.intentos < MAX_INTENTOS,
                or_(
                    Notificacion.proximo_intento_en.is_(None),
                    Notificacion.proximo_intento_en <= momento,
                ),
                or_(
                    Notificacion.bloqueado_hasta.is_(None),
                    Notificacion.bloqueado_hasta < momento,
                ),
            )
            .order_by(
                Notificacion.proximo_intento_en.asc().nullsfirst(),
                Notificacion.creado_en.asc(),
                Notificacion.id.asc(),
            )
            .limit(max_filas)
            .with_for_update(skip_locked=True)
        )
        reclamadas = list((await session.scalars(stmt)).all())
        for fila in reclamadas:
            fila.bloqueado_por = worker_id
            fila.bloqueado_hasta = bloqueado_hasta
            fila.actualizado_en = momento

    return reclamadas


async def registrar_resultado_intento(
    session_factory: async_sessionmaker[AsyncSession],
    notificacion_id: uuid.UUID,
    worker_id: str,
    transporte: TransporteNotificacion,
    resultado: ResultadoTransporte,
    iniciado_en: datetime,
    finalizado_en: datetime,
    *,
    jitter_fn: Callable[[], float | int] | None = None,
) -> str:
    """Persiste el resultado de un intento condicionando al arrendamiento `bloqueado_por`."""
    async with session_factory() as session, session.begin():
        actual = await session.scalar(
            select(Notificacion).where(Notificacion.id == notificacion_id).with_for_update()
        )
        if actual is None:
            return "OMITIDA"

        # Nunca reenviar ni pisar una notificación ya aceptada o entregada.
        if actual.estado in ("ENVIADO", "ENTREGADO"):
            return "OMITIDA"

        # Si el worker perdió el arrendamiento frente a otro worker, no pisa el estado.
        if actual.bloqueado_por != worker_id:
            return "OMITIDA"

        numero_intento = actual.intentos + 1
        if numero_intento > MAX_INTENTOS:
            actual.bloqueado_por = None
            actual.bloqueado_hasta = None
            return "OMITIDA"

        if resultado.aceptado:
            tipo_resultado = "ACEPTADO"
            codigo_guardar = None
            detalle_guardar = None
        else:
            codigo_guardar = str(resultado.codigo or "500")[:40]
            detalle_guardar = sanitizar_detalle_error(resultado.detalle)
            tipo_resultado = clasificar_fallo(codigo_guardar, detalle_guardar)

        insert_intento = (
            insert(NotificacionIntento)
            .values(
                id=uuid.uuid4(),
                notificacion_id=actual.id,
                ciclo=actual.ciclo,
                numero=numero_intento,
                worker_id=worker_id,
                transporte=transporte.nombre,
                transporte_simulado=transporte.es_simulado,
                resultado=tipo_resultado,
                codigo=codigo_guardar,
                detalle=detalle_guardar,
                proveedor_message_id=resultado.proveedor_message_id,
                iniciado_en=iniciado_en,
                finalizado_en=finalizado_en,
            )
            .on_conflict_do_nothing(constraint="uq_intento_numero")
            .returning(NotificacionIntento.id)
        )
        intento_id = (await session.execute(insert_intento)).scalar_one_or_none()
        if intento_id is None:
            return "OMITIDA"

        actual.intentos = numero_intento
        actual.transporte = transporte.nombre
        actual.transporte_simulado = transporte.es_simulado
        actual.bloqueado_por = None
        actual.bloqueado_hasta = None
        actual.actualizado_en = finalizado_en

        if resultado.aceptado:
            actual.proveedor_message_id = resultado.proveedor_message_id
            actual.error_codigo = None
            actual.error_mensaje = None
            actual.proximo_intento_en = None
            actual.aceptado_en = finalizado_en
            if resultado.confirmar_entrega_inmediata:
                actual.estado = "ENTREGADO"
                actual.entregado_en = finalizado_en
            else:
                actual.estado = "ENVIADO"
            return actual.estado

        actual.error_codigo = codigo_guardar
        actual.error_mensaje = f"[{codigo_guardar}] {detalle_guardar}"

        if tipo_resultado == "FALLO_DEFINITIVO" or numero_intento >= MAX_INTENTOS:
            actual.estado = "FALLIDO_PERMANENTE"
            actual.proximo_intento_en = None
            await _registrar_alerta_fallo(session, actual, finalizado_en)
            return actual.estado

        actual.estado = "REINTENTANDO"
        actual.proximo_intento_en = calcular_proximo_intento(
            numero_intento, finalizado_en, jitter_fn=jitter_fn
        )
        return actual.estado


async def despachar_pendientes(
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    transporte: TransporteNotificacion | None = None,
    worker_id: str = "notificaciones-worker",
    ahora: datetime | None = None,
    *,
    limite: int | None = None,
    lease: timedelta | int | float | None = None,
    jitter_fn: Callable[[], float | int] | None = None,
) -> ResumenDespacho:
    """Reclama notificaciones vencidas, las envía fuera de transacción y registra el resultado."""
    adaptador = transporte or obtener_transporte()
    momento_reclamo = ahora or datetime.now(UTC)
    reclamadas = await reclamar_lote(
        session_factory=session_factory,
        worker_id=worker_id,
        ahora=momento_reclamo,
        limite=limite,
        lease=lease,
    )
    resumen = ResumenDespacho(reclamadas=len(reclamadas))

    margen = timedelta(seconds=settings.SMTP_TIMEOUT_SEGUNDOS)
    for notificacion in reclamadas:
        # Un envío que podría terminar después del arrendamiento queda para otra pasada:
        # otro worker podría reclamarlo y se enviaría dos veces.
        if ahora is None and datetime.now(UTC) + margen >= notificacion.bloqueado_hasta:
            resumen.omitidas_arrendamiento += 1
            continue
        iniciado_en = ahora or datetime.now(UTC)
        try:
            resultado = await adaptador.enviar(notificacion)
        except TimeoutError as exc:
            resultado = ResultadoTransporte.fallo("TIMEOUT", f"Timeout de transporte: {exc}")
        except Exception as exc:
            resultado = ResultadoTransporte.fallo(
                "CONNECTION_ERROR", f"Excepción de transporte: {exc}"
            )
        finalizado_en = ahora or datetime.now(UTC)

        estado_final = await registrar_resultado_intento(
            session_factory=session_factory,
            notificacion_id=notificacion.id,
            worker_id=worker_id,
            transporte=adaptador,
            resultado=resultado,
            iniciado_en=iniciado_en,
            finalizado_en=finalizado_en,
            jitter_fn=jitter_fn,
        )
        if estado_final == "ENVIADO":
            resumen.aceptadas += 1
        elif estado_final == "ENTREGADO":
            resumen.entregadas += 1
        elif estado_final == "REINTENTANDO":
            resumen.reintentando += 1
        elif estado_final == "FALLIDO_PERMANENTE":
            resumen.fallidas_permanentes += 1
        else:
            resumen.omitidas_arrendamiento += 1

    return resumen


async def confirmar_entrega(
    session: AsyncSession,
    referencia: uuid.UUID | str | None = None,
    *,
    notificacion_id: uuid.UUID | None = None,
    proveedor_message_id: str | None = None,
    ahora: datetime | None = None,
) -> Notificacion:
    """Marca una notificación como `ENTREGADO` a partir de su ID o `proveedor_message_id`."""
    momento = ahora or datetime.now(UTC)
    target_id = notificacion_id
    target_msg_id = proveedor_message_id

    if referencia is not None:
        if isinstance(referencia, uuid.UUID):
            target_id = referencia
        elif isinstance(referencia, str):
            try:
                posible_uuid = uuid.UUID(referencia)
                target_id = posible_uuid
            except ValueError:
                target_msg_id = referencia

    notificacion: Notificacion | None = None
    if target_id is not None:
        notificacion = await session.scalar(
            select(Notificacion).where(Notificacion.id == target_id).with_for_update()
        )
        if notificacion is None and isinstance(referencia, str) and target_msg_id is None:
            target_msg_id = referencia

    if notificacion is None and target_msg_id is not None:
        notificacion = await session.scalar(
            select(Notificacion)
            .where(Notificacion.proveedor_message_id == target_msg_id)
            .with_for_update()
        )

    if notificacion is None:
        raise APIError(
            404,
            "NOTIFICACION_NO_ENCONTRADA",
            "No se encontró la notificación para confirmar su entrega.",
        )

    if notificacion.estado == "FALLIDO_PERMANENTE":
        raise APIError(
            409,
            "ENTREGA_NO_PERMITIDA",
            "No se puede confirmar la entrega de una notificación en FALLIDO_PERMANENTE.",
        )

    if notificacion.estado != "ENTREGADO":
        notificacion.estado = "ENTREGADO"
        if notificacion.aceptado_en is None:
            notificacion.aceptado_en = momento
        notificacion.entregado_en = momento
        notificacion.proximo_intento_en = None
        notificacion.bloqueado_por = None
        notificacion.bloqueado_hasta = None
        notificacion.actualizado_en = momento
        await session.flush()

    return notificacion


async def reprogramar_manual(
    session: AsyncSession,
    notificacion_id: uuid.UUID,
    nuevo_destinatario: str | None = None,
    ahora: datetime | None = None,
    *,
    atendida_por: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Notificacion:
    """Reprograma una notificación `FALLIDO_PERMANENTE` abriendo un nuevo ciclo de intentos.

    Los intentos de ciclos anteriores se conservan en `notificacion_intentos`
    (únicos por `ciclo, numero`); el contador `intentos` vuelve a 0 para el ciclo nuevo.
    """
    momento = ahora or datetime.now(UTC)
    notificacion = await session.scalar(
        select(Notificacion).where(Notificacion.id == notificacion_id).with_for_update()
    )
    if notificacion is None:
        raise APIError(
            404,
            "NOTIFICACION_NO_ENCONTRADA",
            "Registro de notificación no encontrado.",
        )

    if notificacion.estado != "FALLIDO_PERMANENTE":
        raise APIError(
            409,
            "REENVIO_NO_PERMITIDO",
            "Solo se pueden reprogramar notificaciones en estado FALLIDO_PERMANENTE.",
        )

    if nuevo_destinatario is not None and nuevo_destinatario.strip():
        limpio = nuevo_destinatario.strip()
        if not validar_destinatario(limpio, notificacion.canal):
            raise APIError(
                422,
                "DESTINATARIO_INVALIDO",
                "El nuevo destinatario no tiene un formato válido para el canal.",
            )
        notificacion.destinatario = limpio

    notificacion.ciclo += 1
    notificacion.estado = "EN_COLA"
    notificacion.intentos = 0
    notificacion.proximo_intento_en = momento
    notificacion.bloqueado_por = None
    notificacion.bloqueado_hasta = None
    notificacion.error_codigo = None
    notificacion.error_mensaje = None
    notificacion.actualizado_en = momento

    responsable = atendida_por or actor_id
    await session.execute(
        update(AlertaAdministrativa)
        .where(
            AlertaAdministrativa.notificacion_id == notificacion.id,
            AlertaAdministrativa.atendida_en.is_(None),
        )
        .values(atendida_en=momento, atendida_por=responsable)
    )

    await session.flush()
    return notificacion
