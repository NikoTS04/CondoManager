"""Emisión manual persistente de CON-11, con identidad y contexto obligatorios."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.presupuestos.router import require_presupuesto_user
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteCuotasResponse, EmitirLoteRequest

router = APIRouter(prefix="/cuotas", tags=["Cuotas de Mantenimiento"])


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
