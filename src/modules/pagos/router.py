"""API compatible de pagos con PostgreSQL y evidencia local privada."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Response
from fastapi.responses import FileResponse

from src.core.authorization import autorizar_condominio
from src.core.errors import ErrorResponse
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
    ReportarPagoFormulario,
    SolvenciaResponse,
    SubsanarVoucherRequest,
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


@router.get("/pagos/solvencia/{departamento_id}", response_model=SolvenciaResponse)
async def consultar_solvencia(
    departamento_id: UUID,
    user: dict = Depends(get_current_user),
    service=Depends(get_solvencia_service),
):
    return await service.consultar(departamento_id, user)


@router.post(
    "/pagos/reportar",
    response_model=ComprobanteRecibidoResponse,
    status_code=202,
    responses={200: {"model": ComprobanteRecibidoResponse}, 503: {"model": ErrorResponse}},
)
async def reportar_pago(
    request: Annotated[ReportarPagoFormulario, Form(media_type="multipart/form-data")],
    response: Response,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    try:
        resultado, creado = await service.reportar(request, request.archivo_voucher, user)
        response.status_code = 202 if creado else 200
        return resultado
    finally:
        await request.archivo_voucher.close()


@router.put(
    "/pagos/{comprobante_id}/voucher",
    response_model=ComprobanteRecibidoResponse,
    status_code=202,
    responses={503: {"model": ErrorResponse}},
)
async def subsanar_voucher(
    comprobante_id: UUID,
    request: Annotated[SubsanarVoucherRequest, Form(media_type="multipart/form-data")],
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    try:
        return await service.subsanar(comprobante_id, request.archivo_voucher, user)
    finally:
        await request.archivo_voucher.close()


@router.get(
    "/pagos/{comprobante_id}/voucher",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Evidencia privada de la unidad autorizada",
            "headers": {"Cache-Control": {"schema": {"type": "string", "const": "no-store"}}},
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/png", "image/jpeg", "application/pdf")
            },
        },
    },
)
async def descargar_voucher(
    comprobante_id: UUID,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
):
    ruta, nombre = await service.voucher(comprobante_id, user)
    return FileResponse(
        ruta,
        filename=nombre,
        media_type={".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf"}[
            ruta.suffix
        ],
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
