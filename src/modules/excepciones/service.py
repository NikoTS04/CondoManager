"""Bandeja de excepciones: persistencia, evidencia y resolución trazable (CON-66/86)."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import contexto_consulta, denegar
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.reintentos_job import puede_reintentar_job
from src.core.roles import RolUsuario
from src.core.security import validar_sesion
from src.modules.condominios.models import Condominio
from src.modules.excepciones.models import EvidenciaExcepcion, Excepcion, ResolucionExcepcion
from src.modules.notificaciones.models import (
    AlertaNotificacion,
    EstadoJobNotificaciones,
    Notificacion,
)
from src.modules.notificaciones.persistencia import NotificacionesPersistentesService
from src.modules.notificaciones.schemas import ReenviarNotificacionRequest
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

Accion = Literal["REENVIAR_CORREO", "REINTENTAR_JOB", "CERRAR_CON_MOTIVO"]
Estado = Literal["ABIERTA", "EN_PROCESO", "RESUELTA", "FALLIDA"]
AUDITORIA_RESOLUCION = "EXCEPCION_CORREO_RESUELTA"
CAUSAS_CON_REENVIO = {"ERROR_DEFINITIVO", "INTENTOS_AGOTADOS", "DESTINATARIO_INVALIDO"}
CONDOMINIO_SISTEMA = UUID("3709ed64-791a-5cd8-99c7-142ab3ee590c")


class SolicitudResolucion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accion: Accion
    motivo: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\x00]+$"
        ),
    ]
    nuevo_destinatario: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, min_length=1, max_length=320, pattern=r"^[^\x00]+$"
            ),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def destinatario_segun_accion(self):
        if (self.accion == "REENVIAR_CORREO") != (self.nuevo_destinatario is not None):
            raise ValueError("El contacto corregido se requiere únicamente para reenviar.")
        return self


class ExcepcionDTO(BaseModel):
    id: UUID
    origen: Literal["CORREO", "JOB"]
    operacion_id: str
    causa: str
    prioridad: Literal["ALTA", "MEDIA"]
    estado: Estado
    creada_en: datetime


class EfectoCorreo(BaseModel):
    operacion_id: str
    ciclo: int
    estado_operacion: str


class EfectoJob(BaseModel):
    nombre: str
    estado_proceso: str
    reintentado: bool


class EfectoCierre(BaseModel):
    operacion_id: str
    estado_operacion: str


Efecto = EfectoCorreo | EfectoJob | EfectoCierre | dict[str, Any]


class ResolucionDTO(BaseModel):
    id: UUID
    accion: Accion
    motivo: str
    actor_id: str
    fecha: datetime
    estado: Estado
    efecto: Efecto


class EvidenciaCorreo(BaseModel):
    tipo_evento: str
    ciclo_fallido: int
    ciclo_actual: int
    estado_operacion: str
    origen: Literal["CORREO", "JOB"] = "CORREO"
    operacion_id: str = ""
    referencia_correlacion: str | None = None
    detalle: dict[str, Any] = {}


class DetalleExcepcionDTO(ExcepcionDTO):
    evidencia: EvidenciaCorreo
    historial: list[ResolucionDTO]
    acciones_permitidas: list[Accion]
    requiere_revision_correo: bool


class PaginaExcepcionesDTO(BaseModel):
    items: list[ExcepcionDTO]
    hay_mas: bool


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


def estado_job(alerta: AlertaNotificacion) -> Estado:
    return "ABIERTA" if alerta.atendida_en is None else "RESUELTA"


def resumen(alerta: AlertaNotificacion, aviso: Notificacion | None) -> ExcepcionDTO:
    if aviso is None:
        return ExcepcionDTO(
            id=alerta.id,
            origen="JOB",
            operacion_id=alerta.origen_id,
            causa=alerta.mensaje,
            prioridad="ALTA",
            estado=estado_job(alerta),
            creada_en=alerta.creada_en,
        )
    return ExcepcionDTO(
        id=alerta.id,
        origen="CORREO",
        operacion_id=str(aviso.id),
        causa=alerta.mensaje,
        prioridad="MEDIA" if alerta.tipo == "DESTINATARIO_INVALIDO" else "ALTA",
        estado=estado_excepcion(alerta, aviso),
        creada_en=alerta.creada_en,
    )


def acciones_job(alerta: AlertaNotificacion) -> list[Accion]:
    if alerta.atendida_en is not None:
        return []
    if puede_reintentar_job(alerta.origen_id):
        return ["REINTENTAR_JOB", "CERRAR_CON_MOTIVO"]
    return ["CERRAR_CON_MOTIVO"]


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


def decision_persistida(registro: ResolucionExcepcion) -> ResolucionDTO:
    return ResolucionDTO(
        id=registro.id,
        accion=registro.accion,
        motivo=registro.motivo,
        actor_id=str(registro.actor_id),
        fecha=registro.creado_en,
        estado=registro.estado,
        efecto=registro.efecto,
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

    @staticmethod
    def consulta_job():
        return select(AlertaNotificacion).where(AlertaNotificacion.origen_tipo == "JOB")

    async def _asegurar_excepcion(
        self, alerta: AlertaNotificacion, aviso: Notificacion | None
    ) -> Excepcion:
        await self.db.execute(
            pg_insert(Excepcion)
            .values(
                id=uuid4(),
                alerta_id=alerta.id,
                notificacion_id=alerta.notificacion_id,
                condominio_id=alerta.condominio_id,
                origen=alerta.origen_tipo,
                operacion_id=alerta.origen_id,
                causa=alerta.mensaje,
                prioridad="MEDIA" if alerta.tipo == "DESTINATARIO_INVALIDO" else "ALTA",
                estado=estado_job(alerta) if aviso is None else estado_excepcion(alerta, aviso),
                referencia_correlacion=alerta.referencia_correlacion,
            )
            .on_conflict_do_nothing(index_elements=["alerta_id"])
        )
        excepcion = await self.db.scalar(select(Excepcion).where(Excepcion.alerta_id == alerta.id))
        tiene_evidencia = await self.db.scalar(
            select(EvidenciaExcepcion.id).where(EvidenciaExcepcion.excepcion_id == excepcion.id)
        )
        if tiene_evidencia is None:
            self.db.add(
                EvidenciaExcepcion(
                    excepcion_id=excepcion.id,
                    detalle={
                        "origen": alerta.origen_tipo,
                        "operacion_id": alerta.origen_id,
                        "ciclo": alerta.ciclo,
                        "referencia_correlacion": alerta.referencia_correlacion,
                        "estado_operacion": aviso.estado if aviso is not None else None,
                        "detalle": (aviso.error_mensaje if aviso is not None else None),
                    },
                )
            )
        return excepcion

    async def listar(self, usuario: dict, offset: int, limit: int) -> PaginaExcepcionesDTO:
        es_superadmin = usuario["rol"] == RolUsuario.SUPERADMIN
        cid = None if es_superadmin else contexto_consulta(usuario)
        consulta = self.consulta(cid).order_by(
            AlertaNotificacion.atendida_en.is_not(None),
            AlertaNotificacion.creada_en.desc(),
            AlertaNotificacion.id.desc(),
        )
        filas = [
            (alerta, aviso)
            for alerta, aviso in (
                await self.db.execute(consulta.offset(offset).limit(limit + 1))
            ).all()
        ]
        if es_superadmin:
            consulta_job = self.consulta_job().order_by(
                AlertaNotificacion.atendida_en.is_not(None),
                AlertaNotificacion.creada_en.desc(),
                AlertaNotificacion.id.desc(),
            )
            filas.extend(
                (alerta, None)
                for alerta in (
                    await self.db.scalars(consulta_job.offset(offset).limit(limit + 1))
                ).all()
            )
            filas.sort(key=lambda fila: fila[0].creada_en, reverse=True)
        visibles = filas[:limit]
        for alerta, aviso in visibles:
            await self._asegurar_excepcion(alerta, aviso)
        return PaginaExcepcionesDTO(
            items=[resumen(alerta, aviso) for alerta, aviso in visibles],
            hay_mas=len(filas) > limit,
        )

    async def _caso(self, usuario: dict, id: UUID):
        if usuario["rol"] == RolUsuario.SUPERADMIN:
            alerta = await self.db.scalar(
                select(AlertaNotificacion).where(AlertaNotificacion.id == id)
            )
            if alerta is None:
                raise APIError(404, "EXCEPCION_NO_ENCONTRADA", "La excepción no está disponible.")
            return alerta, (
                await self.db.get(Notificacion, alerta.notificacion_id)
                if alerta.notificacion_id is not None
                else None
            )
        caso = (
            await self.db.execute(
                self.consulta(contexto_consulta(usuario)).where(AlertaNotificacion.id == id)
            )
        ).one_or_none()
        if caso is None:
            raise APIError(404, "EXCEPCION_NO_ENCONTRADA", "La excepción no está disponible.")
        return caso

    async def _historial(self, alerta: AlertaNotificacion):
        excepcion = await self.db.scalar(select(Excepcion).where(Excepcion.alerta_id == alerta.id))
        if excepcion is not None:
            registros = (
                await self.db.scalars(
                    select(ResolucionExcepcion)
                    .where(ResolucionExcepcion.excepcion_id == excepcion.id)
                    .order_by(ResolucionExcepcion.creado_en.desc(), ResolucionExcepcion.id.desc())
                )
            ).all()
            if registros:
                return [decision_persistida(registro) for registro in registros]
        cid = alerta.condominio_id or CONDOMINIO_SISTEMA
        return (
            await self.db.scalars(
                select(AuditoriaLogORM)
                .where(
                    AuditoriaLogORM.condominio_id == cid,
                    AuditoriaLogORM.accion_ejecutada == AUDITORIA_RESOLUCION,
                    AuditoriaLogORM.estado_posterior["excepcion_id"].astext == str(alerta.id),
                )
                .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            )
        ).all()

    async def detalle(self, usuario: dict, id: UUID) -> DetalleExcepcionDTO:
        alerta, aviso = await self._caso(usuario, id)
        excepcion = await self._asegurar_excepcion(alerta, aviso)
        evidencia = await self.db.scalar(
            select(EvidenciaExcepcion)
            .where(EvidenciaExcepcion.excepcion_id == excepcion.id)
            .order_by(EvidenciaExcepcion.creado_en.desc())
        )
        return DetalleExcepcionDTO(
            **resumen(alerta, aviso).model_dump(),
            evidencia=EvidenciaCorreo(
                tipo_evento=aviso.tipo_evento if aviso is not None else alerta.tipo,
                ciclo_fallido=alerta.ciclo,
                ciclo_actual=aviso.ciclo if aviso is not None else alerta.ciclo,
                estado_operacion=aviso.estado if aviso is not None else (alerta.tipo or "JOB"),
                origen=alerta.origen_tipo,
                operacion_id=alerta.origen_id,
                referencia_correlacion=alerta.referencia_correlacion,
                detalle=(evidencia.detalle if evidencia is not None else {}),
            ),
            historial=[
                registro if isinstance(registro, ResolucionDTO) else decision(registro)
                for registro in await self._historial(alerta)
            ],
            acciones_permitidas=(
                acciones_permitidas(alerta, aviso) if aviso is not None else acciones_job(alerta)
            ),
            requiere_revision_correo=(
                requiere_revision_correo(alerta, aviso) if aviso is not None else False
            ),
        )

    async def _reintentar_job(self, nombre: str) -> dict[str, Any]:
        registro = await self.db.scalar(
            select(EstadoJobNotificaciones)
            .where(EstadoJobNotificaciones.nombre == nombre)
            .with_for_update()
        )
        if registro is None:
            return EfectoJob(
                nombre=nombre, estado_proceso="SIN_REGISTRO", reintentado=False
            ).model_dump()
        registro.estado = "EN_CURSO"
        registro.fin = None
        return EfectoJob(
            nombre=nombre, estado_proceso=registro.estado, reintentado=True
        ).model_dump()

    @staticmethod
    def _atender_alerta_job(alerta: AlertaNotificacion, usuario: dict) -> None:
        alerta.atendida_en = datetime.now(UTC)
        alerta.atendida_por = UUID(str(usuario["sub"]))

    async def resolver(
        self, usuario: dict, id: UUID, clave: UUID, solicitud: SolicitudResolucion
    ) -> ResolucionDTO:
        es_superadmin = usuario["rol"] == RolUsuario.SUPERADMIN
        huella = sha256(solicitud.model_dump_json().encode()).hexdigest()
        async with self.db.begin():
            identidad = SQLAlchemyUsuariosRepository(self.db)
            if es_superadmin:
                centinela = await self.db.scalar(
                    select(Condominio).where(Condominio.id == CONDOMINIO_SISTEMA).with_for_update()
                )
                if centinela is None:
                    denegar()
            elif await identidad.contexto(contexto_consulta(usuario), bloquear=True) is None:
                denegar()
            await validar_sesion(usuario, identidad)
            alerta, aviso = await self._caso(usuario, id)
            await self.db.refresh(alerta, with_for_update=True)
            if aviso is not None:
                await self.db.refresh(aviso, with_for_update=True)
            es_job = alerta.origen_tipo == "JOB"
            if es_job and not es_superadmin:
                denegar("Solo SUPERADMIN puede resolver excepciones globales de job.")
            if es_job and solicitud.accion == "REENVIAR_CORREO":
                raise APIError(409, "ACCION_NO_DISPONIBLE", "Un job no se reenvía por correo.")

            excepcion = await self._asegurar_excepcion(alerta, aviso)
            previa = await self.db.scalar(
                select(ResolucionExcepcion).where(
                    ResolucionExcepcion.excepcion_id == excepcion.id,
                    ResolucionExcepcion.clave_idempotencia == clave,
                )
            )
            if previa is not None:
                if previa.huella != huella:
                    raise APIError(409, "CLAVE_REUTILIZADA", "La clave pertenece a otra decisión.")
                return decision_persistida(previa)
            for registro in await self._historial(alerta):
                if isinstance(registro, ResolucionDTO):
                    continue
                datos = registro.estado_posterior
                if datos.get("clave") == str(clave):
                    if datos["huella"] != huella:
                        raise APIError(
                            409, "CLAVE_REUTILIZADA", "La clave pertenece a otra decisión."
                        )
                    return decision(registro)

            permitidas = acciones_job(alerta) if es_job else acciones_permitidas(alerta, aviso)
            if solicitud.accion not in permitidas:
                raise APIError(
                    409, "ACCION_NO_DISPONIBLE", "La acción ya no está permitida para este caso."
                )

            anterior = {
                "estado": "ABIERTA",
                "estado_operacion": aviso.estado if aviso is not None else "JOB_FALLO_DEFINITIVO",
                "ciclo": alerta.ciclo,
            }
            if solicitud.accion == "REENVIAR_CORREO":
                await NotificacionesPersistentesService(self.db).reencolar_bajo_bloqueo(
                    aviso,
                    ReenviarNotificacionRequest(nuevo_destinatario=solicitud.nuevo_destinatario),
                    usuario,
                )
                estado = "EN_PROCESO"
                efecto = EfectoCorreo(
                    operacion_id=str(aviso.id),
                    ciclo=aviso.ciclo,
                    estado_operacion=aviso.estado,
                ).model_dump()
            elif solicitud.accion == "REINTENTAR_JOB":
                efecto = await self._reintentar_job(alerta.origen_id)
                estado = "EN_PROCESO" if efecto["reintentado"] else "RESUELTA"
                self._atender_alerta_job(alerta, usuario)
            elif aviso is not None:
                await self._cerrar(aviso, usuario)
                estado = "RESUELTA"
                efecto = EfectoCorreo(
                    operacion_id=str(aviso.id),
                    ciclo=aviso.ciclo,
                    estado_operacion=aviso.estado,
                ).model_dump()
            else:
                self._atender_alerta_job(alerta, usuario)
                estado = "RESUELTA"
                efecto = EfectoCierre(
                    operacion_id=alerta.origen_id, estado_operacion="CERRADA"
                ).model_dump()
            excepcion.estado = estado

            registro = ResolucionExcepcion(
                id=uuid4(),
                excepcion_id=excepcion.id,
                accion=solicitud.accion,
                motivo=solicitud.motivo,
                actor_id=UUID(str(usuario["sub"])),
                efecto=efecto,
                clave_idempotencia=clave,
                huella=huella,
                estado=estado,
                creado_en=datetime.now(UTC),
            )
            self.db.add(registro)
            self.db.add(
                EvidenciaExcepcion(
                    excepcion_id=excepcion.id,
                    detalle={
                        "origen": alerta.origen_tipo,
                        "operacion_id": alerta.origen_id,
                        "ciclo": alerta.ciclo,
                        "referencia_correlacion": alerta.referencia_correlacion,
                        "efecto": efecto,
                    },
                )
            )
            await self.db.flush()
            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario,
                CONDOMINIO_SISTEMA if es_job else alerta.condominio_id,
                None if es_job else alerta.departamento_id,
                "EXCEPCION_JOB_RESUELTA" if es_job else AUDITORIA_RESOLUCION,
                solicitud.motivo,
                anterior,
                {
                    "excepcion_id": str(id),
                    "clave": str(clave),
                    "huella": huella,
                    "accion": solicitud.accion,
                    "estado": estado,
                    "efecto": efecto,
                },
            )
            return decision_persistida(registro)

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
