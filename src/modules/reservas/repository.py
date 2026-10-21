"""Lecturas SQL del calendario; el llamador conserva el lock del área al escribir."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.modules.reservas.models import BloqueoArea, Reserva


def instantes(reserva):
    zona = ZoneInfo(reserva.zona_horaria)
    return (
        datetime.combine(reserva.fecha_reserva, reserva.hora_inicio, zona).astimezone(UTC),
        datetime.combine(reserva.fecha_reserva, reserva.hora_fin, zona).astimezone(UTC),
    )


class ReservasRepository:
    def __init__(self, session):
        self.session = session

    async def ocupaciones(self, area_id, fecha):
        inicio = datetime.combine(fecha, time(), ZoneInfo("America/Lima")).astimezone(UTC)
        fin = inicio + timedelta(days=1)
        reservas = await self.session.scalars(
            select(Reserva).where(
                Reserva.area_id == area_id,
                Reserva.estado == "CONFIRMADA",
                Reserva.fecha_reserva.between(fecha - timedelta(days=1), fecha + timedelta(days=1)),
            )
        )
        intervalos = [instantes(r) for r in reservas]
        bloqueos = await self.session.scalars(
            select(BloqueoArea).where(
                BloqueoArea.area_id == area_id,
                BloqueoArea.activo.is_(True),
                BloqueoArea.inicio < fin,
                BloqueoArea.fin > inicio,
            )
        )
        intervalos.extend((b.inicio, b.fin) for b in bloqueos)
        return [(max(a, inicio), min(b, fin)) for a, b in intervalos if a < fin and b > inicio]

    async def listar(self, cid, usuario, area_id=None, fecha=None):
        query = select(Reserva).where(Reserva.condominio_id == cid)
        if usuario["rol"] == "RESIDENTE":
            ids = [v["departamento_id"] for v in usuario["departamentos"] if v["es_activo"]]
            query = query.where(Reserva.departamento_id.in_(ids))
        if area_id:
            query = query.where(Reserva.area_id == area_id)
        if fecha:
            query = query.where(Reserva.fecha_reserva == fecha)
        return list(
            await self.session.scalars(query.order_by(Reserva.creado_en.desc(), Reserva.id))
        )
