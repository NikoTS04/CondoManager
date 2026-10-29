"""Consumo durable de productores reales; nunca reaplica operaciones financieras."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento, EventoLoteOutbox
from src.modules.notificaciones.models import EventoConsumido, IncidenciaEvento
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.templates import PlantillaIncompletaError
from src.modules.pagos.fondos_models import EventoFondoMorasOutbox
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.models_mora import EventoMoraOutbox
from src.modules.pagos.models_persistencia import EventoPagoOutbox
from src.modules.reservas.models import EventoReservaOutbox, Reserva

TIPOS = {
    "FondosMorasActualizadosEvent": (EventoFondoMorasOutbox, None),
    "MoraAplicadaEvent": (EventoMoraOutbox, "NOTIF_MORA_DIARIA"),
    "MoraAjustadaEvent": (EventoMoraOutbox, "NOTIF_MORA_DIARIA"),
    "CuotasEmitidasEvent": (EventoLoteOutbox, "NOTIF_EMISION_CUOTA"),
    "PagoReportadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_RECIBIDO"),
    "PagoConciliadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_CONCILIADO"),
    "PagoObservadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_OBSERVADO"),
    "PagoRechazadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_RECHAZADO"),
    "PagoRevisadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_OBSERVADO"),
    "ReservaConfirmadaEvent": (EventoReservaOutbox, "NOTIF_RESERVA_CONFIRMADA"),
    "ReservaCanceladaEvent": (EventoReservaOutbox, "NOTIF_RESERVA_CANCELADA"),
}


# El esquema no persiste cuentas ni CCI del condominio: se remite a la administración
# en lugar de mostrar un dato bancario inventado.
MEDIOS_PAGO = "Consulte los medios de pago vigentes con la administración del condominio."
NORMAS_USO = "Consulte las normas de uso vigentes del área común con la administración."


async def consumir(session_factory, payload):
    """Solo confirma consumo después de persistir avisos o una incidencia recuperable."""
    try:
        if not isinstance(payload, dict) or payload.get("event_type") not in TIPOS:
            raise ValueError("TIPO_EVENTO_NO_SOPORTADO")
        tipo = payload["event_type"]
        modelo, plantilla = TIPOS[tipo]
        eid = UUID(payload["event_id"])
        if modelo is EventoLoteOutbox:
            version = payload.get("schema_version", 1)
            if version not in (1, 2) or (
                version == 2 and payload.get("data", {}).get("metodo") != "JERARQUICA"
            ):
                raise ValueError("VERSION_CUOTAS_NO_SOPORTADA")
        if modelo is EventoPagoOutbox:
            canonico = "schema_version" in payload
            if payload.get("schema_version" if canonico else "version") != 1:
                raise ValueError("VERSION_PAGO_NO_SOPORTADA")
            if tipo == "PagoRevisadoEvent":
                estado = payload["data"]["estado_final"]
                if estado not in {"OBSERVADO", "RECHAZADO"} or not canonico:
                    raise ValueError("ESTADO_PAGO_INVALIDO")
                plantilla = (
                    "NOTIF_PAGO_OBSERVADO" if estado == "OBSERVADO" else "NOTIF_PAGO_RECHAZADO"
                )
        if modelo is EventoReservaOutbox and payload.get("schema_version") != 1:
            raise ValueError("VERSION_RESERVA_NO_SOPORTADA")
        if modelo is EventoMoraOutbox and payload.get("schema_version") != 2:
            raise ValueError("VERSION_MORA_NO_SOPORTADA")
        if modelo is EventoFondoMorasOutbox and payload.get("schema_version") != 1:
            raise ValueError("VERSION_FONDOS_NO_SOPORTADA")
        async with session_factory() as db, db.begin():
            original = await db.get(modelo, eid)
            # El evento debe representar exactamente una operación ya confirmada.
            if original is None or original.payload != payload:
                raise ValueError("EVENTO_SIN_ORIGEN_CONFIRMADO")
            claim = await db.execute(
                insert(EventoConsumido)
                .values(
                    consumidor="notificaciones-v1",
                    event_id=eid,
                    procesado_en=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
                .returning(EventoConsumido.event_id)
            )
            if claim.scalar_one_or_none() is None:
                return 0
            data = payload["data"]
            cid = UUID(data["condominio_id"])
            condominio = await db.get(Condominio, cid)
            if condominio is None:
                raise ValueError("CONTEXTO_EVENTO_INVALIDO")
            if modelo is EventoFondoMorasOutbox:
                # Evento interno de tesorería: se reconoce, no se envía deuda ajena a residentes.
                return 0
            repo = NotificacionesRepository(db)
            if tipo == "CuotasEmitidasEvent":
                cuotas = list(
                    await db.scalars(
                        select(CuotaMantenimiento)
                        .join(Departamento)
                        .join(Edificio)
                        .where(
                            Edificio.condominio_id == cid,
                            CuotaMantenimiento.periodo == data["periodo"],
                        )
                    )
                )
                operaciones = [
                    (
                        c.id,
                        c.departamento_id,
                        {
                            "periodo": c.periodo,
                            "monto": f"{c.monto_total_exigible:.2f}",
                            "vencimiento": c.fecha_vencimiento.isoformat(),
                            "medios_pago": MEDIOS_PAGO,
                        },
                    )
                    for c in cuotas
                ]
            elif modelo is EventoMoraOutbox:
                did = UUID(data["departamento_id"])
                operaciones = [
                    (
                        UUID(data["devengo_id"]),
                        did,
                        {
                            "fecha_local": data["fecha_local"],
                            "monto_mora": data["importe"],
                            "nuevo_saldo": data["saldo_pendiente"],
                            "moneda": data["moneda"],
                            "tipo_movimiento": "Cargo" if tipo == "MoraAplicadaEvent" else "Ajuste",
                        },
                    )
                ]
            else:
                did = UUID(data["departamento_id"])
                operacion = UUID(data.get("reserva_id") or data["comprobante_id"])
                contexto = dict(data)
                if tipo.startswith("Pago"):
                    comprobante = await db.get(ComprobantePago, operacion)
                    # El mensaje usa la instantánea de la revisión, no el saldo actual.
                    resultado = data if canonico else data.get("resultado", {})
                    contexto.update(
                        monto=data.get("monto", f"{comprobante.monto:.2f}"),
                        monto_abonado=resultado.get("monto_imputado"),
                        saldo_restante=resultado.get("nuevo_saldo_departamento"),
                        motivo_rechazo=data.get("motivo_rechazo" if canonico else "motivo"),
                        banco=comprobante.banco_origen,
                        numero_operacion=comprobante.numero_operacion,
                    )
                else:
                    reserva = await db.get(Reserva, operacion)
                    contexto.update(
                        area=data.get("area_nombre") or reserva.area_nombre,
                        fecha=data["fecha_reserva"],
                        horario=f"{data['hora_inicio']}–{data['hora_fin']} ({data['zona_horaria']})",
                    )
                    # La cancelación v1 no publica tarifa; solo la confirmación la comunica.
                    if tipo == "ReservaConfirmadaEvent":
                        contexto.update(
                            normas_convivencia=data.get("normas_uso") or NORMAS_USO,
                            costo=data["costo_reserva"],
                        )
                    else:
                        contexto["motivo"] = data["motivo"]
                        contexto["ajuste"] = data["ajuste_economico"]["estado"]
                operaciones = [(operacion, did, contexto)]
            total = 0
            for operacion, did, contexto in operaciones:
                for u, d, contacto in await repo.destinatarios(cid, did):
                    await repo.encolar(
                        cid=cid,
                        did=did,
                        usuario=u,
                        contacto=contacto,
                        evento=eid,
                        operacion=operacion,
                        tipo=plantilla,
                        canal="EMAIL",
                        contexto={
                            **contexto,
                            "nombre": u.nombre,
                            "dpto": d.numero,
                            "moneda": "S/"
                            if contexto.get("moneda", condominio.moneda) == "PEN"
                            else "USD",
                        },
                    )
                    total += 1
            return total
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        # No guardar payloads: podrían contener contactos o información sensible.
        motivo = (
            "DATOS_PLANTILLA_INCOMPLETOS"
            if isinstance(exc, PlantillaIncompletaError)
            else "EVENTO_INVALIDO_O_VERSION_NO_SOPORTADA"
        )
        clave = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        async with session_factory() as db, db.begin():
            await db.execute(
                insert(IncidenciaEvento)
                .values(
                    clave=clave,
                    motivo=motivo,
                    creado_en=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
            )
        return None
