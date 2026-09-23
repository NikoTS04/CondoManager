"""Router FastAPI para el Dominio de Cuotas (Anderson - PROC-01)."""

from fastapi import APIRouter, HTTPException, status
from src.modules.cuotas.schemas import (
    EmitirLoteCuotasRequest,
    EmitirLoteCuotasResponse,
)
from src.modules.cuotas.service import CuotasService, LoteYaEmitidoException
from scripts.seed_condominio_piloto import generar_datos_departamentos

router = APIRouter(prefix="/cuotas", tags=["Cuotas de Mantenimiento"])

# Cache en memoria para simulación rápida / desarrollo local
LOTES_EMITIDOS = set()


@router.post(
    "/emitir-lote",
    response_model=EmitirLoteCuotasResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emisión masiva mensual de cuotas ordinarias",
)
async def emitir_lote_cuotas(request: EmitirLoteCuotasRequest):
    """Calcula y emite las cuotas de mantenimiento para las unidades activas del condominio."""
    if request.periodo in LOTES_EMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "LOTE_YA_EMITIDO",
                "mensaje": f"El lote para el periodo '{request.periodo}' ya fue emitido previamente.",
            },
        )

    # Obtenemos los departamentos del condominio piloto
    departamentos = generar_datos_departamentos()

    try:
        response = CuotasService.emitir_lote_en_memoria(
            request=request,
            departamentos=departamentos,
            lotes_existentes=list(LOTES_EMITIDOS),
        )
        LOTES_EMITIDOS.add(request.periodo)
        return response
    except LoteYaEmitidoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "LOTE_YA_EMITIDO", "mensaje": str(exc)},
        )
