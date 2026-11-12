"""Alertas administrativas por fallos permanentes; sin contactos ni datos sensibles."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.modules.condominios.models import Departamento
from src.modules.notificaciones.models import AlertaNotificacion

MEDIOS = {
    "EMAIL": "correo",
    "WHATSAPP": "número de WhatsApp",
    "SMS": "teléfono",
    "PUSH": "dispositivo",
}
CANALES = {"EMAIL": "correo", "WHATSAPP": "WhatsApp", "SMS": "SMS", "PUSH": "notificación push"}


def mensaje_alerta(tipo, canal, numero):
    medio = MEDIOS.get(canal, "contacto")
    canal_txt = CANALES.get(canal, "el canal configurado")
    textos = {
        "ERROR_DEFINITIVO": (
            f"El {medio} del residente del Dpto. {numero} rebotó. Actualice los datos de contacto."
        ),
        "INTENTOS_AGOTADOS": (
            f"No se pudo entregar el aviso por {canal_txt} al Dpto. {numero} tras 4 intentos. "
            "Revise los datos de contacto y reenvíe."
        ),
        "ACEPTACION_INCIERTA": (
            f"No se pudo confirmar el envío por {canal_txt} al Dpto. {numero}. "
            "Verifique antes de reenviar."
        ),
        "DESTINATARIO_INVALIDO": (
            f"El {medio} del residente del Dpto. {numero} cambió o ya no está activo. "
            "Verifique los datos de contacto."
        ),
        "PROVEEDOR_NO_CONFIGURADO": (
            f"El proveedor de {canal_txt} no está configurado; el aviso al Dpto. {numero} "
            "no se envió. Contacte a soporte."
        ),
    }
    return textos[tipo]


async def crear_alerta(db, log, tipo, ahora=None):
    """Idempotente por (notificación, ciclo, tipo); se ejecuta en la transacción del fallo."""
    numero = await db.scalar(
        select(Departamento.numero).where(Departamento.id == log.departamento_id)
    )
    await db.execute(
        insert(AlertaNotificacion)
        .values(
            id=uuid4(),
            notificacion_id=log.id,
            condominio_id=log.condominio_id,
            departamento_id=log.departamento_id,
            ciclo=log.ciclo,
            tipo=tipo,
            mensaje=mensaje_alerta(tipo, log.canal, numero or "-"),
            creada_en=ahora or datetime.now(UTC),
        )
        .on_conflict_do_nothing(constraint="uq_alerta_notificacion_tipo")
    )
