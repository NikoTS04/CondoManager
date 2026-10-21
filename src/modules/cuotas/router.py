"""Emisión manual persistente de CON-11, con identidad y contexto obligatorios."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import contexto_consulta
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.presupuestos.router import require_presupuesto_user
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteCuotasResponse, EmitirLoteRequest
from src.modules.usuarios.departamentos import get_departamentos_portal_repository
from src.modules.usuarios.schemas import DepartamentoPortalDTO

router = APIRouter(prefix="/cuotas", tags=["Cuotas de Mantenimiento"])


@router.get("/departamentos", response_model=list[DepartamentoPortalDTO])
async def departamentos_del_portal(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    condominio_id: UUID | None = None,
    repository=Depends(get_departamentos_portal_repository),
):
    cid = contexto_consulta(user, condominio_id)
    return await repository.listar(cid, user)


@router.post("/emitir-lote", response_model=EmitirLoteCuotasResponse, status_code=201)
async def emitir_lote_cuotas(
    request: EmitirLoteRequest,
    user: Annotated[dict[str, Any], Depends(require_presupuesto_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    if not user.get("sub") or not user.get("rol"):
        raise APIError(401, "TOKEN_INVALIDO", "Faltan identidad o rol en el token.")
    if user["rol"] not in {"SUPERADMIN", "ADMIN_JUNTA"}:
        raise APIError(403, "EMISION_ACCESO_DENEGADO", "El rol no puede emitir cuotas.")
    try:
        cid = (
            request.condominio_id
            if user["rol"] == "SUPERADMIN"
            else UUID(str(user.get("condominio_id")))
        )
    except ValueError as exc:
        raise APIError(403, "EMISION_ACCESO_DENEGADO", "Contexto de condominio inválido.") from exc
    return await EmisionCuotasService(session).emitir(
        request, ActorSaldoFavor(str(user["sub"]), user["rol"], cid)
    )
