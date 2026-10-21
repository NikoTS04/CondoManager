"""Comunicaciones persistidas y autorizadas por contexto y destinatario."""

from uuid import UUID

from fastapi import APIRouter, Depends

from src.core.security import get_current_user, require_role
from src.modules.notificaciones.persistencia import get_notificaciones_service
from src.modules.notificaciones.schemas import (
    AlertaNotificacionDTO,
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EnviarComunicadoMasivoRequest,
    EnviarComunicadoMasivoResponse,
    EstadoAlertaEnum,
    EstadoNotificacionEnum,
    NotificacionLogDTO,
    ReenviarNotificacionRequest,
)

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones y Comunicaciones"])
admin = require_role(["SUPERADMIN", "ADMIN_JUNTA"])
consulta_alertas = require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])


@router.get("/logs", response_model=list[NotificacionLogDTO])
async def listar_logs(
    departamento_id: UUID | None = None,
    estado: EstadoNotificacionEnum | None = None,
    canal: CanalNotificacionEnum | None = None,
    condominio_id: UUID | None = None,
    user=Depends(get_current_user),
    service=Depends(get_notificaciones_service),
):
    return await service.listar(user, condominio_id, departamento_id, estado, canal)


@router.post("/despachar", response_model=NotificacionLogDTO, status_code=202)
async def despachar_notificacion(
    request: DespacharNotificacionRequest,
    user=Depends(admin),
    service=Depends(get_notificaciones_service),
):
    return await service.despachar(request, user)


@router.post("/reenviar/{log_id}", response_model=NotificacionLogDTO)
async def reenviar_notificacion(
    log_id: UUID,
    request: ReenviarNotificacionRequest | None = None,
    user=Depends(admin),
    service=Depends(get_notificaciones_service),
):
    return await service.reenviar(log_id, request, user)


@router.post("/comunicado-masivo", response_model=EnviarComunicadoMasivoResponse, status_code=202)
async def despachar_comunicado_masivo(
    request: EnviarComunicadoMasivoRequest,
    user=Depends(admin),
    service=Depends(get_notificaciones_service),
):
    return await service.comunicado(request, user)


@router.get("/alertas", response_model=list[AlertaNotificacionDTO])
async def listar_alertas(
    condominio_id: UUID | None = None,
    estado: EstadoAlertaEnum = EstadoAlertaEnum.ABIERTA,
    user=Depends(consulta_alertas),
    service=Depends(get_notificaciones_service),
):
    return await service.listar_alertas(user, condominio_id, estado.value)


@router.post("/alertas/{alerta_id}/atender", response_model=AlertaNotificacionDTO)
async def atender_alerta(
    alerta_id: UUID,
    user=Depends(admin),
    service=Depends(get_notificaciones_service),
):
    return await service.atender_alerta(alerta_id, user)
