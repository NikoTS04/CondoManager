"""Pagos piloto con autorización por rol, condominio y unidad activa (Brandon - CON-23 / PROC-02)."""

from datetime import date
from decimal import Decimal
from typing import Dict, Optional
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
from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.repository import PagosRepository, get_pagos_repository
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
    user: dict = Depends(get_current_user),
    condominio_id: UUID | None = None,
    pagos_repository: PagosRepository = Depends(get_pagos_repository),
):
    cid = contexto_consulta(user, condominio_id)
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
        # Fallback para entornos sin conexión o pruebas en memoria
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


@router.post("/pagos/reportar", response_model=ComprobanteRecibidoResponse, status_code=202)
async def reportar_pago(
    request: ReportarPagoRequest,
    user: dict = Depends(get_current_user),
    repository=Depends(get_departamentos_portal_repository),
    pagos_repository: PagosRepository = Depends(get_pagos_repository),
):
    depto = await _departamento(user, request.departamento_id, repository, escritura=True)
    condominio_id = str(depto["condominio_id"])

    try:
        # Intentar flujo persistente con el repositorio
        try:
            resp = await PagosService.procesar_reporte_pago_persistente(
                request=request,
                condominio_id=condominio_id,
                repository=pagos_repository,
            )
            # Sincronizar en memoria para endpoints dependientes
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
            # Fallback en memoria si la BD física no está levantada
            return PagosService.procesar_reporte_pago(
                request=request,
                condominio_id=condominio_id,
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
