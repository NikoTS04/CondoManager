"""API compatible de pagos con PostgreSQL y evidencia local privada."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse

from src.core.authorization import autorizar_condominio
from src.core.security import get_current_user, require_role
from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.persistencia import get_pagos_service
from src.modules.pagos.schemas import (
    ComprobantePagoDTO,
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ConciliarPagoRequest,
    EvaluarMorasRequest,
    EvaluarMorasResponse,
    ReportarPagoRequest,
    SolvenciaResponse,
    VoucherSubidoResponse,
)
from src.modules.pagos.solvencia import get_solvencia_service

router = APIRouter(tags=["Pagos y Conciliación"])


@router.get("/pagos/comprobantes", response_model=list[ComprobantePagoDTO])
async def listar_comprobantes(
    user: dict = Depends(get_current_user),
    condominio_id: UUID | None = None,
    service=Depends(get_pagos_service),
):
    return await service.listar(user, condominio_id)


@router.post("/pagos/vouchers", response_model=VoucherSubidoResponse, status_code=201)
async def subir_voucher(
    departamento_id: UUID = Form(...),
    voucher_file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    try:
        return await service.subir(departamento_id, voucher_file, user)
    finally:
        await voucher_file.close()


@router.get("/pagos/solvencia/{departamento_id}", response_model=SolvenciaResponse)
async def consultar_solvencia(
    departamento_id: UUID,
    user: dict = Depends(get_current_user),
    service=Depends(get_solvencia_service),
):
    return await service.consultar(departamento_id, user)


@router.post("/pagos/reportar", response_model=ComprobanteRecibidoResponse, status_code=202)
async def reportar_pago(
    request: ReportarPagoRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    resultado, creado = await service.reportar(request, user)
    response.status_code = 202 if creado else 200
    return resultado


@router.get("/pagos/{comprobante_id}/voucher")
async def descargar_voucher(
    comprobante_id: UUID,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    ruta, nombre = await service.voucher(comprobante_id, user)
    return FileResponse(
        ruta,
        filename=nombre,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/pagos/{comprobante_id}/resultado", response_model=ConciliacionResultResponse)
async def consultar_resultado(
    comprobante_id: UUID,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    return await service.resultado(comprobante_id, user)


@router.post("/pagos/{comprobante_id}/conciliar", response_model=ConciliacionResultResponse)
async def conciliar_pago(
    comprobante_id: UUID,
    request: ConciliarPagoRequest,
    user: dict = Depends(require_role(["ADMIN_JUNTA", "SUPERADMIN"])),
    service=Depends(get_pagos_service),
):
    return await service.revisar(comprobante_id, request, user)


@router.post("/moras/evaluar", response_model=EvaluarMorasResponse)
async def evaluar_moras(
    request: EvaluarMorasRequest,
    user: dict = Depends(require_role(["ADMIN_JUNTA", "SUPERADMIN"])),
):
    autorizar_condominio(user, request.condominio_id, escritura=True)
    return MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=[],
        departamentos={},
        comprobantes_en_revision_por_depto={},
        fecha_evaluacion=request.fecha_corte,
    )
