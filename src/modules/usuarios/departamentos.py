"""Catálogo SQL común al portal y a la validación de unidades de negocio (CON-05)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.usuarios.models import UsuarioDepartamento
from src.modules.usuarios.schemas import DepartamentoPortalDTO


class DepartamentosPortalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _consulta(self):
        deuda = (
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            CuotaMantenimiento.monto_total_exigible
                            - CuotaMantenimiento.monto_pagado,
                            Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                )
            )
            .where(
                CuotaMantenimiento.departamento_id == Departamento.id,
                CuotaMantenimiento.fecha_vencimiento < datetime.now(UTC).date(),
            )
            .correlate(Departamento)
            .scalar_subquery()
        )
        return (
            select(Departamento, Edificio, deuda)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .join(Condominio, Edificio.condominio_id == Condominio.id)
            .where(Condominio.activo.is_(True))
        )

    @staticmethod
    def _representar(departamento, edificio, deuda):
        return DepartamentoPortalDTO(
            id=departamento.id,
            condominio_id=edificio.condominio_id,
            edificio_id=edificio.id,
            edificio_nombre=edificio.nombre_bloque,
            numero=departamento.numero,
            piso=departamento.piso,
            coeficiente=departamento.coeficiente_participacion,
            saldo_a_favor=departamento.saldo_a_favor,
            estado_financiero=departamento.estado_financiero,
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
        return [self._representar(*row) for row in rows]

    async def obtener(self, did: UUID):
        row = (
            await self.session.execute(self._consulta().where(Departamento.id == did))
        ).one_or_none()
        return self._representar(*row) if row is not None else None


def get_departamentos_portal_repository(session: AsyncSession = Depends(get_db_session)):
    return DepartamentosPortalRepository(session)
