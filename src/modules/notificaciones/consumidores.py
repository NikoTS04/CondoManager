"""Consumidores transaccionales de eventos de dominio para notificaciones (CON-32/34/36).

Cada handler procesa su envelope en una sola transacción:
1. `marcar_evento_consumido` (si ya fue procesado, retorna sin duplicar).
2. Lee el estado persistido de la operación de origen cuando corresponda.
3. Resuelve los destinatarios activos del departamento en el condominio.
4. Registra cada notificación en estado `EN_COLA` mediante `registrar_notificacion`.
5. `cerrar_evento_consumido` con el conteo de notificaciones creadas.
Cualquier error revierte toda la transacción sin dejar registros parciales.

Nota de alcance (CON-04): la invitación y verificación por correo electrónico de
nuevos usuarios queda diferida para una evolución posterior al Sprint 2.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.modules.condominios.models import Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.destinatarios import (
    obtener_unidad_departamento,
    resolver_destinatarios_departamento,
)
from src.modules.notificaciones.repository import (
    NuevaNotificacion,
    cerrar_evento_consumido,
    marcar_evento_consumido,
    registrar_notificacion,
)
from src.shared.decimal_types import redondear_moneda

logger = logging.getLogger(__name__)

CONSUMIDOR_NOTIFICACIONES = "service.notificaciones"


class ErrorContratoEvento(ValueError):
    """El envelope o los datos del evento incumplen el contrato requerido."""


@dataclass(frozen=True)
class ResultadoConsumo:
    event_id: uuid.UUID
    event_type: str
    duplicado: bool
    notificaciones_creadas: int
    notificacion_ids: tuple[uuid.UUID, ...] = ()


def _parsear_uuid(nombre: str, valor: Any) -> uuid.UUID:
    if isinstance(valor, uuid.UUID):
        return valor
    if isinstance(valor, str) and valor.strip():
        try:
            return uuid.UUID(valor.strip())
        except ValueError as exc:
            raise ErrorContratoEvento(f"Campo '{nombre}' no es un UUID válido: {valor!r}") from exc
    raise ErrorContratoEvento(f"Campo obligatorio '{nombre}' ausente o inválido.")


def _validar_texto(nombre: str, valor: Any) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorContratoEvento(f"Campo obligatorio '{nombre}' ausente o vacío.")
    return valor.strip()


def _validar_decimal(nombre: str, valor: Any, *, positivo: bool = False) -> Decimal:
    if valor is None:
        raise ErrorContratoEvento(f"Campo monetario obligatorio '{nombre}' ausente.")
    if isinstance(valor, float):
        raise ErrorContratoEvento(
            f"Campo monetario '{nombre}' no permite float; use Decimal o cadena decimal."
        )
    if isinstance(valor, Decimal):
        monto = redondear_moneda(valor)
    elif isinstance(valor, int):
        monto = redondear_moneda(Decimal(valor))
    elif isinstance(valor, str) and valor.strip():
        try:
            monto = redondear_moneda(Decimal(valor.strip()))
        except InvalidOperation as exc:
            raise ErrorContratoEvento(f"Campo monetario '{nombre}' inválido: {valor!r}") from exc
    else:
        raise ErrorContratoEvento(f"Campo monetario obligatorio '{nombre}' inválido.")

    if positivo and monto <= Decimal("0.00"):
        raise ErrorContratoEvento(f"Campo monetario '{nombre}' debe ser mayor que 0.00.")
    if not positivo and monto < Decimal("0.00"):
        raise ErrorContratoEvento(f"Campo monetario '{nombre}' no puede ser negativo.")
    return monto


def _validar_envelope(envelope: dict[str, Any]) -> tuple[uuid.UUID, str, dict[str, Any]]:
    if not isinstance(envelope, dict):
        raise ErrorContratoEvento("El envelope del evento debe ser un diccionario.")
    event_id = _parsear_uuid("event_id", envelope.get("event_id"))
    event_type = _validar_texto("event_type", envelope.get("event_type"))
    _validar_texto("producer", envelope.get("producer"))
    _validar_texto("occurred_at", envelope.get("occurred_at"))
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise ErrorContratoEvento("El campo 'data' del envelope debe ser un objeto JSON.")
    return event_id, event_type, data


async def _ejecutar_en_transaccion(session: AsyncSession, fn, *args, **kwargs):
    if session.in_transaction():
        try:
            resultado = await fn(session, *args, **kwargs)
            await session.commit()
            return resultado
        except Exception:
            await session.rollback()
            raise
    async with session.begin():
        return await fn(session, *args, **kwargs)


async def _tabla_existe(session: AsyncSession, nombre_tabla: str) -> bool:
    regclass = await session.scalar(
        text("SELECT to_regclass(:tabla)"),
        {"tabla": nombre_tabla},
    )
    return regclass is not None


async def _leer_comprobante_persistido(
    session: AsyncSession, comprobante_id: uuid.UUID
) -> dict[str, Any] | None:
    if not await _tabla_existe(session, "comprobantes_pago"):
        return None
    resultado = await session.execute(
        text("SELECT * FROM comprobantes_pago WHERE id = :id"),
        {"id": comprobante_id},
    )
    fila = resultado.mappings().first()
    return dict(fila) if fila is not None else None


async def _leer_reserva_persistida(
    session: AsyncSession, reserva_id: uuid.UUID
) -> dict[str, Any] | None:
    if not await _tabla_existe(session, "reservas"):
        return None
    resultado = await session.execute(
        text("SELECT * FROM reservas WHERE id = :id"),
        {"id": reserva_id},
    )
    fila = resultado.mappings().first()
    return dict(fila) if fila is not None else None


async def _leer_area_persistida(session: AsyncSession, area_id: uuid.UUID) -> dict[str, Any] | None:
    if not await _tabla_existe(session, "areas_comunes"):
        return None
    resultado = await session.execute(
        text("SELECT * FROM areas_comunes WHERE id = :id"),
        {"id": area_id},
    )
    fila = resultado.mappings().first()
    return dict(fila) if fila is not None else None


def _obtener_medios_pago(data: dict[str, Any]) -> str:
    desde_evento = data.get("medios_pago") or data.get("cci_banco")
    if isinstance(desde_evento, str) and desde_evento.strip():
        return desde_evento.strip()
    return settings.NOTIFICACIONES_MEDIOS_PAGO


async def _procesar_cuotas_emitidas(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    event_id, event_type, data = _validar_envelope(envelope)
    condominio_id = _parsear_uuid("condominio_id", data.get("condominio_id"))
    periodo = _validar_texto("periodo", data.get("periodo"))

    es_nuevo = await marcar_evento_consumido(
        session, CONSUMIDOR_NOTIFICACIONES, event_id, event_type
    )
    if not es_nuevo:
        return ResultadoConsumo(
            event_id=event_id,
            event_type=event_type,
            duplicado=True,
            notificaciones_creadas=0,
        )

    filas = (
        await session.execute(
            select(CuotaMantenimiento, Departamento, Edificio)
            .join(Departamento, Departamento.id == CuotaMantenimiento.departamento_id)
            .join(Edificio, Edificio.id == Departamento.edificio_id)
            .where(
                Edificio.condominio_id == condominio_id,
                CuotaMantenimiento.periodo == periodo,
            )
            .order_by(Departamento.id, CuotaMantenimiento.id)
        )
    ).all()

    medios_pago = _obtener_medios_pago(data)
    canal = str(data.get("canal") or "EMAIL").strip().upper()
    ids_creados: list[uuid.UUID] = []

    for cuota, departamento, edificio in filas:
        destinatarios = await resolver_destinatarios_departamento(
            session, departamento.id, condominio_id
        )
        if not destinatarios:
            continue

        etiqueta_dpto = f"{departamento.numero} ({edificio.nombre_bloque})"
        monto_exigible = f"{redondear_moneda(cuota.monto_total_exigible):.2f}"
        monto_pendiente = f"{redondear_moneda(cuota.monto_pendiente):.2f}"
        vencimiento_str = cuota.fecha_vencimiento.isoformat()

        for dest in destinatarios:
            clave = f"CUOTA:{cuota.id}:NOTIF_EMISION_CUOTA:{canal}:{dest.usuario_id}"
            contexto = {
                "nombre": dest.nombre_completo,
                "dpto": etiqueta_dpto,
                "numero_departamento": departamento.numero,
                "edificio": edificio.nombre_bloque,
                "periodo": cuota.periodo,
                "monto": monto_exigible,
                "monto_total_exigible": monto_exigible,
                "monto_pendiente": monto_pendiente,
                "vencimiento": vencimiento_str,
                "cci_banco": medios_pago,
                "medios_pago": medios_pago,
                "cuota_id": str(cuota.id),
            }
            notif_id = await registrar_notificacion(
                session,
                NuevaNotificacion(
                    condominio_id=condominio_id,
                    departamento_id=departamento.id,
                    usuario_id=dest.usuario_id,
                    evento_id=event_id,
                    tipo_evento=event_type,
                    plantilla="NOTIF_EMISION_CUOTA",
                    origen_tipo="CUOTA",
                    origen_id=cuota.id,
                    clave_deduplicacion=clave,
                    canal=canal,
                    destinatario=dest.email,
                    contexto=contexto,
                ),
                ahora=ahora,
            )
            if notif_id is not None:
                ids_creados.append(notif_id)

    await cerrar_evento_consumido(session, CONSUMIDOR_NOTIFICACIONES, event_id, len(ids_creados))
    return ResultadoConsumo(
        event_id=event_id,
        event_type=event_type,
        duplicado=False,
        notificaciones_creadas=len(ids_creados),
        notificacion_ids=tuple(ids_creados),
    )


async def _procesar_pago_reportado(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    event_id, event_type, data = _validar_envelope(envelope)
    comprobante_id = _parsear_uuid("comprobante_id", data.get("comprobante_id"))
    condominio_id = _parsear_uuid("condominio_id", data.get("condominio_id"))
    departamento_id = _parsear_uuid("departamento_id", data.get("departamento_id"))

    es_nuevo = await marcar_evento_consumido(
        session, CONSUMIDOR_NOTIFICACIONES, event_id, event_type
    )
    if not es_nuevo:
        return ResultadoConsumo(
            event_id=event_id,
            event_type=event_type,
            duplicado=True,
            notificaciones_creadas=0,
        )

    unidad = await obtener_unidad_departamento(session, departamento_id, condominio_id)
    if unidad is None:
        raise ErrorContratoEvento(
            "El departamento indicado no existe o no pertenece al condominio del evento."
        )

    comprobante_bd = await _leer_comprobante_persistido(session, comprobante_id)
    if comprobante_bd is not None:
        dpto_bd = comprobante_bd.get("departamento_id")
        if dpto_bd is not None and _parsear_uuid("departamento_id", dpto_bd) != departamento_id:
            raise ErrorContratoEvento(
                "El comprobante persistido no pertenece al departamento del evento."
            )

    monto_raw = (
        comprobante_bd.get("monto")
        if comprobante_bd is not None and comprobante_bd.get("monto") is not None
        else data.get("monto")
    )
    monto = _validar_decimal("monto", monto_raw, positivo=True)

    banco_raw = (
        (
            (comprobante_bd.get("banco_origen") or comprobante_bd.get("banco"))
            if comprobante_bd is not None
            else None
        )
        or data.get("banco")
        or data.get("banco_origen")
    )
    banco = _validar_texto("banco", banco_raw)

    operacion_raw = (
        comprobante_bd.get("numero_operacion") if comprobante_bd is not None else None
    ) or data.get("numero_operacion")
    numero_operacion = _validar_texto("numero_operacion", operacion_raw)

    fecha_op_raw = (
        comprobante_bd.get("fecha_operacion") if comprobante_bd is not None else None
    ) or data.get("fecha_operacion")
    fecha_operacion = (
        fecha_op_raw.isoformat()
        if hasattr(fecha_op_raw, "isoformat")
        else (str(fecha_op_raw).strip() if fecha_op_raw is not None else None)
    )

    destinatarios = await resolver_destinatarios_departamento(
        session, departamento_id, condominio_id
    )
    canal = str(data.get("canal") or "EMAIL").strip().upper()
    plantilla = "NOTIF_PAGO_RECIBIDO"
    ids_creados: list[uuid.UUID] = []

    for dest in destinatarios:
        clave = f"COMPROBANTE:{comprobante_id}:{plantilla}:{canal}:{dest.usuario_id}"
        contexto: dict[str, Any] = {
            "nombre": dest.nombre_completo,
            "dpto": unidad.etiqueta_dpto,
            "numero_departamento": unidad.numero,
            "edificio": unidad.edificio_nombre,
            "comprobante_id": str(comprobante_id),
            "monto": f"{monto:.2f}",
            "banco": banco,
            "numero_operacion": numero_operacion,
        }
        if fecha_operacion:
            contexto["fecha_operacion"] = fecha_operacion

        notif_id = await registrar_notificacion(
            session,
            NuevaNotificacion(
                condominio_id=condominio_id,
                departamento_id=departamento_id,
                usuario_id=dest.usuario_id,
                evento_id=event_id,
                tipo_evento=event_type,
                plantilla=plantilla,
                origen_tipo="COMPROBANTE",
                origen_id=comprobante_id,
                clave_deduplicacion=clave,
                canal=canal,
                destinatario=dest.email,
                contexto=contexto,
            ),
            ahora=ahora,
        )
        if notif_id is not None:
            ids_creados.append(notif_id)

    await cerrar_evento_consumido(session, CONSUMIDOR_NOTIFICACIONES, event_id, len(ids_creados))
    return ResultadoConsumo(
        event_id=event_id,
        event_type=event_type,
        duplicado=False,
        notificaciones_creadas=len(ids_creados),
        notificacion_ids=tuple(ids_creados),
    )


async def _procesar_pago_revisado(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    event_id, event_type, data = _validar_envelope(envelope)
    comprobante_id = _parsear_uuid("comprobante_id", data.get("comprobante_id"))
    departamento_id = _parsear_uuid("departamento_id", data.get("departamento_id"))

    # Soportar condominio_id explícito o resolverlo cuando venga de PagoConciliadoEvent legado
    condominio_raw = data.get("condominio_id")
    condominio_id = (
        _parsear_uuid("condominio_id", condominio_raw) if condominio_raw is not None else None
    )

    es_nuevo = await marcar_evento_consumido(
        session, CONSUMIDOR_NOTIFICACIONES, event_id, event_type
    )
    if not es_nuevo:
        return ResultadoConsumo(
            event_id=event_id,
            event_type=event_type,
            duplicado=True,
            notificaciones_creadas=0,
        )

    unidad = await obtener_unidad_departamento(session, departamento_id, condominio_id)
    if unidad is None:
        raise ErrorContratoEvento(
            "El departamento indicado no existe o no pertenece al condominio del evento."
        )
    condominio_id = unidad.condominio_id

    resultado_raw = data.get("resultado")
    if resultado_raw is None and event_type == "PagoConciliadoEvent":
        resultado_raw = "APROBADO"
    resultado = _validar_texto("resultado", resultado_raw).upper()
    if resultado not in ("APROBADO", "OBSERVADO", "RECHAZADO"):
        raise ErrorContratoEvento(f"Resultado de revisión inválido en {event_type}: {resultado!r}")

    comprobante_bd = await _leer_comprobante_persistido(session, comprobante_id)
    if comprobante_bd is not None:
        dpto_bd = comprobante_bd.get("departamento_id")
        if dpto_bd is not None and _parsear_uuid("departamento_id", dpto_bd) != departamento_id:
            raise ErrorContratoEvento(
                "El comprobante persistido no pertenece al departamento del evento."
            )
        estado_bd = str(comprobante_bd.get("estado") or "").strip().upper()
        if estado_bd and estado_bd != resultado:
            raise ErrorContratoEvento(
                f"El estado persistido del comprobante ({estado_bd}) no coincide con el resultado del evento ({resultado})."
            )

    contexto_base: dict[str, Any] = {
        "dpto": unidad.etiqueta_dpto,
        "numero_departamento": unidad.numero,
        "edificio": unidad.edificio_nombre,
        "comprobante_id": str(comprobante_id),
        "resultado": resultado,
    }
    if data.get("revisado_en"):
        contexto_base["revisado_en"] = str(data["revisado_en"])

    if resultado == "APROBADO":
        plantilla = "NOTIF_PAGO_CONCILIADO"
        monto_aplicado_raw = (
            comprobante_bd.get("monto_aplicado")
            if comprobante_bd is not None and comprobante_bd.get("monto_aplicado") is not None
            else (
                data.get("monto_aplicado")
                if data.get("monto_aplicado") is not None
                else (
                    data.get("monto_conciliado")
                    if data.get("monto_conciliado") is not None
                    else (comprobante_bd.get("monto") if comprobante_bd is not None else None)
                )
            )
        )
        saldo_resultante_raw = (
            comprobante_bd.get("saldo_resultante")
            if comprobante_bd is not None and comprobante_bd.get("saldo_resultante") is not None
            else (
                data.get("saldo_resultante")
                if data.get("saldo_resultante") is not None
                else data.get("saldo_restante_departamento")
            )
        )
        monto_aplicado = _validar_decimal("monto_aplicado", monto_aplicado_raw, positivo=True)
        # Regla crítica CON-34: nunca inventar saldo_resultante (no default 0.00)
        saldo_resultante = _validar_decimal(
            "saldo_resultante", saldo_resultante_raw, positivo=False
        )
        contexto_base["monto_aplicado"] = f"{monto_aplicado:.2f}"
        contexto_base["monto_abonado"] = f"{monto_aplicado:.2f}"
        contexto_base["saldo_resultante"] = f"{saldo_resultante:.2f}"
        contexto_base["saldo_restante"] = f"{saldo_resultante:.2f}"
        if data.get("recibo_url"):
            contexto_base["recibo_url"] = str(data["recibo_url"]).strip()

    elif resultado == "OBSERVADO":
        plantilla = "NOTIF_PAGO_OBSERVADO"
        motivo_raw = (
            (comprobante_bd.get("motivo_rechazo") if comprobante_bd is not None else None)
            or data.get("motivo")
            or data.get("motivo_rechazo")
        )
        instrucciones_raw = (
            comprobante_bd.get("instrucciones") if comprobante_bd is not None else None
        ) or data.get("instrucciones")
        motivo = _validar_texto("motivo", motivo_raw)
        instrucciones = _validar_texto("instrucciones", instrucciones_raw)
        contexto_base["motivo"] = motivo
        contexto_base["instrucciones"] = instrucciones
        if data.get("enlace_subir_nuevo"):
            contexto_base["enlace_subir_nuevo"] = str(data["enlace_subir_nuevo"]).strip()

    else:  # RECHAZADO
        plantilla = "NOTIF_PAGO_RECHAZADO"
        motivo_raw = (
            (comprobante_bd.get("motivo_rechazo") if comprobante_bd is not None else None)
            or data.get("motivo")
            or data.get("motivo_rechazo")
        )
        instrucciones_raw = (
            comprobante_bd.get("instrucciones") if comprobante_bd is not None else None
        ) or data.get("instrucciones")
        motivo = _validar_texto("motivo", motivo_raw)
        instrucciones = _validar_texto("instrucciones", instrucciones_raw)
        contexto_base["motivo"] = motivo
        contexto_base["motivo_rechazo"] = motivo
        contexto_base["instrucciones"] = instrucciones
        if data.get("enlace_subir_nuevo"):
            contexto_base["enlace_subir_nuevo"] = str(data["enlace_subir_nuevo"]).strip()

    destinatarios = await resolver_destinatarios_departamento(
        session, departamento_id, condominio_id
    )
    canal = str(data.get("canal") or "EMAIL").strip().upper()
    ids_creados: list[uuid.UUID] = []

    for dest in destinatarios:
        clave = f"COMPROBANTE:{comprobante_id}:{plantilla}:{canal}:{dest.usuario_id}"
        contexto = {
            **contexto_base,
            "nombre": dest.nombre_completo,
        }
        notif_id = await registrar_notificacion(
            session,
            NuevaNotificacion(
                condominio_id=condominio_id,
                departamento_id=departamento_id,
                usuario_id=dest.usuario_id,
                evento_id=event_id,
                tipo_evento=event_type,
                plantilla=plantilla,
                origen_tipo="COMPROBANTE",
                origen_id=comprobante_id,
                clave_deduplicacion=clave,
                canal=canal,
                destinatario=dest.email,
                contexto=contexto,
            ),
            ahora=ahora,
        )
        if notif_id is not None:
            ids_creados.append(notif_id)

    await cerrar_evento_consumido(session, CONSUMIDOR_NOTIFICACIONES, event_id, len(ids_creados))
    return ResultadoConsumo(
        event_id=event_id,
        event_type=event_type,
        duplicado=False,
        notificaciones_creadas=len(ids_creados),
        notificacion_ids=tuple(ids_creados),
    )


def _resolver_horario_reserva(data: dict[str, Any], reserva_bd: dict[str, Any] | None) -> str:
    horario = data.get("horario")
    if isinstance(horario, str) and horario.strip():
        return horario.strip()
    hora_inicio = data.get("hora_inicio") or (
        reserva_bd.get("hora_inicio") if reserva_bd is not None else None
    )
    hora_fin = data.get("hora_fin") or (
        reserva_bd.get("hora_fin") if reserva_bd is not None else None
    )
    if hora_inicio is not None and hora_fin is not None:
        ini_str = (
            hora_inicio.strftime("%H:%M")
            if hasattr(hora_inicio, "strftime")
            else str(hora_inicio).strip()
        )
        fin_str = (
            hora_fin.strftime("%H:%M") if hasattr(hora_fin, "strftime") else str(hora_fin).strip()
        )
        if ini_str and fin_str:
            return f"{ini_str} - {fin_str}"
    raise ErrorContratoEvento("Campo obligatorio 'horario' (o hora_inicio/hora_fin) ausente.")


async def _procesar_reserva_confirmada(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    event_id, event_type, data = _validar_envelope(envelope)
    reserva_id = _parsear_uuid("reserva_id", data.get("reserva_id"))
    departamento_id = _parsear_uuid("departamento_id", data.get("departamento_id"))
    condominio_raw = data.get("condominio_id")
    condominio_id = (
        _parsear_uuid("condominio_id", condominio_raw) if condominio_raw is not None else None
    )

    es_nuevo = await marcar_evento_consumido(
        session, CONSUMIDOR_NOTIFICACIONES, event_id, event_type
    )
    if not es_nuevo:
        return ResultadoConsumo(
            event_id=event_id,
            event_type=event_type,
            duplicado=True,
            notificaciones_creadas=0,
        )

    unidad = await obtener_unidad_departamento(session, departamento_id, condominio_id)
    if unidad is None:
        raise ErrorContratoEvento(
            "El departamento de la reserva no existe o no pertenece al condominio indicado."
        )
    condominio_id = unidad.condominio_id

    reserva_bd = await _leer_reserva_persistida(session, reserva_id)
    if reserva_bd is not None:
        dpto_bd = reserva_bd.get("departamento_id")
        if dpto_bd is not None and _parsear_uuid("departamento_id", dpto_bd) != departamento_id:
            raise ErrorContratoEvento(
                "La reserva persistida no pertenece al departamento indicado en el evento."
            )

    area_id_raw = data.get("area_id") or (
        reserva_bd.get("area_id") if reserva_bd is not None else None
    )
    area_bd = (
        await _leer_area_persistida(session, _parsear_uuid("area_id", area_id_raw))
        if area_id_raw is not None
        else None
    )

    area_raw = (
        data.get("area")
        or data.get("area_nombre")
        or (area_bd.get("nombre") if area_bd is not None else None)
    )
    area = _validar_texto("area", area_raw)

    fecha_raw = (
        data.get("fecha_reserva")
        or data.get("fecha")
        or (reserva_bd.get("fecha_reserva") if reserva_bd is not None else None)
    )
    if hasattr(fecha_raw, "isoformat"):
        fecha_raw = fecha_raw.isoformat()
    fecha = _validar_texto("fecha_reserva", fecha_raw)

    horario = _resolver_horario_reserva(data, reserva_bd)

    costo_raw = (
        data.get("costo")
        if data.get("costo") is not None
        else (
            data.get("costo_reserva")
            if data.get("costo_reserva") is not None
            else (
                reserva_bd.get("costo_reserva")
                if reserva_bd is not None and reserva_bd.get("costo_reserva") is not None
                else (area_bd.get("costo_reserva") if area_bd is not None else None)
            )
        )
    )
    costo = _validar_decimal("costo", costo_raw, positivo=False)

    normas_raw = (
        data.get("normas_convivencia")
        or data.get("normas")
        or (area_bd.get("descripcion") if area_bd is not None else None)
    )
    normas = _validar_texto("normas_convivencia", normas_raw)

    destinatarios = await resolver_destinatarios_departamento(
        session, departamento_id, condominio_id
    )
    canal = str(data.get("canal") or "EMAIL").strip().upper()
    plantilla = "NOTIF_RESERVA_CONFIRMADA"
    ids_creados: list[uuid.UUID] = []

    for dest in destinatarios:
        clave = f"RESERVA:{reserva_id}:{plantilla}:{canal}:{dest.usuario_id}"
        contexto = {
            "nombre": dest.nombre_completo,
            "dpto": unidad.etiqueta_dpto,
            "numero_departamento": unidad.numero,
            "edificio": unidad.edificio_nombre,
            "reserva_id": str(reserva_id),
            "area": area,
            "fecha": fecha,
            "fecha_reserva": fecha,
            "horario": horario,
            "costo": f"{costo:.2f}",
            "normas_convivencia": normas,
        }
        notif_id = await registrar_notificacion(
            session,
            NuevaNotificacion(
                condominio_id=condominio_id,
                departamento_id=departamento_id,
                usuario_id=dest.usuario_id,
                evento_id=event_id,
                tipo_evento=event_type,
                plantilla=plantilla,
                origen_tipo="RESERVA",
                origen_id=reserva_id,
                clave_deduplicacion=clave,
                canal=canal,
                destinatario=dest.email,
                contexto=contexto,
            ),
            ahora=ahora,
        )
        if notif_id is not None:
            ids_creados.append(notif_id)

    await cerrar_evento_consumido(session, CONSUMIDOR_NOTIFICACIONES, event_id, len(ids_creados))
    return ResultadoConsumo(
        event_id=event_id,
        event_type=event_type,
        duplicado=False,
        notificaciones_creadas=len(ids_creados),
        notificacion_ids=tuple(ids_creados),
    )


async def _procesar_reserva_cancelada(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    event_id, event_type, data = _validar_envelope(envelope)
    reserva_id = _parsear_uuid("reserva_id", data.get("reserva_id"))
    departamento_id = _parsear_uuid("departamento_id", data.get("departamento_id"))
    condominio_raw = data.get("condominio_id")
    condominio_id = (
        _parsear_uuid("condominio_id", condominio_raw) if condominio_raw is not None else None
    )

    es_nuevo = await marcar_evento_consumido(
        session, CONSUMIDOR_NOTIFICACIONES, event_id, event_type
    )
    if not es_nuevo:
        return ResultadoConsumo(
            event_id=event_id,
            event_type=event_type,
            duplicado=True,
            notificaciones_creadas=0,
        )

    unidad = await obtener_unidad_departamento(session, departamento_id, condominio_id)
    if unidad is None:
        raise ErrorContratoEvento(
            "El departamento de la reserva no existe o no pertenece al condominio indicado."
        )
    condominio_id = unidad.condominio_id

    reserva_bd = await _leer_reserva_persistida(session, reserva_id)
    if reserva_bd is not None:
        dpto_bd = reserva_bd.get("departamento_id")
        if dpto_bd is not None and _parsear_uuid("departamento_id", dpto_bd) != departamento_id:
            raise ErrorContratoEvento(
                "La reserva persistida no pertenece al departamento indicado en el evento."
            )

    area_id_raw = data.get("area_id") or (
        reserva_bd.get("area_id") if reserva_bd is not None else None
    )
    area_bd = (
        await _leer_area_persistida(session, _parsear_uuid("area_id", area_id_raw))
        if area_id_raw is not None
        else None
    )

    area_raw = (
        data.get("area")
        or data.get("area_nombre")
        or (area_bd.get("nombre") if area_bd is not None else None)
    )
    area = _validar_texto("area", area_raw)

    fecha_raw = (
        data.get("fecha_reserva")
        or data.get("fecha")
        or (reserva_bd.get("fecha_reserva") if reserva_bd is not None else None)
    )
    if hasattr(fecha_raw, "isoformat"):
        fecha_raw = fecha_raw.isoformat()
    fecha = _validar_texto("fecha_reserva", fecha_raw)

    horario = _resolver_horario_reserva(data, reserva_bd)
    motivo = _validar_texto("motivo", data.get("motivo"))

    ajuste_economico = data.get("ajuste_economico")
    monto_reembolso_raw = data.get("monto_reembolso")
    monto_reembolso_str: str | None = None
    if monto_reembolso_raw is not None:
        monto_reembolso = _validar_decimal("monto_reembolso", monto_reembolso_raw, positivo=False)
        monto_reembolso_str = f"{monto_reembolso:.2f}"
        if not ajuste_economico:
            if monto_reembolso > Decimal("0.00"):
                ajuste_economico = f"Reembolso / ajuste aplicable: S/ {monto_reembolso_str}"
            else:
                ajuste_economico = "Sin cargo ni reembolso pendiente (S/ 0.00)"

    if not ajuste_economico:
        ajuste_economico = "Sin ajuste económico aplicable"

    destinatarios = await resolver_destinatarios_departamento(
        session, departamento_id, condominio_id
    )
    canal = str(data.get("canal") or "EMAIL").strip().upper()
    plantilla = "NOTIF_RESERVA_CANCELADA"
    ids_creados: list[uuid.UUID] = []

    for dest in destinatarios:
        clave = f"RESERVA:{reserva_id}:{plantilla}:{canal}:{dest.usuario_id}"
        contexto: dict[str, Any] = {
            "nombre": dest.nombre_completo,
            "dpto": unidad.etiqueta_dpto,
            "numero_departamento": unidad.numero,
            "edificio": unidad.edificio_nombre,
            "reserva_id": str(reserva_id),
            "area": area,
            "fecha": fecha,
            "fecha_reserva": fecha,
            "horario": horario,
            "motivo": motivo,
            "ajuste_economico": str(ajuste_economico).strip(),
        }
        if monto_reembolso_str is not None:
            contexto["monto_reembolso"] = monto_reembolso_str

        notif_id = await registrar_notificacion(
            session,
            NuevaNotificacion(
                condominio_id=condominio_id,
                departamento_id=departamento_id,
                usuario_id=dest.usuario_id,
                evento_id=event_id,
                tipo_evento=event_type,
                plantilla=plantilla,
                origen_tipo="RESERVA",
                origen_id=reserva_id,
                clave_deduplicacion=clave,
                canal=canal,
                destinatario=dest.email,
                contexto=contexto,
            ),
            ahora=ahora,
        )
        if notif_id is not None:
            ids_creados.append(notif_id)

    await cerrar_evento_consumido(session, CONSUMIDOR_NOTIFICACIONES, event_id, len(ids_creados))
    return ResultadoConsumo(
        event_id=event_id,
        event_type=event_type,
        duplicado=False,
        notificaciones_creadas=len(ids_creados),
        notificacion_ids=tuple(ids_creados),
    )


async def consumir_cuotas_emitidas(
    session: AsyncSession, envelope: dict[str, Any], ahora: datetime | None = None
) -> ResultadoConsumo:
    return await _ejecutar_en_transaccion(session, _procesar_cuotas_emitidas, envelope, ahora=ahora)


async def consumir_pago_reportado(
    session: AsyncSession, envelope: dict[str, Any], ahora: datetime | None = None
) -> ResultadoConsumo:
    return await _ejecutar_en_transaccion(session, _procesar_pago_reportado, envelope, ahora=ahora)


async def consumir_pago_revisado(
    session: AsyncSession, envelope: dict[str, Any], ahora: datetime | None = None
) -> ResultadoConsumo:
    return await _ejecutar_en_transaccion(session, _procesar_pago_revisado, envelope, ahora=ahora)


async def consumir_reserva_confirmada(
    session: AsyncSession, envelope: dict[str, Any], ahora: datetime | None = None
) -> ResultadoConsumo:
    return await _ejecutar_en_transaccion(
        session, _procesar_reserva_confirmada, envelope, ahora=ahora
    )


async def consumir_reserva_cancelada(
    session: AsyncSession, envelope: dict[str, Any], ahora: datetime | None = None
) -> ResultadoConsumo:
    return await _ejecutar_en_transaccion(
        session, _procesar_reserva_cancelada, envelope, ahora=ahora
    )


MANEJADORES_EVENTOS = {
    "CuotasEmitidasEvent": _procesar_cuotas_emitidas,
    "CuotaEmitidaEvent": _procesar_cuotas_emitidas,
    "PagoReportadoEvent": _procesar_pago_reportado,
    "PagoRevisadoEvent": _procesar_pago_revisado,
    "PagoConciliadoEvent": _procesar_pago_revisado,
    "ReservaConfirmadaEvent": _procesar_reserva_confirmada,
    "ReservaCanceladaEvent": _procesar_reserva_cancelada,
}


async def consumir_evento(
    session: AsyncSession,
    envelope: dict[str, Any],
    ahora: datetime | None = None,
) -> ResultadoConsumo:
    """Despacha un envelope de evento a su handler registrado en una sola transacción."""
    _, event_type, _ = _validar_envelope(envelope)
    manejador = MANEJADORES_EVENTOS.get(event_type)
    if manejador is None:
        raise ErrorContratoEvento(f"Tipo de evento no soportado: {event_type!r}")
    return await _ejecutar_en_transaccion(session, manejador, envelope, ahora=ahora)
