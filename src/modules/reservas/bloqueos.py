"""Bloqueos preventivos con los mismos locks de las reservas."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select

from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.reservas.areas.repository import get_areas_repository
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.models import BloqueoArea, Reserva

router = APIRouter(prefix="/condominios/{cid}/areas/{aid}/bloqueos", tags=["Bloqueos"])


class CrearBloqueo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    inicio: AwareDatetime
    fin: AwareDatetime
    motivo: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def intervalo(self):
        if self.fin <= self.inicio or self.inicio <= datetime.now(UTC):
            raise ValueError("Seleccione un intervalo futuro con fin posterior al inicio.")
        return self


class BloqueoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    area_id: UUID
    inicio: datetime
    fin: datetime
    activo: bool


async def contexto(repo, cid, aid, actor, escritura=False):
    areas = AreasService(repo)
    await areas._contexto(cid, actor, escritura)
    await areas._area(cid, aid, escritura)


async def auditar(repo, cid, actor, accion, motivo, anterior, bloqueo):
    await SQLAlchemyPagosRepository(repo.session).auditar(
        actor, cid, None, accion, motivo, anterior,
        BloqueoDTO.model_validate(bloqueo).model_dump(mode="json"),
    )


@router.get("", response_model=list[BloqueoDTO])
async def listar(cid: UUID, aid: UUID, actor=Depends(get_current_user), repo=Depends(get_areas_repository)):
    await contexto(repo, cid, aid, actor)
    return list(await repo.session.scalars(
        select(BloqueoArea).where(BloqueoArea.area_id == aid)
        .order_by(BloqueoArea.inicio.desc(), BloqueoArea.id).limit(100)
    ))


@router.post("", response_model=BloqueoDTO, status_code=201)
async def crear(cid: UUID, aid: UUID, request: CrearBloqueo, actor=Depends(get_current_user), repo=Depends(get_areas_repository)):
    await contexto(repo, cid, aid, actor, True)
    inicio = func.timezone(Reserva.zona_horaria, Reserva.fecha_reserva + Reserva.hora_inicio)
    fin = func.timezone(Reserva.zona_horaria, Reserva.fecha_reserva + Reserva.hora_fin)
    if await repo.session.scalar(select(Reserva.id).where(
        Reserva.area_id == aid, Reserva.estado == "CONFIRMADA",
        inicio < request.fin, fin > request.inicio,
    ).limit(1)):
        raise APIError(409, "BLOQUEO_AFECTA_RESERVAS", "Reprograme o cancele las reservas antes de bloquear.")
    bloqueo = BloqueoArea(
        id=uuid4(), area_id=aid, inicio=request.inicio.astimezone(UTC),
        fin=request.fin.astimezone(UTC), activo=True,
    )
    repo.session.add(bloqueo)
    await repo.session.flush()
    await auditar(repo, cid, actor, "AREA_BLOQUEADA", request.motivo, {}, bloqueo)
    return bloqueo


@router.delete("/{bid}", response_model=BloqueoDTO)
async def liberar(cid: UUID, aid: UUID, bid: UUID, actor=Depends(get_current_user), repo=Depends(get_areas_repository)):
    await contexto(repo, cid, aid, actor, True)
    bloqueo = await repo.session.scalar(select(BloqueoArea).where(
        BloqueoArea.id == bid, BloqueoArea.area_id == aid,
    ).with_for_update())
    if bloqueo is None:
        raise APIError(404, "BLOQUEO_NO_ENCONTRADO", "No existe ese bloqueo en el área.")
    if bloqueo.activo:
        anterior = BloqueoDTO.model_validate(bloqueo).model_dump(mode="json")
        bloqueo.activo = False
        await auditar(repo, cid, actor, "BLOQUEO_LEVANTADO", "LIBERACION_ADMINISTRATIVA", anterior, bloqueo)
    return bloqueo
