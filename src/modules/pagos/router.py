"""API compatible de pagos con PostgreSQL, deduplicación y evidencia local privada.

Soporta CON-23 (Deduplicación - Brandon) y CON-22/70 (Persistencia, Vouchers y Auditoría - Anderson).
"""

from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from src.core.authorization import (
    autorizar_condominio,
    autorizar_departamento,
    contexto_consulta,
    puede_ver_departamento,
)
from src.core.errors import APIError
from src.core.security import get_current_user, require_role
from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.persistencia import get_pagos_service
from src.modules.pagos.repository import PagosRepository, get_pagos_repository
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
from src.modules.pagos.service import PagosService, VoucherDuplicadoException
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.usuarios.departamentos import get_departamentos_portal_repository

router = APIRouter(tags=["Pagos y Conciliación"])

COMPROBANTES_REGISTRADOS: Dict[str, dict] = {}


async def _departamento(user: dict, depto_id: UUID, repository, *, escritura=False):
    depto = await repository.obtener(depto_id)
    if not depto:
        raise HTTPException(404, detail={"error_code": "DEPARTAMENTO_NO_ENCONTRADO"})
    autorizar_departamento(user, depto_id, depto["condominio_id"], escritura=escritura)
    if not depto.get("activo", True):
        raise HTTPException(403, detail={"error_code": "ACCESO_DENEGADO"})
    return depto


@router.get("/pagos/comprobantes", response_model=list[ComprobantePagoDTO])
async def listar_comprobantes(
    user: dict = Depends(get_current_user),
    condominio_id: UUID | None = None,
    service=Depends(get_pagos_service),
    pagos_repository: Optional[PagosRepository] = Depends(get_pagos_repository),
):
    if service is not None and hasattr(service, "listar"):
        try:
            return await service.listar(user, condominio_id)
        except Exception:
            pass

    cid = contexto_consulta(user, condominio_id)
    if isinstance(pagos_repository, PagosRepository):
        try:
            comprobantes_db = await pagos_repository.listar_por_condominio(UUID(str(cid)))
            if comprobantes_db:
                return [
                    ComprobantePagoDTO(
                        id=c.id,
                        departamento_id=c.departamento_id,
                        banco=c.banco_origen,
                        numero_operacion=c.numero_operacion,
                        fecha_operacion=c.fecha_operacion,
                        monto=c.monto,
                        estado="CONCILIADO" if c.estado == "APROBADO" else c.estado,
                        idempotency_hash=c.idempotency_hash,
                        url_voucher=c.url_voucher,
                        motivo_rechazo=c.motivo_rechazo,
                    )
                    for c in comprobantes_db
                    if puede_ver_departamento(user, c.departamento_id)
                ]
        except Exception:
            pass

    return [
        {
            **c,
            "banco": c["banco_origen"],
            "estado": "CONCILIADO" if c["estado"] == "APROBADO" else c["estado"],
        }
        for c in COMPROBANTES_REGISTRADOS.values()
        if str(c["condominio_id"]) == str(cid)
        and puede_ver_departamento(user, c["departamento_id"])
    ]


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
    response: Response = None,
    user: dict = Depends(get_current_user),
    service=Depends(get_pagos_service),
    repository=Depends(get_departamentos_portal_repository),
    pagos_repository: Optional[PagosRepository] = Depends(get_pagos_repository),
):
    if service is not None and hasattr(service, "reportar"):
        try:
            resultado, creado = await service.reportar(request, user)
            if response is not None:
                response.status_code = 202 if creado else 200
            return resultado
        except (APIError, HTTPException):
            raise
        except Exception:
            pass

    depto = await _departamento(user, request.departamento_id, repository, escritura=True)
    condominio_id = str(depto["condominio_id"])

    try:
        # Intentar flujo persistente si el repositorio es una instancia válida
        if isinstance(pagos_repository, PagosRepository):
            try:
                resp = await PagosService.procesar_reporte_pago_persistente(
                    request=request,
                    condominio_id=condominio_id,
                    repository=pagos_repository,
                )
                COMPROBANTES_REGISTRADOS[resp.idempotency_hash] = {
                    "id": resp.comprobante_id,
                    "condominio_id": UUID(condominio_id),
                    "departamento_id": request.departamento_id,
                    "banco_origen": request.banco.strip().upper(),
                    "numero_operacion": request.numero_operacion.strip(),
                    "fecha_operacion": request.fecha_operacion,
                    "monto": request.monto,
                    "url_voucher": request.url_voucher,
                    "idempotency_hash": resp.idempotency_hash,
                    "estado": resp.estado,
                }
                return resp
            except (ConnectionRefusedError, OSError):
                pass

        return PagosService.procesar_reporte_pago(
            request=request,
            condominio_id=condominio_id,
            comprobantes_existentes=COMPROBANTES_REGISTRADOS,
        )
    except VoucherDuplicadoException as exc:
        raise HTTPException(409, detail={"error_code": exc.error_code, "mensaje": exc.mensaje})


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
