"""Registro, asignación y revisión de incidencias con auditoría."""

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urljoin
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import UploadFile
from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from src.core.authorization import (
    autorizar_departamento,
    contexto_consulta,
    denegar,
    vinculos_activos,
)
from src.core.config import settings
from src.core.errors import APIError
from src.core.roles import RolUsuario
from src.core.security import validar_sesion
from src.modules.incidencias.estados import ESTADOS_ASIGNABLES, transicion_permitida
from src.modules.incidencias.models import AsignacionIncidencia, Incidencia
from src.modules.incidencias.schemas import (
    AsignarIncidencia,
    AvisoAsignacionDTO,
    CrearIncidencia,
    RechazarIncidencia,
    RevisarIncidencia,
)
from src.modules.notificaciones.avisos_contrato import (
    AVISO_ASIGNACION_PROVEEDOR,
    AVISO_ASIGNACION_RESIDENTE,
    RolAvisoAsignacion,
    clave_asignacion,
)
from src.modules.notificaciones.models import AlertaNotificacion, Notificacion
from src.modules.notificaciones.repository import AVISO_INCIDENCIA, NotificacionesRepository
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.storage import VoucherStorage
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

MAX_EVIDENCIA = 3 * 1024 * 1024


def contexto_junta(usuario: dict) -> UUID:
    if usuario["rol"] != RolUsuario.ADMIN_JUNTA:
        denegar("Solo Junta puede gestionar la bandeja de incidencias.")
    return contexto_consulta(usuario)


def estado_revision(incidencia: Incidencia) -> dict:
    return {
        "incidencia_id": str(incidencia.id),
        "estado_ticket": incidencia.estado,
        "categoria_confirmada": incidencia.categoria_confirmada,
        "prioridad": incidencia.prioridad,
        "motivo_rechazo": incidencia.motivo_rechazo,
        "version": incidencia.version,
        "asignacion_actual_id": str(incidencia.asignacion_actual_id)
        if incidencia.asignacion_actual_id
        else None,
        "responsable_usuario_id": str(incidencia.responsable_usuario_id)
        if incidencia.responsable_usuario_id
        else None,
        "responsable_proveedor_id": str(incidencia.responsable_proveedor_id)
        if incidencia.responsable_proveedor_id
        else None,
        "plazo": incidencia.plazo.isoformat() if incidencia.plazo else None,
    }


def contexto_lectura(usuario: dict) -> UUID:
    if usuario["rol"] not in (RolUsuario.ADMIN_JUNTA, RolUsuario.AUDITOR):
        denegar("Solo Junta o Auditor puede consultar los avisos de asignación.")
    return contexto_consulta(usuario)


def reportes_propios(usuario: dict):
    return and_(
        Incidencia.reportante_id == UUID(usuario["sub"]),
        Incidencia.departamento_id.in_([UUID(did) for did in vinculos_activos(usuario)]),
    )


async def preparar_evidencia(
    archivo: UploadFile | None,
) -> tuple[bytes | None, str | None, str | None]:
    if archivo is None:
        return None, None, None
    limite = min(MAX_EVIDENCIA, settings.VOUCHER_MAX_BYTES)
    try:
        datos = await archivo.read(limite + 1)
    finally:
        await archivo.close()
    if len(datos) > limite:
        return None, None, "La foto excede el tamaño permitido."
    mensaje = "La foto no es un archivo JPEG o PNG válido."
    if not datos.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8")):
        return None, None, mensaje
    try:
        _, mime = await asyncio.to_thread(VoucherStorage.validar, datos)
    except APIError:
        return None, None, mensaje
    return datos, mime, None


class IncidenciasService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def registrar(
        self, usuario: dict, formulario: CrearIncidencia, clave: UUID
    ) -> tuple[Incidencia, str | None, bool]:
        if usuario["rol"] != RolUsuario.RESIDENTE:
            denegar("Solo el residente puede reportar una incidencia.")
        cid = contexto_consulta(usuario)
        uid = UUID(usuario["sub"])
        did = formulario.departamento_id
        autorizar_departamento(usuario, did, cid, escritura=True)

        datos = formulario.model_dump(mode="json", exclude={"evidencia"})
        if any("\x00" in datos[campo] for campo in ("ubicacion", "categoria", "descripcion")):
            raise APIError(422, "DATOS_INVALIDOS", "Revise el texto ingresado.")
        evidencia, mime, advertencia = await preparar_evidencia(formulario.evidencia)
        huella = sha256(
            json.dumps(
                {
                    **datos,
                    "evidencia_sha256": sha256(evidencia).hexdigest() if evidencia else None,
                    "advertencia_evidencia": advertencia,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

        identidad = SQLAlchemyUsuariosRepository(self.session)
        # Comparte el lock de condominio que serializa la cadena de auditoría.
        if await identidad.contexto(cid, bloquear=True) is None:
            denegar()
        vigente = await validar_sesion(usuario, identidad)
        autorizar_departamento(vigente, did, cid, escritura=True)
        unidad = await identidad.departamento(cid, did, bloquear=True)
        if unidad is None or not unidad[0].activo:
            denegar("El departamento debe estar activo en tu condominio.")

        anterior = await self.session.scalar(
            select(Incidencia).where(
                Incidencia.condominio_id == cid,
                Incidencia.reportante_id == uid,
                Incidencia.clave_idempotencia == clave,
            )
        )
        if anterior is not None:
            if anterior.hash_solicitud != huella:
                raise APIError(
                    409, "CLAVE_IDEMPOTENCIA_REUTILIZADA", "La clave pertenece a otro reporte."
                )
            return anterior, advertencia, False

        incidencia = Incidencia(
            condominio_id=cid,
            reportante_id=uid,
            departamento_id=did,
            clave_idempotencia=clave,
            hash_solicitud=huella,
            ubicacion=formulario.ubicacion,
            categoria=formulario.categoria,
            descripcion=formulario.descripcion,
            urgencia=formulario.urgencia,
            evidencia=evidencia,
            evidencia_mime=mime,
        )
        self.session.add(incidencia)
        await self.session.flush()
        avisos = await self.encolar_aviso(incidencia)
        await SQLAlchemyPagosRepository(self.session).auditar(
            vigente,
            cid,
            did,
            "CREACION_TICKET_INCIDENCIA",
            "REPORTE_RESIDENTE",
            {},
            {
                "incidencia_id": str(incidencia.id),
                "estado_ticket": incidencia.estado,
                "tiene_evidencia": incidencia.tiene_evidencia,
                "avisos_encolados": avisos,
            },
        )
        await self.session.commit()
        return incidencia, advertencia, True

    async def encolar_aviso(self, incidencia: Incidencia) -> int:
        cid = incidencia.condominio_id
        cola = NotificacionesRepository(self.session)
        destinatarios = await cola.destinatarios_junta(cid)
        enlace = urljoin(settings.ACTIVACION_WEB_URL, f"/incidencias/{incidencia.id}")
        for administrador in destinatarios:
            await cola.encolar(
                cid=cid,
                did=incidencia.departamento_id,
                usuario=administrador,
                contacto=administrador.email,
                evento=incidencia.id,
                operacion=incidencia.id,
                tipo=AVISO_INCIDENCIA,
                canal="EMAIL",
                contexto={"incidencia_id": str(incidencia.id), "enlace": enlace},
            )
        return len(destinatarios)

    async def listar(self, usuario: dict, *, offset: int, limit: int) -> dict:
        cid = contexto_junta(usuario)
        prioridad = func.coalesce(Incidencia.prioridad, Incidencia.urgencia)
        orden = case(
            (Incidencia.estado == "RECHAZADO", 2),
            (prioridad == "URGENTE", 0),
            else_=1,
        )
        consulta = select(Incidencia).where(Incidencia.condominio_id == cid).order_by(orden)
        return await self._paginar(consulta, offset=offset, limit=limit)

    async def listar_propias(self, usuario: dict, *, offset: int, limit: int) -> dict:
        if usuario["rol"] != RolUsuario.RESIDENTE:
            denegar("Solo el residente puede consultar sus reportes.")
        consulta = select(Incidencia).where(
            Incidencia.condominio_id == contexto_consulta(usuario),
            reportes_propios(usuario),
        )
        return await self._paginar(consulta, offset=offset, limit=limit)

    async def _paginar(
        self, consulta: Select[tuple[Incidencia]], *, offset: int, limit: int
    ) -> dict:
        registros = (
            await self.session.scalars(
                consulta.order_by(Incidencia.creado_en.desc(), Incidencia.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        return {"items": registros[:limit], "hay_mas": len(registros) > limit}

    async def revisar(
        self, usuario: dict, incidencia_id: UUID, revision: RevisarIncidencia
    ) -> Incidencia:
        cid = contexto_junta(usuario)
        identidad = SQLAlchemyUsuariosRepository(self.session)
        if await identidad.contexto(cid, bloquear=True) is None:
            denegar()
        vigente = await validar_sesion(usuario, identidad)

        incidencia = await self.session.scalar(
            select(Incidencia)
            .where(Incidencia.id == incidencia_id, Incidencia.condominio_id == cid)
            .with_for_update()
        )
        if incidencia is None:
            raise APIError(404, "INCIDENCIA_NO_ENCONTRADA", "La incidencia no está disponible.")
        if incidencia.estado != "REGISTRADO":
            raise APIError(
                409, "INCIDENCIA_NO_EDITABLE", "La incidencia ya no está disponible para revisión."
            )
        if incidencia.version != revision.version:
            raise APIError(
                409, "VERSION_DESACTUALIZADA", "El reporte cambió. Consulta la última versión."
            )

        anterior = estado_revision(incidencia)
        if isinstance(revision, RechazarIncidencia):
            incidencia.estado = "RECHAZADO"
            incidencia.motivo_rechazo = revision.motivo
            accion, motivo = "RECHAZO_TICKET_INCIDENCIA", revision.motivo
        else:
            if (
                incidencia.categoria_confirmada == revision.categoria
                and incidencia.prioridad == revision.prioridad
            ):
                return incidencia
            incidencia.categoria_confirmada = revision.categoria
            incidencia.prioridad = revision.prioridad
            accion, motivo = "CLASIFICACION_TICKET_INCIDENCIA", "REVISION_JUNTA"

        incidencia.version += 1
        await SQLAlchemyPagosRepository(self.session).auditar(
            vigente,
            cid,
            incidencia.departamento_id,
            accion,
            motivo,
            anterior,
            estado_revision(incidencia),
        )
        await self.session.commit()
        return incidencia

    async def asignar(
        self,
        usuario: dict,
        incidencia_id: UUID,
        solicitud: AsignarIncidencia,
        clave: UUID,
    ) -> tuple[Incidencia, AsignacionIncidencia, int, bool]:
        cid = contexto_junta(usuario)
        identidad = SQLAlchemyUsuariosRepository(self.session)
        if await identidad.contexto(cid, bloquear=True) is None:
            denegar()
        vigente = await validar_sesion(usuario, identidad)

        incidencia = await self.session.scalar(
            select(Incidencia)
            .where(Incidencia.id == incidencia_id, Incidencia.condominio_id == cid)
            .with_for_update()
        )
        if incidencia is None:
            raise APIError(404, "INCIDENCIA_NO_ENCONTRADA", "La incidencia no está disponible.")

        huella = sha256(
            json.dumps(
                {**solicitud.model_dump(mode="json"), "incidencia_id": str(incidencia.id)},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        previa = await self.session.scalar(
            select(AsignacionIncidencia).where(
                AsignacionIncidencia.condominio_id == cid,
                AsignacionIncidencia.incidencia_id == incidencia.id,
                AsignacionIncidencia.clave_idempotencia == clave,
            )
        )
        if previa is not None:
            if previa.hash_solicitud != huella:
                raise APIError(
                    409, "CLAVE_IDEMPOTENCIA_REUTILIZADA", "La clave pertenece a otra asignación."
                )
            return incidencia, previa, await self._contar_avisos(previa), False

        if incidencia.estado not in ESTADOS_ASIGNABLES or not transicion_permitida(
            incidencia.estado, "ASIGNADO"
        ):
            raise APIError(
                409, "INCIDENCIA_NO_ASIGNABLE", "El ticket ya no admite una nueva asignación."
            )
        if incidencia.version != solicitud.version:
            raise APIError(
                409, "VERSION_DESACTUALIZADA", "El reporte cambió. Consulta la última versión."
            )
        if solicitud.plazo <= datetime.now(UTC):
            raise APIError(422, "PLAZO_INVALIDO", "El plazo debe ser una fecha futura.")

        if solicitud.responsable_usuario_id is not None:
            responsable = await identidad.por_id(solicitud.responsable_usuario_id)
            rol = await identidad.rol_usuario(solicitud.responsable_usuario_id, cid)
            if (
                responsable is None
                or not responsable.esta_activo
                or rol is None
                or not rol.es_activo
            ):
                raise APIError(
                    403,
                    "RESPONSABLE_NO_AUTORIZADO",
                    "El responsable no está activo en este condominio.",
                )

        anterior = estado_revision(incidencia)
        asignacion = AsignacionIncidencia(
            condominio_id=cid,
            incidencia_id=incidencia.id,
            reportante_id=incidencia.reportante_id,
            departamento_id=incidencia.departamento_id,
            actor_id=UUID(str(usuario["sub"])),
            clave_idempotencia=clave,
            hash_solicitud=huella,
            responsable_usuario_id=solicitud.responsable_usuario_id,
            responsable_proveedor_id=solicitud.responsable_proveedor_id,
            proveedor_nombre=solicitud.proveedor_nombre,
            correo_proveedor=solicitud.correo_proveedor,
            plazo=solicitud.plazo,
            nota=solicitud.nota,
        )
        self.session.add(asignacion)
        await self.session.flush()

        incidencia.estado = "ASIGNADO"
        incidencia.asignacion_actual_id = asignacion.id
        incidencia.responsable_usuario_id = asignacion.responsable_usuario_id
        incidencia.responsable_proveedor_id = asignacion.responsable_proveedor_id
        incidencia.proveedor_nombre = asignacion.proveedor_nombre
        incidencia.correo_proveedor = asignacion.correo_proveedor
        incidencia.fecha_asignacion = asignacion.creado_en or datetime.now(UTC)
        incidencia.plazo = asignacion.plazo
        incidencia.version += 1

        avisos = await self.encolar_avisos_asignacion(incidencia, asignacion)
        await SQLAlchemyPagosRepository(self.session).auditar(
            vigente,
            cid,
            incidencia.departamento_id,
            "ASIGNACION_TICKET_INCIDENCIA",
            "ASIGNACION_JUNTA",
            anterior,
            {
                **estado_revision(incidencia),
                "asignacion_id": str(asignacion.id),
                "avisos_encolados": avisos,
            },
        )
        await self.session.commit()
        return incidencia, asignacion, avisos, True

    async def encolar_avisos_asignacion(
        self, incidencia: Incidencia, asignacion: AsignacionIncidencia
    ) -> int:
        cid = incidencia.condominio_id
        identidad = SQLAlchemyUsuariosRepository(self.session)
        reportante = await identidad.por_id(incidencia.reportante_id)
        departamento = await identidad.departamento(cid, incidencia.departamento_id)
        condominio = await identidad.contexto(cid)
        if reportante is None or departamento is None or condominio is None:
            raise APIError(409, "ASIGNACION_SIN_CONTEXTO", "No se puede encolar el aviso.")

        enlace = urljoin(settings.ACTIVACION_WEB_URL, f"/incidencias/{incidencia.id}")
        cola = NotificacionesRepository(self.session)
        residente = clave_asignacion(asignacion.id, RolAvisoAsignacion.RESIDENTE)
        await cola.encolar(
            cid=cid,
            did=incidencia.departamento_id,
            usuario=reportante,
            contacto=reportante.email,
            evento=residente.evento_id,
            operacion=residente.operacion_id,
            tipo=AVISO_ASIGNACION_RESIDENTE,
            canal="EMAIL",
            contexto={
                "codigo_ticket": str(incidencia.id),
                "estado": "ASIGNADO",
                "enlace": enlace,
                "nombre": reportante.nombre,
                "dpto": departamento[0].numero,
            },
        )
        avisos = 1
        if asignacion.responsable_proveedor_id is not None and asignacion.correo_proveedor:
            proveedor = clave_asignacion(asignacion.id, RolAvisoAsignacion.PROVEEDOR)
            await cola.encolar(
                cid=cid,
                did=incidencia.departamento_id,
                usuario=None,
                contacto=asignacion.correo_proveedor,
                evento=proveedor.evento_id,
                operacion=proveedor.operacion_id,
                tipo=AVISO_ASIGNACION_PROVEEDOR,
                canal="EMAIL",
                externo=asignacion.responsable_proveedor_id,
                contexto={
                    "codigo_ticket": str(incidencia.id),
                    "proveedor": asignacion.proveedor_nombre,
                    "condominio": condominio.nombre,
                    "ubicacion": incidencia.ubicacion,
                    "categoria": incidencia.categoria_confirmada or incidencia.categoria,
                    "prioridad": incidencia.prioridad or incidencia.urgencia,
                    "descripcion": incidencia.descripcion,
                    "plazo": asignacion.plazo.astimezone(ZoneInfo("America/Lima")).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                },
            )
            avisos += 1
        return avisos

    async def _contar_avisos(self, asignacion: AsignacionIncidencia) -> int:
        return await self.session.scalar(
            select(func.count())
            .select_from(Notificacion)
            .where(
                Notificacion.evento_id == asignacion.id,
                Notificacion.tipo_evento.in_(
                    (AVISO_ASIGNACION_RESIDENTE, AVISO_ASIGNACION_PROVEEDOR)
                ),
            )
        )

    async def listar_avisos(
        self, usuario: dict, incidencia_id: UUID, *, offset: int, limit: int
    ) -> dict:
        cid = contexto_lectura(usuario)
        incidencia = await self.session.scalar(
            select(Incidencia.id).where(
                Incidencia.id == incidencia_id, Incidencia.condominio_id == cid
            )
        )
        if incidencia is None:
            raise APIError(404, "INCIDENCIA_NO_ENCONTRADA", "La incidencia no está disponible.")
        asignaciones = (
            await self.session.scalars(
                select(AsignacionIncidencia)
                .where(
                    AsignacionIncidencia.condominio_id == cid,
                    AsignacionIncidencia.incidencia_id == incidencia_id,
                )
                .order_by(AsignacionIncidencia.creado_en.desc(), AsignacionIncidencia.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        items: list[AvisoAsignacionDTO] = []
        for asignacion in asignaciones[:limit]:
            tipos = [
                (RolAvisoAsignacion.RESIDENTE, AVISO_ASIGNACION_RESIDENTE),
            ]
            if asignacion.responsable_proveedor_id is not None:
                tipos.append((RolAvisoAsignacion.PROVEEDOR, AVISO_ASIGNACION_PROVEEDOR))
            for rol, tipo in tipos:
                clave = clave_asignacion(asignacion.id, rol)
                aviso = await self.session.scalar(
                    select(Notificacion).where(
                        Notificacion.evento_id == clave.evento_id,
                        Notificacion.operacion_id == clave.operacion_id,
                        Notificacion.tipo_evento == tipo,
                    )
                )
                if aviso is None:
                    items.append(
                        AvisoAsignacionDTO(
                            asignacion_id=asignacion.id,
                            destinatario_tipo=rol.value,
                            estado="CONTACTO_FALTANTE",
                        )
                    )
                    continue
                alerta = await self.session.scalar(
                    select(AlertaNotificacion.id).where(
                        AlertaNotificacion.notificacion_id == aviso.id,
                        AlertaNotificacion.atendida_en.is_(None),
                    )
                )
                items.append(
                    AvisoAsignacionDTO(
                        asignacion_id=asignacion.id,
                        destinatario_tipo=rol.value,
                        estado=aviso.estado,
                        aviso_id=aviso.id,
                        intentos=aviso.intentos,
                        fecha_actualizacion=aviso.fecha_actualizacion,
                        alerta_abierta=alerta is not None,
                    )
                )
        return {"items": items, "hay_mas": len(asignaciones) > limit}

    async def consultar(
        self, usuario: dict, incidencia_id: UUID, *, incluir_evidencia: bool = False
    ) -> Incidencia:
        rol = usuario["rol"]
        if rol not in (RolUsuario.RESIDENTE, RolUsuario.ADMIN_JUNTA):
            denegar()
        query = select(Incidencia).where(
            Incidencia.id == incidencia_id,
            Incidencia.condominio_id == contexto_consulta(usuario),
        )
        if rol == RolUsuario.RESIDENTE:
            query = query.where(reportes_propios(usuario))
        if incluir_evidencia:
            query = query.options(undefer(Incidencia.evidencia))
        incidencia = await self.session.scalar(query)
        if incidencia is None:
            raise APIError(404, "INCIDENCIA_NO_ENCONTRADA", "La incidencia no está disponible.")
        return incidencia
