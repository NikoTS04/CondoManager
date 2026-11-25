"""Decisiones sobre alertas globales y consumo en el ciclo existente de correo."""

import os
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.errors import APIError
from src.core.security import validar_sesion
from src.modules.excepciones.models import ResolucionJob
from src.modules.excepciones.schemas import (
    Accion,
    DetalleExcepcionDTO,
    EfectoJob,
    Estado,
    EvidenciaJob,
    ExcepcionDTO,
    PaginaExcepcionesDTO,
    ResolucionDTO,
    SolicitudResolucion,
)
from src.modules.notificaciones.models import AlertaNotificacion
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

JOB_NOTIFICACIONES = "notificaciones"
ESTADOS_ACTIVOS = ("EN_COLA", "EN_CURSO")
RESULTADOS: dict[str, Estado] = {
    "EN_COLA": "EN_PROCESO",
    "EN_CURSO": "EN_PROCESO",
    "COMPLETADO": "RESUELTA",
    "FALLIDO": "FALLIDA",
    "INCIERTO": "FALLIDA",
    "OMITIDO": "RESUELTA",
    "PENDIENTE_INFORMACION": "PENDIENTE_INFORMACION",
}
ESTADO_INICIAL = {
    "REINTENTAR_JOB": "EN_COLA",
    "CERRAR_CON_MOTIVO": "OMITIDO",
    "SOLICITAR_INFORMACION": "PENDIENTE_INFORMACION",
}


def estado_job(alerta: AlertaNotificacion, ultima: ResolucionJob | None) -> Estado:
    if alerta.atendida_en is not None:
        return "RESUELTA"
    return RESULTADOS[ultima.resultado] if ultima else "ABIERTA"


def acciones_job(alerta: AlertaNotificacion, historial: list[ResolucionJob]) -> list[Accion]:
    estado = estado_job(alerta, historial[0] if historial else None)
    if estado in {"RESUELTA", "EN_PROCESO"}:
        return []
    acciones: list[Accion] = ["CERRAR_CON_MOTIVO"]
    if estado != "PENDIENTE_INFORMACION":
        acciones.append("SOLICITAR_INFORMACION")
    if (
        alerta.origen_id == JOB_NOTIFICACIONES
        and settings.MAILJET_ENABLED
        and os.getenv("VERCEL_ENV") != "preview"
        and all(r.accion != "REINTENTAR_JOB" for r in historial)
    ):
        acciones.insert(0, "REINTENTAR_JOB")
    return acciones


def resumen_job(alerta: AlertaNotificacion, ultima: ResolucionJob | None) -> ExcepcionDTO:
    return ExcepcionDTO(
        id=alerta.id,
        origen="JOB",
        operacion_id=alerta.origen_id,
        causa=alerta.mensaje,
        prioridad="ALTA",
        estado=estado_job(alerta, ultima),
        creada_en=alerta.creada_en,
    )


def decision_job(registro: ResolucionJob) -> ResolucionDTO:
    return ResolucionDTO(
        id=registro.id,
        accion=registro.accion,
        motivo=registro.motivo,
        actor_id=str(registro.actor_id),
        fecha=registro.fecha,
        estado=RESULTADOS[registro.resultado],
        efecto=EfectoJob(
            operacion_id=registro.nombre_job,
            estado_operacion=registro.resultado,
            intento_id=registro.id if registro.accion == "REINTENTAR_JOB" else None,
            responsable=registro.responsable,
        ),
    )


class ExcepcionesJobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def consulta():
        return select(AlertaNotificacion).where(
            AlertaNotificacion.origen_tipo == "JOB",
            AlertaNotificacion.condominio_id.is_(None),
        )

    @staticmethod
    def decisiones():
        return select(ResolucionJob).order_by(ResolucionJob.fecha.desc(), ResolucionJob.id.desc())

    async def listar(self, offset: int, limit: int) -> PaginaExcepcionesDTO:
        consulta = self.consulta().order_by(
            AlertaNotificacion.atendida_en.is_not(None),
            AlertaNotificacion.creada_en.desc(),
            AlertaNotificacion.id.desc(),
        )
        alertas = (await self.db.scalars(consulta.offset(offset).limit(limit + 1))).all()
        pagina = alertas[:limit]
        decisiones = await self.db.scalars(
            self.decisiones().where(ResolucionJob.alerta_id.in_([alerta.id for alerta in pagina]))
        )
        ultimas: dict[UUID, ResolucionJob] = {}
        for decision in decisiones:
            ultimas.setdefault(decision.alerta_id, decision)
        return PaginaExcepcionesDTO(
            items=[resumen_job(alerta, ultimas.get(alerta.id)) for alerta in pagina],
            hay_mas=len(alertas) > limit,
        )

    async def _caso(self, id: UUID, *, bloquear=False) -> AlertaNotificacion:
        consulta = self.consulta().where(AlertaNotificacion.id == id)
        alerta = await self.db.scalar(consulta.with_for_update() if bloquear else consulta)
        if alerta is None:
            raise APIError(404, "EXCEPCION_NO_ENCONTRADA", "La excepción no está disponible.")
        return alerta

    async def _historial(self, id: UUID) -> list[ResolucionJob]:
        return list(await self.db.scalars(self.decisiones().where(ResolucionJob.alerta_id == id)))

    async def detalle(self, id: UUID) -> DetalleExcepcionDTO:
        alerta = await self._caso(id)
        historial = await self._historial(id)
        ultima = historial[0] if historial else None
        intento = next((r for r in historial if r.accion == "REINTENTAR_JOB"), None)
        return DetalleExcepcionDTO(
            **resumen_job(alerta, ultima).model_dump(),
            evidencia=EvidenciaJob(
                nombre=alerta.origen_id,
                ciclo_fallido=alerta.ciclo,
                referencia_correlacion=alerta.referencia_correlacion,
                intento_id=intento.id if intento else None,
                estado_operacion=intento.resultado if intento else "FALLIDO",
            ),
            historial=[decision_job(registro) for registro in historial],
            acciones_permitidas=acciones_job(alerta, historial),
            requiere_revision_correo=False,
        )

    async def resolver(
        self,
        usuario: dict,
        id: UUID,
        clave: UUID,
        solicitud: SolicitudResolucion,
    ) -> ResolucionDTO:
        huella = sha256(solicitud.model_dump_json().encode()).hexdigest()
        async with self.db.begin():
            await validar_sesion(usuario, SQLAlchemyUsuariosRepository(self.db))
            alerta = await self._caso(id, bloquear=True)
            historial = await self._historial(id)
            previo = next((r for r in historial if r.clave == clave), None)
            if previo:
                if previo.huella != huella:
                    raise APIError(409, "CLAVE_REUTILIZADA", "La clave pertenece a otra decisión.")
                return decision_job(previo)
            if solicitud.accion not in acciones_job(alerta, historial):
                raise APIError(
                    409, "ACCION_NO_DISPONIBLE", "La acción ya no está permitida para este caso."
                )

            if solicitud.accion == "REINTENTAR_JOB":
                # Serializa solicitudes de alertas de distintas fechas del mismo job.
                await self.db.execute(text("SELECT pg_advisory_xact_lock(189562)"))
                activo = await self.db.scalar(
                    select(ResolucionJob.id).where(
                        ResolucionJob.nombre_job == alerta.origen_id,
                        ResolucionJob.resultado.in_(ESTADOS_ACTIVOS),
                    )
                )
                if activo:
                    raise APIError(
                        409, "JOB_REINTENTO_ACTIVO", "La tarea ya tiene un reintento activo."
                    )

            ahora = datetime.now(UTC)
            actor_id = UUID(usuario["sub"])
            if solicitud.accion == "CERRAR_CON_MOTIVO":
                alerta.atendida_en, alerta.atendida_por = ahora, actor_id
            registro = ResolucionJob(
                alerta_id=id,
                nombre_job=alerta.origen_id,
                clave=clave,
                huella=huella,
                accion=solicitud.accion,
                motivo=solicitud.motivo,
                actor_id=actor_id,
                responsable=solicitud.responsable,
                fecha=ahora,
                resultado=ESTADO_INICIAL[solicitud.accion],
            )
            self.db.add(registro)
            await self.db.flush()
            return decision_job(registro)


async def tomar_reintento(sesiones) -> UUID | None:
    """Se llama con el bloqueo del job adquirido en la ejecución programada."""
    ahora = datetime.now(UTC)
    async with sesiones() as db, db.begin():
        await db.execute(
            update(ResolucionJob)
            .where(
                ResolucionJob.nombre_job == JOB_NOTIFICACIONES,
                ResolucionJob.resultado == "EN_CURSO",
            )
            .values(resultado="INCIERTO", fin=ahora)
        )
        registro = await db.scalar(
            select(ResolucionJob)
            .where(
                ResolucionJob.nombre_job == JOB_NOTIFICACIONES, ResolucionJob.resultado == "EN_COLA"
            )
            .with_for_update()
        )
        if registro is None:
            return None
        registro.resultado = "EN_CURSO"
        registro.inicio = ahora
        return registro.id


async def finalizar_reintento(sesiones, id: UUID | None, resultado: str) -> None:
    if id is None:
        return
    ahora = datetime.now(UTC)
    async with sesiones() as db, db.begin():
        registro = await db.get(ResolucionJob, id, with_for_update=True)
        if registro is None or registro.resultado != "EN_CURSO":
            return
        registro.resultado, registro.fin = resultado, ahora
        if resultado == "COMPLETADO":
            alerta = await db.get(AlertaNotificacion, registro.alerta_id, with_for_update=True)
            alerta.atendida_en, alerta.atendida_por = ahora, registro.actor_id
