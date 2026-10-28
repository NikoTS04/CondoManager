"""Guard de CON-42: integrable en la misma transacción de CON-41/73."""

from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.modules.pagos.contabilidad import CERO, saldo_en_mora
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.schemas import SolvenciaResponse
from src.shared.fechas import fecha_lima


class SolvenciaService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SQLAlchemyPagosRepository(session)

    async def consultar(self, did, usuario):
        async with self.session.begin():
            depto, condominio = await self.repo.departamento(did, usuario)
            if not depto.activo:
                raise APIError(403, "DEPARTAMENTO_INACTIVO", "El departamento está inactivo.")
            cuotas = await self.repo.cuotas(depto.id)
            saldo = saldo_en_mora(cuotas, condominio.dias_gracia, fecha_lima())
            return SolvenciaResponse(
                departamento_id=did,
                saldo_vencido=saldo,
                habilitado_reservas=saldo == CERO,
            )

    @asynccontextmanager
    async def para_reserva(self, solicitud, usuario):
        bloqueo = None
        async with self.session.begin():
            depto, condominio = await self.repo.departamento(
                solicitud.departamento_id,
                usuario,
                escritura=True,
                bloquear=True,
            )
            # El contexto de la solicitud también debe coincidir, incluso para SuperAdmin.
            if condominio.id != solicitud.condominio_id:
                raise HTTPException(403, detail={"error_code": "ACCESO_DENEGADO"})
            cuotas = await self.repo.cuotas(depto.id, bloquear=True)
            saldo = saldo_en_mora(cuotas, condominio.dias_gracia, fecha_lima())
            if saldo > CERO:
                bloqueo = {
                    "error_code": "DEUDA_MORA_ACTIVA",
                    "mensaje": "El departamento mantiene deuda vencida en mora. Un comprobante en revisión no cancela la deuda.",
                    "detalles": {"departamento_id": str(depto.id), "saldo_vencido": str(saldo)},
                }
                await self.repo.auditar(
                    usuario,
                    condominio.id,
                    depto.id,
                    "SOLICITUD_RESERVA_RECHAZADA_MORA",
                    "DEUDA_MORA_ACTIVA",
                    {"saldo_vencido": str(saldo)},
                    {"reserva_creada": False, "saldo_vencido": str(saldo)},
                    exito=False,
                )
            else:
                # CON-41 puede persistir con self.session antes de abandonar este contexto.
                yield SolvenciaResponse(
                    departamento_id=depto.id, saldo_vencido=saldo, habilitado_reservas=True
                )
        if bloqueo:
            # Auditoría FALLIDO ya confirmada; no se publica confirmación de reserva.
            raise HTTPException(403, detail=bloqueo)


def get_solvencia_service(session: AsyncSession = Depends(get_db_session, use_cache=False)):
    return SolvenciaService(session)
