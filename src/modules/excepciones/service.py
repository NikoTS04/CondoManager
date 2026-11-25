"""Bandeja CON-66 sobre alertas de correo y auditoría existentes."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import contexto_consulta, denegar
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.security import validar_sesion
from src.modules.excepciones.jobs import ExcepcionesJobService
from src.modules.excepciones.schemas import (
    Accion,
    DetalleExcepcionDTO,
    EfectoCorreo,
    Estado,
    EvidenciaCorreo,
    ExcepcionDTO,
    PaginaExcepcionesDTO,
    ResolucionDTO,
    SolicitudResolucion,
)
from src.modules.notificaciones.models import AlertaNotificacion, Notificacion
from src.modules.notificaciones.persistencia import NotificacionesPersistentesService
from src.modules.notificaciones.schemas import ReenviarNotificacionRequest
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

AUDITORIA_RESOLUCION = "EXCEPCION_CORREO_RESUELTA"
CAUSAS_CON_REENVIO = {"ERROR_DEFINITIVO", "INTENTOS_AGOTADOS", "DESTINATARIO_INVALIDO"}


def estado_excepcion(alerta: AlertaNotificacion, aviso: Notificacion) -> Estado:
    if alerta.atendida_en is None:
        return "ABIERTA"
    if aviso.ciclo != alerta.ciclo + 1:
        return "RESUELTA"
    if aviso.estado in {"EN_COLA", "REINTENTANDO"}:
        return "EN_PROCESO"
    return "RESUELTA" if aviso.estado in {"ENVIADO", "ENTREGADO"} else "FALLIDA"


def requiere_revision_correo(alerta: AlertaNotificacion, aviso: Notificacion) -> bool:
    return (
        alerta.atendida_en is None
        and aviso.ciclo == alerta.ciclo
        and (
            alerta.tipo == "ACEPTACION_INCIERTA"
            or (aviso.error_mensaje or "").startswith("ACEPTACION_INCIERTA")
        )
    )


def acciones_permitidas(alerta: AlertaNotificacion, aviso: Notificacion) -> list[Accion]:
    if (
        alerta.atendida_en is not None
        or aviso.ciclo != alerta.ciclo
        or aviso.estado != "FALLIDO_PERMANENTE"
        or requiere_revision_correo(alerta, aviso)
    ):
        return []
    if alerta.tipo in CAUSAS_CON_REENVIO:
        return ["REENVIAR_CORREO", "CERRAR_CON_MOTIVO"]
    return ["CERRAR_CON_MOTIVO"]


def resumen(alerta: AlertaNotificacion, aviso: Notificacion) -> ExcepcionDTO:
    return ExcepcionDTO(
        id=alerta.id,
        origen="CORREO",
        operacion_id=str(aviso.id),
        causa=alerta.mensaje,
        prioridad="MEDIA" if alerta.tipo == "DESTINATARIO_INVALIDO" else "ALTA",
        estado=estado_excepcion(alerta, aviso),
        creada_en=alerta.creada_en,
    )


def decision(registro: AuditoriaLogORM) -> ResolucionDTO:
    datos = registro.estado_posterior
    return ResolucionDTO(
        id=registro.id,
        accion=datos["accion"],
        motivo=registro.motivo,
        actor_id=registro.actor_id,
        fecha=registro.timestamp,
        estado=datos["estado"],
        efecto=datos["efecto"],
    )


class ExcepcionesService:
    def __init__(self, session: AsyncSession):
        self.db = session

    @staticmethod
    def consulta(cid: UUID):
        return (
            select(AlertaNotificacion, Notificacion)
            .join(
                Notificacion,
                (Notificacion.id == AlertaNotificacion.notificacion_id)
                & (Notificacion.condominio_id == AlertaNotificacion.condominio_id),
            )
            .where(
                AlertaNotificacion.condominio_id == cid,
                Notificacion.canal == "EMAIL",
                Notificacion.finalidad == "OPERATIVA",
            )
        )

    async def listar(self, usuario: dict, offset: int, limit: int) -> PaginaExcepcionesDTO:
        if usuario["rol"] == "SUPERADMIN":
            return await ExcepcionesJobService(self.db).listar(offset, limit)
        consulta = self.consulta(contexto_consulta(usuario)).order_by(
            AlertaNotificacion.atendida_en.is_not(None),
            AlertaNotificacion.creada_en.desc(),
            AlertaNotificacion.id.desc(),
        )
        filas = (await self.db.execute(consulta.offset(offset).limit(limit + 1))).all()
        return PaginaExcepcionesDTO(
            items=[resumen(*fila) for fila in filas[:limit]],
            hay_mas=len(filas) > limit,
        )

    async def _caso(self, cid: UUID, id: UUID):
        caso = (
            await self.db.execute(self.consulta(cid).where(AlertaNotificacion.id == id))
        ).one_or_none()
        if caso is None:
            raise APIError(404, "EXCEPCION_NO_ENCONTRADA", "La excepción no está disponible.")
        return caso

    async def _historial(self, alerta: AlertaNotificacion):
        return (
            await self.db.scalars(
                select(AuditoriaLogORM)
                .where(
                    AuditoriaLogORM.condominio_id == alerta.condominio_id,
                    AuditoriaLogORM.accion_ejecutada == AUDITORIA_RESOLUCION,
                    AuditoriaLogORM.estado_posterior["excepcion_id"].astext == str(alerta.id),
                )
                .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            )
        ).all()

    async def detalle(self, usuario: dict, id: UUID) -> DetalleExcepcionDTO:
        if usuario["rol"] == "SUPERADMIN":
            return await ExcepcionesJobService(self.db).detalle(id)
        alerta, aviso = await self._caso(contexto_consulta(usuario), id)
        return DetalleExcepcionDTO(
            **resumen(alerta, aviso).model_dump(),
            evidencia=EvidenciaCorreo(
                tipo_evento=aviso.tipo_evento,
                ciclo_fallido=alerta.ciclo,
                ciclo_actual=aviso.ciclo,
                estado_operacion=aviso.estado,
            ),
            historial=[decision(registro) for registro in await self._historial(alerta)],
            acciones_permitidas=acciones_permitidas(alerta, aviso),
            requiere_revision_correo=requiere_revision_correo(alerta, aviso),
        )

    async def resolver(
        self, usuario: dict, id: UUID, clave: UUID, solicitud: SolicitudResolucion
    ) -> ResolucionDTO:
        if usuario["rol"] == "SUPERADMIN":
            return await ExcepcionesJobService(self.db).resolver(usuario, id, clave, solicitud)
        cid = contexto_consulta(usuario)
        # Conserva la huella de los comandos de correo registrados antes de CON-66 jobs.
        huella = sha256(solicitud.model_dump_json(exclude={"responsable"}).encode()).hexdigest()
        async with self.db.begin():
            identidad = SQLAlchemyUsuariosRepository(self.db)
            if await identidad.contexto(cid, bloquear=True) is None:
                denegar()
            await validar_sesion(usuario, identidad)
            alerta, aviso = await self._caso(cid, id)
            # Mismo orden de bloqueo que el reenvío existente y el worker.
            await self.db.refresh(aviso, with_for_update=True)
            await self.db.refresh(alerta, with_for_update=True)
            for registro in await self._historial(alerta):
                datos = registro.estado_posterior
                if datos["clave"] == str(clave):
                    if datos["huella"] != huella:
                        raise APIError(
                            409, "CLAVE_REUTILIZADA", "La clave pertenece a otra decisión."
                        )
                    return decision(registro)
            if solicitud.accion not in acciones_permitidas(alerta, aviso):
                raise APIError(
                    409, "ACCION_NO_DISPONIBLE", "La acción ya no está permitida para este caso."
                )

            anterior = {"estado": "ABIERTA", "estado_operacion": aviso.estado, "ciclo": aviso.ciclo}
            if solicitud.accion == "REENVIAR_CORREO":
                await NotificacionesPersistentesService(self.db).reencolar_bajo_bloqueo(
                    aviso,
                    ReenviarNotificacionRequest(nuevo_destinatario=solicitud.nuevo_destinatario),
                    usuario,
                )
                estado = "EN_PROCESO"
            else:
                await self._cerrar(aviso, usuario)
                estado = "RESUELTA"

            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario,
                cid,
                alerta.departamento_id,
                AUDITORIA_RESOLUCION,
                solicitud.motivo,
                anterior,
                {
                    "excepcion_id": str(id),
                    "clave": str(clave),
                    "huella": huella,
                    "accion": solicitud.accion,
                    "estado": estado,
                    "efecto": EfectoCorreo(
                        operacion_id=str(aviso.id),
                        ciclo=aviso.ciclo,
                        estado_operacion=aviso.estado,
                    ).model_dump(),
                },
            )
            return decision((await self._historial(alerta))[0])

    async def _cerrar(self, aviso: Notificacion, usuario: dict) -> None:
        ahora = datetime.now(UTC)
        await self.db.execute(
            update(AlertaNotificacion)
            .where(
                AlertaNotificacion.notificacion_id == aviso.id,
                AlertaNotificacion.condominio_id == aviso.condominio_id,
                AlertaNotificacion.ciclo == aviso.ciclo,
                AlertaNotificacion.atendida_en.is_(None),
            )
            .values(atendida_en=ahora, atendida_por=UUID(usuario["sub"]))
        )
        aviso.estado = "OMITIDO"
        aviso.fecha_actualizacion = ahora
