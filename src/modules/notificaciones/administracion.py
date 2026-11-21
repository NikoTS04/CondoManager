"""Controles humanos de correo y supervisión contextual de la cola."""

from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from src.core.authorization import autorizar_condominio, contexto_consulta
from src.core.config import settings
from src.core.errors import APIError
from src.modules.notificaciones.comunicados import ComunicadosService
from src.modules.notificaciones.models import (
    AlertaNotificacion,
    ContactoBloqueado,
    EstadoJobNotificaciones,
    IntentoNotificacion,
    Notificacion,
    PoliticaNotificaciones,
)
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.pagos.repository import SQLAlchemyPagosRepository


class AdministracionNotificaciones:
    def __init__(self, db):
        self.db = db

    async def configuracion(self, usuario, cid, datos=None):
        if datos is None:
            autorizar_condominio(usuario, cid)
        async with self.db.begin():
            if datos is not None:
                await ComunicadosService(self.db).autorizar(usuario, cid)
            politica = await self.db.get(PoliticaNotificaciones, cid)
            anterior = {
                "dias": politica.dias if politica else [3, 0],
                "hora": politica.hora if politica else 8,
                "habilitado": politica.habilitado if politica else True,
            }
            if datos is None:
                return anterior
            if politica is not None and datos.model_dump() == anterior:
                return anterior
            if politica is None:
                politica = PoliticaNotificaciones(condominio_id=cid)
                self.db.add(politica)
            for k, v in datos.model_dump().items():
                setattr(politica, k, v)
            # Revisar hoy con la política nueva, sin duplicar claves ya emitidas.
            politica.ultima_fecha = datetime.now(ZoneInfo("America/Lima")).date() - timedelta(days=1)
            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario, cid, None, "NOTIFICACIONES_CONFIGURADAS", "POLITICA_ADMINISTRATIVA",
                anterior, datos.model_dump(),
            )
            return datos.model_dump()

    async def bloqueados(self, usuario, cid):
        cid = contexto_consulta(usuario, cid)
        async with self.db.begin():
            return [{
                "email": c.email, "motivo": c.motivo, "creado_en": c.creado_en,
            } for c in await self.db.scalars(
                select(ContactoBloqueado).where(ContactoBloqueado.condominio_id == cid)
                .order_by(ContactoBloqueado.creado_en.desc()).limit(500)
            )]

    async def reactivar(self, usuario, cid, datos):
        async with self.db.begin():
            await ComunicadosService(self.db).autorizar(usuario, cid)
            email = datos.email.strip().lower()
            contacto = await self.db.get(ContactoBloqueado, (cid, email))
            if contacto:
                await self.db.delete(contacto)
                await SQLAlchemyPagosRepository(self.db).auditar(
                    usuario, cid, None, "CONTACTO_CORREO_REACTIVADO", datos.motivo,
                    {"email": email, "motivo": contacto.motivo, "bloqueado": True},
                    {"email": email, "bloqueado": False},
                )
            return {"estado": "REACTIVADO"}

    async def resolver(self, usuario, id, datos):
        async with self.db.begin():
            log = await self.db.get(Notificacion, id)
            if log is None:
                raise APIError(404, "NOTIFICACION_NO_HALLADA", "No existe la notificación.")
            await ComunicadosService(self.db).autorizar(usuario, log.condominio_id)
            log = await self.db.scalar(
                select(Notificacion).where(Notificacion.id == id).with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                log.ciclo != datos.ciclo or log.intentos != datos.intento
                or not (log.error_mensaje or "").startswith("ACEPTACION_INCIERTA")
            ):
                raise APIError(409, "ESTADO_CAMBIADO", "Revise el estado y el intento actual.")
            intento = await self.db.scalar(select(IntentoNotificacion).where(
                IntentoNotificacion.notificacion_id == id,
                IntentoNotificacion.ciclo == datos.ciclo,
                IntentoNotificacion.numero == datos.intento,
            ).with_for_update())
            if intento is None or intento.terminado_en is None:
                raise APIError(409, "INTENTO_EN_CURSO", "Espere a la recuperación del intento.")
            anterior = {"estado": log.estado, "ciclo": log.ciclo, "intentos": log.intentos}
            if datos.decision == "ACEPTADO":
                if not datos.message_id:
                    raise APIError(422, "MESSAGE_ID_REQUERIDO", "Indique el MessageID verificado en Mailjet.")
                if intento.proveedor_message_id and intento.proveedor_message_id != datos.message_id:
                    raise APIError(409, "MESSAGE_ID_DISTINTO", "El intento tiene otra referencia.")
                log.estado = "ENVIADO"
                intento.proveedor_message_id = log.proveedor_message_id = datos.message_id
            elif datos.decision == "NO_ACEPTADO":
                if not datos.confirmar_no_aceptado:
                    raise APIError(422, "CONFIRMACION_REQUERIDA", "Confirme la revisión y autorización de un nuevo ciclo.")
                if await self.db.get(ContactoBloqueado, (log.condominio_id, log.destinatario.lower())):
                    raise APIError(409, "CONTACTO_BLOQUEADO", "Revise el contacto suprimido.")
                if log.finalidad == "OPERATIVA":
                    destinos = await NotificacionesRepository(self.db).destinatarios(
                        log.condominio_id, log.departamento_id, log.canal
                    )
                    valido = any(u.id == log.usuario_destinatario_id and c == log.destinatario for u, _, c in destinos)
                else:
                    from src.modules.usuarios.comunicaciones import destinatario_identidad_valido
                    valido = await destinatario_identidad_valido(self.db, log, datetime.now(UTC))
                if not valido:
                    raise APIError(409, "DESTINATARIO_INVALIDO", "El destinatario ya no es elegible.")
                log.ciclo += 1
                log.intentos = 0
                log.proveedor_message_id = None
                log.estado = "EN_COLA"
            else:
                log.estado = "OMITIDO"
            log.error_mensaje = None
            log.proximo_reintento = log.bloqueado_hasta = None
            log.fecha_actualizacion = datetime.now(UTC)
            await self.db.execute(update(AlertaNotificacion).where(
                AlertaNotificacion.notificacion_id == id,
                AlertaNotificacion.atendida_en.is_(None),
            ).values(atendida_en=datetime.now(UTC), atendida_por=UUID(usuario["sub"])))
            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario, log.condominio_id, log.departamento_id,
                "NOTIFICACION_INCIERTA_RESUELTA", datos.referencia, anterior,
                {"estado": log.estado, "ciclo": log.ciclo, "decision": datos.decision,
                 "message_id": datos.message_id, "notificacion_id": str(log.id)},
            )
            return {"estado": log.estado, "ciclo": log.ciclo}

    async def operacion(self, usuario, cid):
        cid = contexto_consulta(usuario, cid)
        async with self.db.begin():
            conteos = dict((await self.db.execute(
                select(Notificacion.estado, func.count()).where(Notificacion.condominio_id == cid)
                .group_by(Notificacion.estado)
            )).all())
            pendiente_desde = await self.db.scalar(select(func.min(Notificacion.fecha_creacion)).where(
                Notificacion.condominio_id == cid, Notificacion.estado.in_(["EN_COLA", "REINTENTANDO"])
            ))
            inciertos = await self.db.scalar(select(func.count()).select_from(Notificacion).where(
                Notificacion.condominio_id == cid,
                Notificacion.error_mensaje.startswith("ACEPTACION_INCIERTA"),
            ))
            alertas = await self.db.scalar(select(func.count()).select_from(AlertaNotificacion).where(
                AlertaNotificacion.condominio_id == cid, AlertaNotificacion.atendida_en.is_(None)
            ))
            job = await self.db.get(EstadoJobNotificaciones, "correo")
            return {
                "habilitado": settings.MAILJET_ENABLED, "conteos": conteos,
                "pendiente_desde": pendiente_desde, "inciertos": inciertos,
                "cola_atrasada": bool(settings.MAILJET_ENABLED and pendiente_desde and (
                    pendiente_desde < datetime.now(UTC) - timedelta(minutes=15)
                )),
                "alertas_abiertas": alertas,
                "job": {"inicio": job.inicio, "fin": job.fin, "estado": job.estado} if job else None,
                "requiere_revision": settings.MAILJET_ENABLED and (
                    job is None or job.fin is None or job.fin < datetime.now(UTC) - timedelta(minutes=5)
                    or job.estado != "COMPLETADO"
                ),
            }
