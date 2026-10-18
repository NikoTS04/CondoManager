"""Router FastAPI para el Dominio de Cuotas (Anderson - PROC-01)."""

from fastapi import APIRouter, HTTPException, status

from src.core.errors import APIError
from src.modules.condominios.estructura.router import Actor, Servicio
from src.modules.cuotas.distribucion.exceptions import DistribucionError
from src.modules.cuotas.distribucion.repository import DepartamentoDistribucion
from src.modules.cuotas.distribucion.schemas import MetodoDistribucion
from src.modules.cuotas.distribucion.service import validar_departamentos
from src.modules.cuotas.schemas import (
    EmitirLoteCuotasRequest,
    EmitirLoteCuotasResponse,
)
from src.modules.cuotas.service import CuotasService, LoteYaEmitidoException

router = APIRouter(prefix="/cuotas", tags=["Cuotas de Mantenimiento"])

# Cache en memoria para simulación rápida / desarrollo local
LOTES_EMITIDOS = set()


@router.post(
    "/emitir-lote",
    response_model=EmitirLoteCuotasResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emisión masiva mensual de cuotas ordinarias",
)
async def emitir_lote_cuotas(request: EmitirLoteCuotasRequest, actor: Actor, servicio: Servicio):
    """Calcula y emite las cuotas de mantenimiento para las unidades activas del condominio."""
    await servicio.autorizar(request.condominio_id, actor, True)
    clave = (request.condominio_id, request.periodo)
    if clave in LOTES_EMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "LOTE_YA_EMITIDO",
                "mensaje": f"El lote para el periodo '{request.periodo}' ya fue emitido previamente.",
            },
        )

    unidades = await servicio.repo.departamentos(request.condominio_id, activo=True)
    if not unidades:
        raise APIError(
            422, "SIN_DEPARTAMENTOS_ACTIVOS", "Registre al menos un departamento activo."
        )
    try:
        validar_departamentos(
            [DepartamentoDistribucion(d.id, d.coeficiente_participacion) for d in unidades],
            MetodoDistribucion.POR_ALICUOTA,
        )
    except DistribucionError as exc:
        raise APIError(422, exc.error_code, exc.mensaje, exc.detalles) from exc
    departamentos = [
        {
            "id": d.id,
            "numero": d.numero,
            "coeficiente": d.coeficiente_participacion,
            "saldo_a_favor": d.saldo_a_favor,
        }
        for d in unidades
    ]

    try:
        response = CuotasService.emitir_lote_en_memoria(
            request=request,
            departamentos=departamentos,
            lotes_existentes=[
                periodo for cid, periodo in LOTES_EMITIDOS if cid == request.condominio_id
            ],
        )
        LOTES_EMITIDOS.add(clave)
        return response
    except LoteYaEmitidoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "LOTE_YA_EMITIDO", "mensaje": str(exc)},
        )
