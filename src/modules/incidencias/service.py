"""Registro idempotente de incidencias y aviso transaccional a Junta."""

import asyncio
import json
from hashlib import sha256
from urllib.parse import urljoin
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
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
from src.modules.incidencias.schemas import CrearIncidencia
from src.modules.notificaciones.repository import AVISO_INCIDENCIA, NotificacionesRepository
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.storage import VoucherStorage
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

MAX_EVIDENCIA = 3 * 1024 * 1024


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
            query = query.where(
                Incidencia.reportante_id == UUID(usuario["sub"]),
                Incidencia.departamento_id.in_([UUID(did) for did in vinculos_activos(usuario)]),
            )
        if incluir_evidencia:
            query = query.options(undefer(Incidencia.evidencia))
        incidencia = await self.session.scalar(query)
        if incidencia is None:
            raise APIError(404, "INCIDENCIA_NO_ENCONTRADA", "La incidencia no está disponible.")
        return incidencia
