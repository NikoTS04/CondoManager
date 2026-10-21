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
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.models_persistencia import EventoPagoOutbox
from src.modules.reservas.models import EventoReservaOutbox, Reserva

TIPOS = {
    "CuotasEmitidasEvent": (EventoLoteOutbox, "NOTIF_EMISION_CUOTA"),
    "PagoReportadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_RECIBIDO"),
    "PagoConciliadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_CONCILIADO"),
    "PagoObservadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_OBSERVADO"),
    "PagoRechazadoEvent": (EventoPagoOutbox, "NOTIF_PAGO_RECHAZADO"),
    "ReservaConfirmadaEvent": (EventoReservaOutbox, "NOTIF_RESERVA_CONFIRMADA"),
    "ReservaCanceladaEvent": (EventoReservaOutbox, "NOTIF_RESERVA_CANCELADA"),
}


async def consumir(session_factory, payload):
    """Solo confirma consumo después de persistir avisos o una incidencia recuperable."""
    try:
        if not isinstance(payload, dict) or payload.get("event_type") not in TIPOS:
            raise ValueError("TIPO_EVENTO_NO_SOPORTADO")
        tipo = payload["event_type"]
        modelo, plantilla = TIPOS[tipo]
        eid = UUID(payload["event_id"])
        if modelo is EventoPagoOutbox and payload.get("version") != 1:
            raise ValueError("VERSION_PAGO_NO_SOPORTADA")
        if modelo is EventoReservaOutbox and payload.get("schema_version") != 1:
            raise ValueError("VERSION_RESERVA_NO_SOPORTADA")
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
                            "cci_banco": "Consulta los medios de pago con la administración.",
                        },
                    )
                    for c in cuotas
                ]
            else:
                did = UUID(data["departamento_id"])
                operacion = UUID(data.get("reserva_id") or data["comprobante_id"])
                contexto = dict(data)
                if tipo.startswith("Pago"):
                    comprobante = await db.get(ComprobantePago, operacion)
                    # El mensaje usa la instantánea de la revisión, no el saldo actual.
                    resultado = data.get("resultado", {})
                    contexto.update(
                        monto_abonado=resultado.get("monto_imputado", data["monto"]),
                        saldo_restante=resultado.get("nuevo_saldo_departamento", "No disponible"),
                        motivo_rechazo=data.get("motivo"),
                        banco=comprobante.banco_origen,
                        numero_operacion=comprobante.numero_operacion,
                        recibo_url=f"/residente?dpto={did}",
                        enlace_subir_nuevo=f"/residente?dpto={did}",
                    )
                else:
                    reserva = await db.get(Reserva, operacion)
                    contexto.update(
                        area=data.get("area_nombre", reserva.area_nombre),
                        fecha=data["fecha_reserva"],
                        horario=f"{data['hora_inicio']}–{data['hora_fin']} ({data['zona_horaria']})",
                        normas_convivencia="Consulta las condiciones publicadas del área.",
                        costo=data.get("costo_reserva", "No aplica"),
                    )
                    if tipo == "ReservaCanceladaEvent":
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
    except (ValueError, KeyError, TypeError, AttributeError):
        # No guardar payloads: podrían contener contactos o información sensible.
        clave = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        async with session_factory() as db, db.begin():
            await db.execute(
                insert(IncidenciaEvento)
                .values(
                    clave=clave,
                    motivo="EVENTO_INVALIDO_O_VERSION_NO_SOPORTADA",
                    creado_en=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
            )
        return None
