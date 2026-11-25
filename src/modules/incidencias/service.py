"""Registro de incidencias y revisión administrativa con auditoría."""

import asyncio
import json
from hashlib import sha256
from urllib.parse import urljoin
from uuid import UUID

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
from src.modules.incidencias.models import Incidencia
from src.modules.incidencias.schemas import CrearIncidencia, RechazarIncidencia, RevisarIncidencia
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
    }


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
