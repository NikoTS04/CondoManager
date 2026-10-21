"""Persistencia contextual del catálogo y su cadena de auditoría."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.security import validar_sesion
from src.modules.condominios.models import Departamento, Edificio
from src.modules.reservas.areas.models import AreaComun
from src.modules.reservas.areas.schemas import AreaComunDTO
from src.modules.reservas.disponibilidad import DisponibilidadRepository
from src.modules.usuarios.models import UsuarioDepartamento
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository


class AreasRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.identidad = SQLAlchemyUsuariosRepository(session)

    async def contexto(self, cid, bloquear=False):
        return await self.identidad.contexto(cid, bloquear=bloquear)

    async def validar_actor(self, actor):
        return await validar_sesion(actor, self.identidad)

    async def area(self, cid, aid, bloquear=False):
        query = (
            select(AreaComun)
            .where(AreaComun.condominio_id == cid, AreaComun.id == aid)
            .execution_options(populate_existing=True)
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def area_global(self, aid):
        return await self.session.get(AreaComun, aid)

    async def ocupaciones(self, aid, cid, fecha):
        # Se usa bajo el mismo lock/transacción del área al crear una reserva.
        return await DisponibilidadRepository(self.session).reservas_confirmadas(aid, cid, fecha)

    async def edificio(self, cid, eid):
        return await self.session.scalar(
            select(Edificio).where(Edificio.condominio_id == cid, Edificio.id == eid)
        )

    def _edificios_usuario(self, cid, uid):
        return (
            select(Departamento.edificio_id)
            .join(UsuarioDepartamento, UsuarioDepartamento.departamento_id == Departamento.id)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .where(
                UsuarioDepartamento.usuario_id == UUID(uid),
                UsuarioDepartamento.es_activo.is_(True),
                Departamento.activo.is_(True),
                Edificio.condominio_id == cid,
            )
        )

    async def edificios_usuario(self, cid, uid):
        return set(await self.session.scalars(self._edificios_usuario(cid, uid)))

    @staticmethod
    def representar(area, moneda, edificio_nombre=None):
        return AreaComunDTO(
            id=area.id,
            condominio_id=area.condominio_id,
            edificio_id=area.edificio_id,
            edificio_nombre=edificio_nombre,
            nombre=area.nombre,
            descripcion=area.descripcion,
            aforo_maximo=area.aforo_maximo,
            costo_reserva=area.costo_reserva,
            tiempo_maximo_horas=area.tiempo_maximo_horas,
            esta_activa=area.esta_activa,
            hora_apertura=area.hora_apertura.strftime("%H:%M"),
            hora_cierre=area.hora_cierre.strftime("%H:%M"),
            moneda=moneda,
        )

    async def presentar(self, area, moneda):
        edificio = (
            await self.edificio(area.condominio_id, area.edificio_id) if area.edificio_id else None
        )
        return self.representar(area, moneda, edificio.nombre_bloque if edificio else None)

    async def listar(self, cid, moneda, *, activa=None, limit=None, offset=0, residente=None):
        query = (
            select(AreaComun, Edificio.nombre_bloque)
            .outerjoin(
                Edificio, and_(Edificio.id == AreaComun.edificio_id, Edificio.condominio_id == cid)
            )
            .where(AreaComun.condominio_id == cid)
            .order_by(AreaComun.nombre, AreaComun.id)
        )
        if activa is not None:
            query = query.where(AreaComun.esta_activa.is_(activa))
        if residente:
            query = query.where(
                or_(
                    AreaComun.edificio_id.is_(None),
                    AreaComun.edificio_id.in_(self._edificios_usuario(cid, residente)),
                )
            )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        return [
            self.representar(area, moneda, nombre)
            for area, nombre in await self.session.execute(query)
        ]

    async def ultimo_hash(self, cid):
        return await self.identidad.ultimo_hash(cid)

    async def guardar(self, area, auditoria):
        await self.identidad.agregar(area, auditoria)
        await self.identidad.confirmar()


def get_areas_repository(session: AsyncSession = Depends(get_db_session)):
    return AreasRepository(session)
