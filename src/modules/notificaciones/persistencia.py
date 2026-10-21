"""API de comunicaciones: confirmar cola no equivale a entregar un mensaje."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy import select

from src.core.authorization import autorizar_condominio
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import validar_sesion
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.schemas import NotificacionLogDTO
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository


class NotificacionesPersistentesService:
    def __init__(self, session):
        self.session = session
        self.repo = NotificacionesRepository(session)

    @staticmethod
    def dto(log):
        return NotificacionLogDTO.model_validate(
            {
                **{k: getattr(log, k) for k in NotificacionLogDTO.model_fields},
                "condominio_id": str(log.condominio_id),
                "departamento_id": str(log.departamento_id),
            }
        )

    async def listar(self, usuario, cid=None, did=None, estado=None, canal=None):
        async with self.session.begin():
            return [self.dto(n) for n in await self.repo.listar(usuario, cid, did, estado, canal)]

    async def despachar(self, request, usuario):
        try:
            cid, did = UUID(request.condominio_id), UUID(request.departamento_id)
        except ValueError:
            raise APIError(
                422, "CONTEXTO_INVALIDO", "Use UUID de condominio y departamento."
            ) from None
        autorizar_condominio(usuario, cid, escritura=True)
        async with self.session.begin():
            await SQLAlchemyPagosRepository(self.session).departamento(
                did, usuario, escritura=True, bloquear=True
            )
            await validar_sesion(usuario, SQLAlchemyUsuariosRepository(self.session))
            destinatarios = await self.repo.destinatarios(cid, did, request.canal.value)
            destino = next(
                ((u, d, c) for u, d, c in destinatarios if c == request.destinatario), None
            )
            if destino is None:
                raise APIError(
                    422, "DESTINATARIO_NO_AUTORIZADO", "Seleccione un contacto activo de la unidad."
                )
            u, d, contacto = destino
            evento = uuid4()
            log = await self.repo.encolar(
                cid=cid,
                did=did,
                usuario=u,
                contacto=contacto,
                evento=evento,
                operacion=evento,
                tipo=request.tipo_evento,
                canal=request.canal.value,
                contexto={**request.contexto, "nombre": u.nombre, "dpto": d.numero},
            )
            return self.dto(log)

    async def comunicado(self, request, usuario):
        try:
            cid = UUID(request.condominio_id)
        except ValueError:
            raise APIError(422, "CONTEXTO_INVALIDO", "Use un UUID de condominio.") from None
        autorizar_condominio(usuario, cid, escritura=True)
        async with self.session.begin():
            identidad = SQLAlchemyUsuariosRepository(self.session)
            if await identidad.contexto(cid, bloquear=True) is None:
                raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio activo.")
            await validar_sesion(usuario, identidad)
            destinos = await self.repo.destinatarios(cid, canal=request.canal.value)
            evento = uuid4()
            for u, d, contacto in destinos:
                await self.repo.encolar(
                    cid=cid,
                    did=d.id,
                    usuario=u,
                    contacto=contacto,
                    evento=evento,
                    operacion=d.id,
                    tipo="NOTIF_COMUNICADO_GENERAL",
                    canal=request.canal.value,
                    contexto={
                        "titulo": request.titulo,
                        "mensaje": request.mensaje,
                        "remitente": request.remitente,
                    },
                )
        return {"condominio_id": str(cid), "generadas": len(destinos), "estado_general": "EN_COLA"}

    async def reenviar(self, id, request, usuario):
        async with self.session.begin():
            log = await self.session.get(Notificacion, id)
            if log is None:
                raise APIError(404, "NOTIFICACION_NO_HALLADA", "No existe la notificación.")
            autorizar_condominio(usuario, log.condominio_id, escritura=True)
            identidad = SQLAlchemyUsuariosRepository(self.session)
            await identidad.contexto(log.condominio_id, bloquear=True)
            await validar_sesion(usuario, identidad)
            log = await self.session.scalar(
                select(Notificacion)
                .where(Notificacion.id == id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if log.estado != "FALLIDO_PERMANENTE":
                return self.dto(log)
            nuevo = request.nuevo_destinatario if request else None
            destinos = await self.repo.destinatarios(
                log.condominio_id, log.departamento_id, log.canal
            )
            if not nuevo or nuevo == log.destinatario:
                raise APIError(
                    409,
                    "INTENTOS_AGOTADOS",
                    "Corrija el contacto autorizado antes de iniciar otro ciclo.",
                )
            if not any(u.id == log.usuario_destinatario_id and c == nuevo for u, _, c in destinos):
                raise APIError(
                    422,
                    "DESTINATARIO_NO_AUTORIZADO",
                    "El contacto no pertenece al destinatario activo.",
                )
            anterior = {"ciclo": log.ciclo, "estado": log.estado}
            log.destinatario = nuevo
            log.ciclo += 1
            log.intentos = 0
            log.estado = "EN_COLA"
            log.proximo_reintento = None
            log.bloqueado_hasta = None
            log.error_mensaje = None
            log.proveedor_message_id = None
            log.fecha_actualizacion = datetime.now(UTC)
            await SQLAlchemyPagosRepository(self.session).auditar(
                usuario,
                log.condominio_id,
                log.departamento_id,
                "NOTIFICACION_REENVIO_MANUAL",
                "CONTACTO_AUTORIZADO_CORREGIDO",
                anterior,
                {"ciclo": log.ciclo, "estado": log.estado},
            )
            return self.dto(log)


def get_notificaciones_service(session=Depends(get_db_session, use_cache=False)):
    return NotificacionesPersistentesService(session)
