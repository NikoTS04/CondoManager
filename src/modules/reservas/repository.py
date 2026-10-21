"""Repositorio de persistencia SQL para Reservas de Áreas Comunes (Brandon - CON-41 / CON-43 / CON-73)."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.reservas.areas.models import AreaComun
from src.modules.reservas.disponibilidad import ZONA_LIMA
from src.modules.reservas.models import Reserva


class ReservasRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def obtener_por_id(self, reserva_id: UUID, bloquear: bool = False) -> Optional[Reserva]:
        query = select(Reserva).where(Reserva.id == reserva_id)
        if bloquear:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def buscar_solapamientos(
        self,
        area_id: UUID,
        fecha: date,
        hora_inicio: time,
        hora_fin: time,
        excluir_reserva_id: Optional[UUID] = None,
        bloquear: bool = False,
    ) -> List[Reserva]:
        """Consulta intervalos solapados para el área y fecha indicadas [hora_inicio, hora_fin)."""
        # Compara instantes para conservar los históricos UTC y las nuevas
        # reservas locales; pueden pertenecer a días calendario distintos.
        inicio = func.timezone(Reserva.zona_horaria, Reserva.fecha_reserva + Reserva.hora_inicio)
        fin = func.timezone(Reserva.zona_horaria, Reserva.fecha_reserva + Reserva.hora_fin)
        condiciones = [
            Reserva.area_id == area_id,
            Reserva.estado == "CONFIRMADA",
            inicio < datetime.combine(fecha, hora_fin, ZONA_LIMA),
            fin > datetime.combine(fecha, hora_inicio, ZONA_LIMA),
        ]
        if excluir_reserva_id is not None:
            condiciones.append(Reserva.id != excluir_reserva_id)

        query = select(Reserva).where(and_(*condiciones))
        if bloquear:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def listar_disponibilidad(self, area_id: UUID, fecha: date) -> List[Reserva]:
        query = (
            select(Reserva)
            .where(
                Reserva.area_id == area_id,
                Reserva.fecha_reserva == fecha,
                Reserva.estado == "CONFIRMADA",
            )
            .order_by(Reserva.hora_inicio.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def listar_reservas(
        self,
        condominio_id: UUID,
        area_id: Optional[UUID] = None,
        fecha: Optional[date] = None,
        departamento_ids: Optional[List[UUID]] = None,
    ) -> List[tuple[Reserva, str]]:
        """Retorna reservas con el nombre del área común asociada."""
        query = (
            select(Reserva, AreaComun.nombre.label("area_nombre"))
            .join(AreaComun, Reserva.area_id == AreaComun.id)
            .where(AreaComun.condominio_id == condominio_id)
            .order_by(Reserva.fecha_reserva.desc(), Reserva.hora_inicio.desc())
        )
        if area_id is not None:
            query = query.where(Reserva.area_id == area_id)
        if fecha is not None:
            query = query.where(Reserva.fecha_reserva == fecha)
        if departamento_ids is not None:
            query = query.where(Reserva.departamento_id.in_(departamento_ids))

        result = await self.session.execute(query)
        return list(result.all())

    async def guardar(self, reserva: Reserva) -> Reserva:
        # El contexto de solvencia del router mantiene los locks de contexto y
        # área hasta confirmar juntos consulta de deuda, exclusión y creación.
        self.session.add(reserva)
        await self.session.flush()
        return reserva

    async def actualizar_estado(self, reserva: Reserva, nuevo_estado: str) -> Reserva:
        reserva.estado = nuevo_estado
        await self.session.commit()
        await self.session.refresh(reserva)
        return reserva


def get_reservas_repository(session: AsyncSession = Depends(get_db_session)) -> ReservasRepository:
    return ReservasRepository(session)
