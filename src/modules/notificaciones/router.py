"""Router FastAPI para el Dominio de Notificaciones (Alejandro - PROC-03)."""

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.authorization import autorizar_condominio, autorizar_departamento, contexto_consulta
from src.core.security import require_role
from src.modules.notificaciones.schemas import (
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EnviarComunicadoMasivoRequest,
    EnviarComunicadoMasivoResponse,
    EstadoNotificacionEnum,
    NotificacionLogDTO,
    ReenviarNotificacionRequest,
)
from src.modules.notificaciones.service import NotificacionesService
from src.modules.usuarios.piloto import DEPARTAMENTOS_PILOTO

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones y Comunicaciones"])

# Almacén en memoria de bitácora para desarrollo local y pruebas
NOTIFICACIONES_REGISTRADAS: Dict[uuid.UUID, NotificacionLogDTO] = {}


@router.get(
    "/logs",
    response_model=List[NotificacionLogDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar bitácora de notificaciones despachadas",
)
async def listar_logs(
    departamento_id: Optional[str] = Query(None, description="Filtrar por número de departamento"),
    estado: Optional[EstadoNotificacionEnum] = Query(None, description="Filtrar por estado del envío"),
    canal: Optional[CanalNotificacionEnum] = Query(None, description="Filtrar por canal"),
    condominio_id: uuid.UUID | None = None,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])),
):
    """Retorna los registros de notificaciones aplicando filtros opcionales."""
    cid = contexto_consulta(user, condominio_id)
    resultados = [n for n in NOTIFICACIONES_REGISTRADAS.values() if n.condominio_id == str(cid)]

    if departamento_id:
        resultados = [r for r in resultados if r.departamento_id == departamento_id]
    if estado:
        resultados = [r for r in resultados if r.estado == estado]
    if canal:
        resultados = [r for r in resultados if r.canal == canal]

    return resultados


@router.post(
    "/despachar",
    response_model=NotificacionLogDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Despachar una notificación individual",
)
async def despachar_notificacion(
    request: DespacharNotificacionRequest,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
):
    """Despacha una notificación renderizando la plantilla correspondiente y registrando la entrega."""
    autorizar_condominio(user, request.condominio_id, escritura=True)
    depto = DEPARTAMENTOS_PILOTO.get(request.departamento_id)
    if not depto:
        raise HTTPException(404, detail={"error_code": "DEPARTAMENTO_NO_ENCONTRADO"})
    autorizar_departamento(user, depto["id"], depto["condominio_id"], escritura=True)
    if str(depto["condominio_id"]) != request.condominio_id:
        raise HTTPException(403, detail={"error_code": "ACCESO_DENEGADO"})
    log = NotificacionesService.despachar_notificacion(request)
    NOTIFICACIONES_REGISTRADAS[log.id] = log
    return log


@router.post(
    "/reenviar/{log_id}",
    response_model=NotificacionLogDTO,
    status_code=status.HTTP_200_OK,
    summary="Reintentar o reenviar una notificación fallida",
)
async def reenviar_notificacion(
    log_id: uuid.UUID,
    request: Optional[ReenviarNotificacionRequest] = None,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
):
    """Permite al Administrador reenviar una notificación rebotada, actualizando opcionalmente el destinatario."""
    log = NOTIFICACIONES_REGISTRADAS.get(log_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOTIFICACION_NO_HALLADA", "mensaje": "Registro de notificación no encontrado."},
        )

    autorizar_condominio(user, log.condominio_id, escritura=True)
    nuevo_destinatario = request.nuevo_destinatario if request else None
    log_actualizado = NotificacionesService.reenviar_notificacion_manual(
        log=log,
        nuevo_destinatario=nuevo_destinatario,
    )
    NOTIFICACIONES_REGISTRADAS[log_id] = log_actualizado
    return log_actualizado


@router.post(
    "/comunicado-masivo",
    response_model=EnviarComunicadoMasivoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Despacho de comunicado oficial masivo a todos los departamentos",
)
async def despachar_comunicado_masivo(
    request: EnviarComunicadoMasivoRequest,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
):
    """Emite un comunicado extraordinario para todos los 139 departamentos de la comunidad."""
    autorizar_condominio(user, request.condominio_id, escritura=True)
    departamentos = [
        d for d in DEPARTAMENTOS_PILOTO.values()
        if str(d["condominio_id"]) == request.condominio_id and d["activo"]
    ]
    respuesta, logs = NotificacionesService.despachar_comunicado_masivo(
        request=request, departamentos=departamentos
    )

    for log in logs:
        NOTIFICACIONES_REGISTRADAS[log.id] = log

    return respuesta
