"""Callback autenticado; aceptación del servidor remoto no equivale a lectura."""

import json
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.errors import APIError
from src.modules.condominios.models import Condominio
from src.modules.notificaciones.alertas import crear_alerta
from src.modules.notificaciones.models import IntentoNotificacion, Notificacion
from src.modules.pagos.repository import SQLAlchemyPagosRepository

router = APIRouter()
basic = HTTPBasic(auto_error=False)


def autenticar(credencial: HTTPBasicCredentials | None = Depends(basic)):
    secreto = settings.MAILJET_WEBHOOK_SECRET.get_secret_value()
    if (
        len(secreto) < 32 or credencial is None
        or not secrets.compare_digest(credencial.username.encode(), b"mailjet")
        or not secrets.compare_digest(credencial.password.encode(), secreto.encode())
    ):
        raise APIError(401, "CALLBACK_NO_AUTORIZADO", "Se requiere credencial del proveedor.")


class EventoMailjet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event: str = Field(max_length=30)
    MessageID: int = Field(gt=0, strict=True)
    CustomID: str = Field(default="", max_length=100)
    email: str = Field(max_length=320)


async def aplicar_evento(evento, session_factory=AsyncSessionLocal):
    if evento.event not in {"sent", "bounce", "blocked", "spam"}:
        return
    try:
        identificador, ciclo, numero = evento.CustomID.rsplit("-", 2)
        nid, ciclo, numero = UUID(identificador), int(ciclo), int(numero)
    except (ValueError, AttributeError):
        return
    async with session_factory() as db, db.begin():
        cid = await db.scalar(select(Notificacion.condominio_id).where(Notificacion.id == nid))
        if cid is None:
            return
        # Orden común de locks con las operaciones administrativas y su cadena de auditoría.
        await db.scalar(select(Condominio).where(Condominio.id == cid).with_for_update())
        log = await db.scalar(select(Notificacion).where(Notificacion.id == nid).with_for_update())
        intento = await db.scalar(select(IntentoNotificacion).where(
            IntentoNotificacion.notificacion_id == nid,
            IntentoNotificacion.ciclo == ciclo, IntentoNotificacion.numero == numero,
        ).with_for_update())
        if (
            intento is None or log.transporte != "PROVEEDOR" or log.canal != "EMAIL"
            or log.destinatario != evento.email or log.ciclo != ciclo or log.intentos != numero
            or (intento.proveedor_message_id and intento.proveedor_message_id != str(evento.MessageID))
        ):
            return
        if evento.event == "sent" and log.estado == "FALLIDO_PERMANENTE" and not (
            log.error_mensaje or ""
        ).startswith("ACEPTACION_INCIERTA"):
            return
        nuevo = "ENTREGADO" if evento.event == "sent" else "FALLIDO_PERMANENTE"
        error = None if evento.event == "sent" else "MAILJET_" + evento.event.upper()
        if log.estado == nuevo and log.error_mensaje == error:
            return
        anterior = {"estado": log.estado, "ciclo": log.ciclo}
        ahora = datetime.now(UTC)
        intento.terminado_en = ahora
        intento.proveedor_message_id = log.proveedor_message_id = str(evento.MessageID)
        intento.error = log.error_mensaje = error
        log.estado = nuevo
        log.proximo_reintento = log.bloqueado_hasta = None
        log.fecha_actualizacion = ahora
        if error:
            await crear_alerta(db, log, "ERROR_DEFINITIVO", ahora)
        await SQLAlchemyPagosRepository(db).auditar(
            {"rol": "SISTEMA_AUTOMATICO", "sub": "MAILJET_CALLBACK"},
            cid, log.departamento_id, "NOTIFICACION_RESULTADO_MAILJET",
            evento.event.upper(), anterior, {"estado": nuevo, "ciclo": log.ciclo},
        )


@router.post("/notificaciones/mailjet/eventos", dependencies=[Depends(autenticar)])
async def callback(request: Request):
    cuerpo = bytearray()
    async for fragmento in request.stream():
        cuerpo.extend(fragmento)
        if len(cuerpo) > 65536:
            raise APIError(413, "CALLBACK_DEMASIADO_GRANDE", "Máximo 64 KiB.")
    try:
        datos = json.loads(cuerpo)
        datos = datos if isinstance(datos, list) else [datos]
        if not 1 <= len(datos) <= 100:
            raise ValueError
        eventos = [EventoMailjet.model_validate(d) for d in datos]
    except (ValueError, TypeError, ValidationError):
        raise APIError(422, "CALLBACK_INVALIDO", "Formato de evento inválido.") from None
    for evento in eventos:
        await aplicar_evento(evento)
    return {"estado": "RECIBIDO"}
