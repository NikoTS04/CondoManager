"""Catálogo SQL común al portal y a la validación de unidades de negocio (CON-05)."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.pagos.contabilidad import CERO, saldo_en_mora
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.models import UsuarioDepartamento
from src.modules.usuarios.schemas import DepartamentoPortalDTO
from src.shared.fechas import fecha_lima


class DepartamentosPortalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _consulta(self):
        return (
            select(Departamento, Edificio, Condominio)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .join(Condominio, Edificio.condominio_id == Condominio.id)
            .where(Condominio.activo.is_(True))
        )

    async def _representar(self, departamento, edificio, condominio):
        cuotas = await SQLAlchemyPagosRepository(self.session).cuotas(departamento.id)
        deuda = saldo_en_mora(cuotas, condominio.dias_gracia, fecha_lima())
        return DepartamentoPortalDTO(
            id=departamento.id,
            condominio_id=edificio.condominio_id,
            edificio_id=edificio.id,
            edificio_nombre=edificio.nombre_bloque,
            numero=departamento.numero,
            piso=departamento.piso,
            coeficiente=departamento.coeficiente_participacion,
            saldo_a_favor=departamento.saldo_a_favor,
            estado_financiero="EN_MORA" if deuda > CERO else "AL_DIA",
            activo=departamento.activo,
            deuda_vencida=deuda,
        ).model_dump()

    async def listar(self, cid: UUID, actor: dict):
        query = self._consulta().where(Edificio.condominio_id == cid, Departamento.activo.is_(True))
        if actor["rol"] == "RESIDENTE":
            ids = select(UsuarioDepartamento.departamento_id).where(
                UsuarioDepartamento.usuario_id == UUID(actor["sub"]),
                UsuarioDepartamento.es_activo.is_(True),
            )
            query = query.where(Departamento.id.in_(ids))
        rows = await self.session.execute(
            query.order_by(Edificio.nombre_bloque, Departamento.numero, Departamento.id)
        )
        return [await self._representar(*row) for row in rows]

    async def obtener(self, did: UUID):
        row = (
            await self.session.execute(self._consulta().where(Departamento.id == did))
        ).one_or_none()
        return await self._representar(*row) if row is not None else None


def get_departamentos_portal_repository(session: AsyncSession = Depends(get_db_session)):
    return DepartamentosPortalRepository(session)
