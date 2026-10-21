"""Router FastAPI persistente para el Dominio de Notificaciones (Alejandro - PROC-03)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import (
    autorizar_condominio,
    contexto_consulta,
    denegar,
    vinculos_activos,
)
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import require_role
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.notificaciones.destinatarios import resolver_destinatarios_condominio
from src.modules.notificaciones.entrega import reprogramar_manual
from src.modules.notificaciones.models import (
    AlertaAdministrativa,
    Notificacion,
    NotificacionIntento,
)
from src.modules.notificaciones.repository import NuevaNotificacion, registrar_notificacion
from src.modules.notificaciones.schemas import (
    AlertaAdministrativaDTO,
    CanalNotificacionEnum,
    EnviarComunicadoMasivoRequest,
    EnviarComunicadoMasivoResponse,
    EstadoNotificacionEnum,
    NotificacionDetalleDTO,
    NotificacionIntentoDTO,
    NotificacionLogDTO,
    OrigenNotificacionEnum,
    ReenviarNotificacionRequest,
)
from src.modules.usuarios.models import UsuarioDepartamento

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones y Comunicaciones"])


def _actor_uuid(user: dict) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(user.get("sub")))
    except (ValueError, TypeError):
        return None


@router.get(
    "/logs",
    response_model=list[NotificacionLogDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar bitácora persistente de notificaciones",
)
async def listar_logs(
    condominio_id: uuid.UUID | None = Query(None, description="Contexto de condominio"),
    departamento_id: uuid.UUID | None = Query(None, description="Filtrar por UUID de departamento"),
    estado: EstadoNotificacionEnum | None = Query(None, description="Filtrar por estado del envío"),
    canal: CanalNotificacionEnum | None = Query(None, description="Filtrar por canal"),
    origen_tipo: OrigenNotificacionEnum | None = Query(
        None, description="Filtrar por tipo de origen"
    ),
    tipo_evento: str | None = Query(None, description="Filtrar por tipo de evento o plantilla"),
    tipo: str | None = Query(None, description="Filtrar por tipo/origen de la comunicación"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[NotificacionLogDTO]:
    """Retorna la bitácora de notificaciones del condominio aplicando filtros y paginación."""
    cid = contexto_consulta(user, condominio_id)
    stmt = select(Notificacion).where(Notificacion.condominio_id == cid)

    if departamento_id is not None:
        stmt = stmt.where(Notificacion.departamento_id == departamento_id)
    if estado is not None:
        stmt = stmt.where(Notificacion.estado == estado.value)
    if canal is not None:
        stmt = stmt.where(Notificacion.canal == canal.value)
    if origen_tipo is not None:
        stmt = stmt.where(Notificacion.origen_tipo == origen_tipo.value)
    if tipo_evento:
        stmt = stmt.where(
            or_(
                Notificacion.tipo_evento == tipo_evento,
                Notificacion.plantilla == tipo_evento,
            )
        )
    if tipo:
        stmt = stmt.where(
            or_(
                Notificacion.origen_tipo == tipo,
                Notificacion.tipo_evento == tipo,
                Notificacion.plantilla == tipo,
            )
        )

    stmt = (
        stmt.order_by(Notificacion.creado_en.desc(), Notificacion.id.desc())
        .limit(limit)
        .offset(offset)
    )
    filas = list((await session.scalars(stmt)).all())
    return [NotificacionLogDTO.model_validate(fila) for fila in filas]


@router.get(
    "/logs/{log_id}",
    response_model=NotificacionDetalleDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar detalle de notificación e historial de intentos",
)
async def obtener_log_detalle(
    log_id: uuid.UUID,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])),
    session: AsyncSession = Depends(get_db_session),
) -> NotificacionDetalleDTO:
    """Devuelve una notificación con su historial de intentos de entrega."""
    notif = await session.get(Notificacion, log_id)
    if notif is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "NOTIFICACION_NO_HALLADA",
            "Registro de notificación no encontrado.",
        )

    autorizar_condominio(user, notif.condominio_id, escritura=False)

    intentos = list(
        (
            await session.scalars(
                select(NotificacionIntento)
                .where(NotificacionIntento.notificacion_id == log_id)
                .order_by(NotificacionIntento.ciclo.asc(), NotificacionIntento.numero.asc())
            )
        ).all()
    )
    base_dto = NotificacionLogDTO.model_validate(notif)
    return NotificacionDetalleDTO(
        **base_dto.model_dump(),
        historial_intentos=[NotificacionIntentoDTO.model_validate(item) for item in intentos],
    )


@router.get(
    "/mis-notificaciones",
    response_model=list[NotificacionLogDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar comunicaciones propias del residente autenticado",
)
async def listar_mis_notificaciones(
    condominio_id: uuid.UUID | None = Query(None, description="Contexto de condominio"),
    departamento_id: uuid.UUID | None = Query(None, description="Filtrar por UUID de unidad"),
    estado: EstadoNotificacionEnum | None = Query(None, description="Filtrar por estado"),
    canal: CanalNotificacionEnum | None = Query(None, description="Filtrar por canal"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role(["RESIDENTE"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[NotificacionLogDTO]:
    """Devuelve únicamente las notificaciones propias (`usuario_id`) de unidades con vínculo activo."""
    cid = contexto_consulta(user, condominio_id)
    uid = _actor_uuid(user)
    if uid is None:
        denegar("Identidad de residente inválida.")

    deptos_sql = set(
        (
            await session.scalars(
                select(UsuarioDepartamento.departamento_id)
                .join(Departamento, UsuarioDepartamento.departamento_id == Departamento.id)
                .join(Edificio, Departamento.edificio_id == Edificio.id)
                .where(
                    UsuarioDepartamento.usuario_id == uid,
                    UsuarioDepartamento.es_activo.is_(True),
                    Departamento.activo.is_(True),
                    Edificio.condominio_id == cid,
                )
            )
        ).all()
    )
    deptos_token: set[uuid.UUID] = set()
    for dpto_str in vinculos_activos(user):
        try:
            deptos_token.add(uuid.UUID(dpto_str))
        except ValueError:
            continue

    total_vinculos_db = (
        await session.scalar(
            select(func.count())
            .select_from(UsuarioDepartamento)
            .where(UsuarioDepartamento.usuario_id == uid)
        )
        or 0
    )
    tiene_vinculos_token = bool(user.get("departamentos"))
    if total_vinculos_db > 0 and tiene_vinculos_token:
        deptos_permitidos = deptos_sql & deptos_token
    elif total_vinculos_db > 0:
        deptos_permitidos = deptos_sql
    else:
        deptos_permitidos = deptos_token

    if departamento_id is not None and departamento_id not in deptos_permitidos:
        denegar("El departamento no pertenece a sus vínculos activos.")

    if not deptos_permitidos:
        return []

    stmt = select(Notificacion).where(
        Notificacion.condominio_id == cid,
        Notificacion.usuario_id == uid,
        or_(
            Notificacion.departamento_id.is_(None),
            Notificacion.departamento_id.in_(deptos_permitidos),
        ),
    )
    if departamento_id is not None:
        stmt = stmt.where(Notificacion.departamento_id == departamento_id)
    if estado is not None:
        stmt = stmt.where(Notificacion.estado == estado.value)
    if canal is not None:
        stmt = stmt.where(Notificacion.canal == canal.value)

    stmt = (
        stmt.order_by(Notificacion.creado_en.desc(), Notificacion.id.desc())
        .limit(limit)
        .offset(offset)
    )
    filas = list((await session.scalars(stmt)).all())
    return [NotificacionLogDTO.model_validate(fila) for fila in filas]


@router.get(
    "/alertas",
    response_model=list[AlertaAdministrativaDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar alertas administrativas de envíos fallidos",
)
async def listar_alertas(
    condominio_id: uuid.UUID | None = Query(None, description="Contexto de condominio"),
    solo_abiertas: bool = Query(True, description="Devolver solo alertas no atendidas"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[AlertaAdministrativaDTO]:
    """Lista las alertas administrativas abiertas del condominio autorizado."""
    cid = contexto_consulta(user, condominio_id)
    stmt = select(AlertaAdministrativa).where(AlertaAdministrativa.condominio_id == cid)
    if solo_abiertas:
        stmt = stmt.where(AlertaAdministrativa.atendida_en.is_(None))
    stmt = (
        stmt.order_by(AlertaAdministrativa.creado_en.desc(), AlertaAdministrativa.id.desc())
        .limit(limit)
        .offset(offset)
    )
    filas = list((await session.scalars(stmt)).all())
    return [AlertaAdministrativaDTO.model_validate(fila) for fila in filas]


@router.post(
    "/alertas/{alerta_id}/atender",
    response_model=AlertaAdministrativaDTO,
    status_code=status.HTTP_200_OK,
    summary="Marcar una alerta administrativa como atendida",
)
async def atender_alerta(
    alerta_id: uuid.UUID,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
    session: AsyncSession = Depends(get_db_session),
) -> AlertaAdministrativaDTO:
    """Marca como atendida una alerta administrativa del condominio autorizado."""
    alerta = await session.get(AlertaAdministrativa, alerta_id)
    if alerta is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "ALERTA_NO_HALLADA",
            "Alerta administrativa no encontrada.",
        )

    autorizar_condominio(user, alerta.condominio_id, escritura=True)

    if alerta.atendida_en is None:
        alerta.atendida_en = datetime.now(UTC)
        alerta.atendida_por = _actor_uuid(user)
        await session.flush()

    return AlertaAdministrativaDTO.model_validate(alerta)


@router.post(
    "/reenviar/{log_id}",
    response_model=NotificacionLogDTO,
    status_code=status.HTTP_200_OK,
    summary="Reprogramar manualmente una notificación en fallo permanente",
)
async def reenviar_notificacion(
    log_id: uuid.UUID,
    request: ReenviarNotificacionRequest | None = None,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
    session: AsyncSession = Depends(get_db_session),
) -> NotificacionLogDTO:
    """Reprograma una notificación en estado FALLIDO_PERMANENTE delegando en entrega.reprogramar_manual."""
    notif = await session.get(Notificacion, log_id)
    if notif is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "NOTIFICACION_NO_HALLADA",
            "Registro de notificación no encontrado.",
        )

    autorizar_condominio(user, notif.condominio_id, escritura=True)
    nuevo_destinatario = request.nuevo_destinatario if request else None
    actualizada = await reprogramar_manual(
        session,
        log_id,
        nuevo_destinatario=nuevo_destinatario,
        actor_id=_actor_uuid(user),
    )
    return NotificacionLogDTO.model_validate(actualizada)


@router.post(
    "/comunicado-masivo",
    response_model=EnviarComunicadoMasivoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar comunicado oficial masivo a residentes con vínculo activo",
)
async def despachar_comunicado_masivo(
    request: EnviarComunicadoMasivoRequest,
    user: dict = Depends(require_role(["SUPERADMIN", "ADMIN_JUNTA"])),
    session: AsyncSession = Depends(get_db_session),
) -> EnviarComunicadoMasivoResponse:
    """Registra persistentemente el comunicado para los residentes activos; el envío lo realiza el worker."""
    cid = autorizar_condominio(user, request.condominio_id, escritura=True)
    condominio = await session.get(Condominio, cid)
    if condominio is None:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            "CONDOMINIO_NO_ENCONTRADO",
            "No existe un condominio con el identificador solicitado.",
        )

    comunicado_id = request.comunicado_id or request.id or uuid.uuid4()
    destinatarios = await resolver_destinatarios_condominio(session, cid)

    destinatarios_unicos = {}
    for dest in destinatarios:
        if dest.usuario_id not in destinatarios_unicos:
            destinatarios_unicos[dest.usuario_id] = dest

    creadas = 0
    for dest in destinatarios_unicos.values():
        clave = f"COMUNICADO:{comunicado_id}:{request.canal.value}:{dest.usuario_id}"
        notificacion_id = await registrar_notificacion(
            session,
            NuevaNotificacion(
                condominio_id=cid,
                departamento_id=dest.departamento_id,
                usuario_id=dest.usuario_id,
                evento_id=comunicado_id,
                tipo_evento="NOTIF_COMUNICADO_GENERAL",
                plantilla="NOTIF_COMUNICADO_GENERAL",
                origen_tipo="COMUNICADO",
                origen_id=comunicado_id,
                clave_deduplicacion=clave,
                canal=request.canal.value,
                destinatario=dest.email,
                contexto={
                    "titulo": request.titulo,
                    "mensaje": request.mensaje,
                    "remitente": request.remitente,
                    "nombre": dest.nombre_completo,
                    "dpto": dest.departamento_numero,
                },
            ),
        )
        if notificacion_id is not None:
            creadas += 1

    return EnviarComunicadoMasivoResponse(
        comunicado_id=comunicado_id,
        condominio_id=str(cid),
        total_destinatarios=len(destinatarios_unicos),
        notificaciones_generadas=creadas,
        estado_general="EN_COLA",
    )
