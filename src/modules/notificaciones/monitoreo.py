"""CON-68: vista de salud y alertas visibles para administración (solo lectura)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from src.core.authorization import contexto_consulta
from src.core.database import get_db_session
from src.core.roles import RolUsuario
from src.core.salud_operativa import salud_operativa
from src.core.security import require_role
from src.modules.condominios.models import Departamento
from src.modules.notificaciones.alertas import ORIGEN_JOB
from src.modules.notificaciones.models import AlertaNotificacion, Notificacion

router = APIRouter(prefix="/monitoreo", tags=["Sistema"])
solo_global = require_role(["SUPERADMIN"])
consulta = require_role(["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"])


def alerta_visible(alerta, numero, tipo_evento):
    es_job = alerta.origen_tipo == ORIGEN_JOB
    return {
        "id": alerta.id,
        "componente": "job" if es_job else "correo",
        "operacion": alerta.origen_id if es_job else (tipo_evento or alerta.origen_id),
        "referencia_diagnostico": {
            "origen_tipo": alerta.origen_tipo,
            "origen_id": alerta.origen_id,
            "referencia_correlacion": alerta.referencia_correlacion,
        },
        "condominio_id": str(alerta.condominio_id) if alerta.condominio_id else None,
        "departamento_numero": numero,
        "tipo": alerta.tipo,
        "mensaje": alerta.mensaje,
        "estado": "ATENDIDA" if alerta.atendida_en else "ABIERTA",
        "creada_en": alerta.creada_en,
        "atendida_en": alerta.atendida_en,
    }


async def listar_alertas_visibles(db, usuario, condominio_id, estado, limit, offset):
    """Alertas según el alcance del rol: el global ve todas; el resto, solo su condominio."""
    consulta_sql = (
        select(AlertaNotificacion, Departamento.numero, Notificacion.tipo_evento)
        .outerjoin(Departamento, Departamento.id == AlertaNotificacion.departamento_id)
        .outerjoin(Notificacion, Notificacion.id == AlertaNotificacion.notificacion_id)
    )
    if usuario.get("rol") == RolUsuario.SUPERADMIN:
        if condominio_id:
            consulta_sql = consulta_sql.where(AlertaNotificacion.condominio_id == condominio_id)
    else:
        # Las alertas de job tienen condominio nulo, así que este filtro las excluye.
        cid = contexto_consulta(usuario, condominio_id)
        consulta_sql = consulta_sql.where(AlertaNotificacion.condominio_id == cid)
    atendida = AlertaNotificacion.atendida_en
    consulta_sql = consulta_sql.where(
        atendida.is_not(None) if estado == "ATENDIDA" else atendida.is_(None)
    )
    consulta_sql = (
        consulta_sql.order_by(AlertaNotificacion.creada_en.desc(), AlertaNotificacion.id)
        .limit(limit)
        .offset(offset)
    )
    async with db.begin():
        filas = (await db.execute(consulta_sql)).all()
    return [alerta_visible(*fila) for fila in filas]


@router.get("/salud")
async def salud(
    response: Response, user=Depends(solo_global), db=Depends(get_db_session, use_cache=False)
):
    response.headers["Cache-Control"] = "no-store"
    return await salud_operativa(db)


@router.get("/alertas")
async def alertas(
    response: Response,
    condominio_id: UUID | None = None,
    estado: Literal["ABIERTA", "ATENDIDA"] = "ABIERTA",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(consulta),
    db=Depends(get_db_session, use_cache=False),
):
    response.headers["Cache-Control"] = "no-store"
    return await listar_alertas_visibles(db, user, condominio_id, estado, limit, offset)
