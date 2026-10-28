"""Tesorería contextual: caja conciliada y coberturas versionadas del borrador."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.condominios.models import Condominio, Edificio
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.presupuestos.repository import SQLAlchemyPresupuestoRepository
from src.modules.cuotas.presupuestos.schemas import PERIODO_PATTERN
from src.modules.cuotas.prorrateo_api import acceso_administrativo
from src.modules.cuotas.prorrateo_schemas import Dinero, texto_admitido
from src.modules.pagos.fondos import FondosMorasService, datos_aplicacion
from src.shared.fechas import fecha_lima

router = APIRouter(tags=["Fondos de moras"])


class ReservaMorasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_esperada: int = Field(ge=1, strict=True)
    item_id: UUID
    edificio_id: UUID
    monto: Dinero = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=1000)

    @field_validator("motivo")
    @classmethod
    def motivo_real(cls, value):
        value = texto_admitido(value).strip()
        if not value:
            raise ValueError("Indique el motivo de la cobertura.")
        return value


async def presupuesto_autorizado(session, id, actor, escritura=False):
    p = await session.get(PresupuestoMensual, id)
    if p is None:
        raise APIError(404, "PRESUPUESTO_NO_ENCONTRADO", "No existe el presupuesto.")
    acceso_administrativo(actor, p.condominio_id, escritura)
    if escritura:
        p = await SQLAlchemyPresupuestoRepository(session).obtener_por_id(id, p.condominio_id, bloquear=True)
        if not (await session.get(Condominio, p.condominio_id)).activo:
            raise APIError(409, "CONDOMINIO_INACTIVO", "No se modifica caja de un condominio inactivo.")
    return p


@router.get("/edificios/{edificio_id}/fondos-moras")
async def consultar_fondo(edificio_id: UUID, periodo: str | None = Query(default=None, pattern=PERIODO_PATTERN),
                         actor=Depends(get_current_user),
                         session: AsyncSession = Depends(get_db_session, use_cache=False)):
    async with session.begin():
        if periodo and periodo.startswith("0000-"):
            raise APIError(422, "PERIODO_INVALIDO", "El año debe ser mayor que cero.")
        e = await session.get(Edificio, edificio_id)
        if e is None:
            raise APIError(404, "EDIFICIO_NO_ENCONTRADO", "No existe el edificio.")
        acceso_administrativo(actor, e.condominio_id)
        c = await session.scalar(select(Condominio).where(Condominio.id == e.condominio_id).with_for_update())
        return await FondosMorasService(session).resumen(c.id, e.id, c.moneda, periodo or fecha_lima().strftime("%Y-%m"))


@router.get("/presupuestos/{presupuesto_id}/aplicaciones-moras")
async def listar_aplicaciones(presupuesto_id: UUID, actor=Depends(get_current_user),
                              session: AsyncSession = Depends(get_db_session, use_cache=False)):
    async with session.begin():
        p = await presupuesto_autorizado(session, presupuesto_id, actor)
        return [datos_aplicacion(a) for a in await FondosMorasService(session).aplicaciones(p.id)]


@router.post("/presupuestos/{presupuesto_id}/aplicaciones-moras", status_code=201)
async def reservar_moras(presupuesto_id: UUID, request: ReservaMorasRequest,
                        clave: Annotated[str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9_-]{1,100}$")],
                        actor=Depends(get_current_user),
                        session: AsyncSession = Depends(get_db_session, use_cache=False)):
    async with session.begin():
        p = await presupuesto_autorizado(session, presupuesto_id, actor, True)
        return datos_aplicacion(await FondosMorasService(session).reservar(p, request, clave, actor))


@router.delete("/presupuestos/{presupuesto_id}/aplicaciones-moras/{aplicacion_id}", status_code=204)
async def liberar_moras(presupuesto_id: UUID, aplicacion_id: UUID, version_esperada: int = Query(ge=1),
                       actor=Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session, use_cache=False)):
    async with session.begin():
        p = await presupuesto_autorizado(session, presupuesto_id, actor, True)
        servicio = FondosMorasService(session)
        a = next((a for a in await servicio.aplicaciones(p.id) if a.id == aplicacion_id), None)
        if a is None:
            raise APIError(404, "APLICACION_NO_ENCONTRADA", "No existe la cobertura en este presupuesto.")
        await servicio.liberar(p, a, version_esperada, actor)
    return Response(status_code=204)
