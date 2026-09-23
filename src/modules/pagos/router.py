"""Router FastAPI para Pagos, Conciliación y Moras (Tarqui - PROC-02)."""

from datetime import date
from typing import Dict
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.security import require_role
from src.modules.pagos.schemas import (
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ConciliarPagoRequest,
    EvaluarMorasRequest,
    EvaluarMorasResponse,
    ReportarPagoRequest,
)
from src.modules.pagos.service import PagosService, VoucherDuplicadoException
from src.modules.pagos.moras_service import MotorMorasService

router = APIRouter(tags=["Pagos y Conciliación"])

# Almacén en memoria para simulación y desarrollo local
COMPROBANTES_REGISTRADOS: Dict[str, Dict] = {}


@router.post(
    "/pagos/reportar",
    response_model=ComprobanteRecibidoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reporte de comprobante de pago bancario por residente",
)
async def reportar_pago(request: ReportarPagoRequest):
    """Registra un comprobante con validación de clave de idempotencia SHA-256."""
    condominio_id = "vb3-condo"
    try:
        response = PagosService.procesar_reporte_pago(
            request=request,
            condominio_id=condominio_id,
            comprobantes_existentes=COMPROBANTES_REGISTRADOS,
        )
        return response
    except VoucherDuplicadoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )


@router.post(
    "/pagos/{comprobante_id}/conciliar",
    response_model=ConciliacionResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobación o rechazo de comprobante por la Junta Directiva",
    dependencies=[Depends(require_role(["ADMIN_JUNTA", "SUPERADMIN"]))],
)
async def conciliar_pago(comprobante_id: uuid.UUID, request: ConciliarPagoRequest):
    """Ejecuta la conciliación bancaria y la imputación contable en orden de prelación."""
    # Buscar comprobante en la memoria
    comprobante = None
    for c in COMPROBANTES_REGISTRADOS.values():
        if c["id"] == comprobante_id:
            comprobante = c
            break

    if not comprobante:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "COMPROBANTE_NO_ENCONTRADO", "mensaje": "Comprobante no hallado."},
        )

    # Simulación de cuotas pendientes del departamento
    cuotas_mock = [
        {
            "id": uuid.uuid4(),
            "fecha_vencimiento": date(2026, 9, 20),
            "monto_total_exigible": comprobante["monto"],
            "monto_pagado": 0.0,
            "estado": "PENDIENTE",
        }
    ]
    depto_mock = {"id": comprobante["departamento_id"], "saldo_a_favor": 0.0, "estado_financiero": "PENDIENTE"}

    try:
        result = PagosService.conciliar_comprobante(
            comprobante=comprobante,
            decision=request.decision,
            cuotas_pendientes=cuotas_mock,
            departamento=depto_mock,
            motivo_rechazo=request.motivo_rechazo,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post(
    "/moras/evaluar",
    response_model=EvaluarMorasResponse,
    status_code=status.HTTP_200_OK,
    summary="Disparo del motor nocturno de evaluación de moras tras la gracia",
)
async def evaluar_moras(request: EvaluarMorasRequest):
    """Ejecuta la evaluación de cuotas vencidas y aplica recargos respetando la gracia."""
    # Simulación de cuotas de prueba
    response = MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=[],
        departamentos={},
        comprobantes_en_revision_por_depto={},
        fecha_evaluacion=request.fecha_corte,
    )
    return response
