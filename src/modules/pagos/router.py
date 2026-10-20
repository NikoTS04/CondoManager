"""Pagos piloto con autorización por rol, condominio y unidad activa."""

from datetime import date
from decimal import Decimal
from typing import Dict
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from src.core.authorization import (
    autorizar_condominio,
    autorizar_departamento,
    contexto_consulta,
    denegar,
    puede_ver_departamento,
)
from src.core.security import get_current_user, require_role
from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.schemas import (
    ComprobantePagoDTO,
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ConciliarPagoRequest,
    EvaluarMorasRequest,
    EvaluarMorasResponse,
    ReportarPagoRequest,
)
from src.modules.pagos.service import PagosService, VoucherDuplicadoException
from src.modules.usuarios.departamentos import get_departamentos_portal_repository

router = APIRouter(tags=["Pagos y Conciliación"])
COMPROBANTES_REGISTRADOS: Dict[str, Dict] = {}


async def _departamento(usuario, departamento_id, repository, *, escritura=False):
    if not puede_ver_departamento(usuario, departamento_id):
        denegar("El departamento no pertenece a sus vínculos activos.")
    depto = await repository.obtener(departamento_id)
    if not depto:
        raise HTTPException(404, detail={"error_code": "DEPARTAMENTO_NO_ENCONTRADO"})
    autorizar_departamento(usuario, departamento_id, depto["condominio_id"], escritura=escritura)
    if escritura and not depto["activo"]:
        denegar("El departamento se encuentra inactivo.")
    return depto


@router.get("/pagos/comprobantes", response_model=list[ComprobantePagoDTO])
async def listar_comprobantes(
    user: dict = Depends(get_current_user), condominio_id: UUID | None = None
):
    cid = contexto_consulta(user, condominio_id)
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


@router.post("/pagos/reportar", response_model=ComprobanteRecibidoResponse, status_code=202)
async def reportar_pago(
    request: ReportarPagoRequest,
    user: dict = Depends(get_current_user),
    repository=Depends(get_departamentos_portal_repository),
):
    depto = await _departamento(user, request.departamento_id, repository, escritura=True)
    try:
        return PagosService.procesar_reporte_pago(
            request=request,
            condominio_id=str(depto["condominio_id"]),
            comprobantes_existentes=COMPROBANTES_REGISTRADOS,
        )
    except VoucherDuplicadoException as exc:
        raise HTTPException(409, detail={"error_code": exc.error_code, "mensaje": exc.mensaje})


@router.post("/pagos/{comprobante_id}/conciliar", response_model=ConciliacionResultResponse)
async def conciliar_pago(
    comprobante_id: UUID,
    request: ConciliarPagoRequest,
    user: dict = Depends(require_role(["ADMIN_JUNTA", "SUPERADMIN"])),
    repository=Depends(get_departamentos_portal_repository),
):
    comprobante = next(
        (c for c in COMPROBANTES_REGISTRADOS.values() if c["id"] == comprobante_id), None
    )
    if not comprobante:
        raise HTTPException(404, detail={"error_code": "COMPROBANTE_NO_ENCONTRADO"})
    autorizar_condominio(user, comprobante["condominio_id"], escritura=True)
    depto = await _departamento(user, comprobante["departamento_id"], repository, escritura=True)
    # La conciliación sigue siendo una simulación; no modifica las cuotas SQL.
    cuotas_mock = [
        {
            "id": uuid4(),
            "fecha_vencimiento": date(2026, 9, 20),
            "monto_total_exigible": comprobante["monto"],
            "monto_pagado": Decimal("0.00"),
            "estado": "PENDIENTE",
        }
    ]
    try:
        result = PagosService.conciliar_comprobante(
            comprobante=comprobante,
            decision=request.decision,
            cuotas_pendientes=cuotas_mock,
            departamento=depto,
            motivo_rechazo=request.motivo_rechazo,
        )
        if result.departamento_habilitado_reservas:
            depto["deuda_vencida"] = Decimal("0.00")
        return result
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))


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
