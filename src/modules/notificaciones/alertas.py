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


ORIGEN_CORREO = "CORREO"
ORIGEN_JOB = "JOB"
TIPO_JOB = "JOB_FALLO_DEFINITIVO"
REFERENCIA_MAX = 64


def ciclo_job(ahora):
    """Ciclo de un job: fecha UTC de la ejecución como entero AAAAMMDD."""
    return ahora.year * 10000 + ahora.month * 100 + ahora.day


async def _insertar(db, **valores):
    """Inserta de forma idempotente por (origen_tipo, origen_id, ciclo, tipo).

    Devuelve True si creó la alerta y False si ya existía.
    """
    referencia = valores.get("referencia_correlacion")
    if referencia is not None:
        valores["referencia_correlacion"] = referencia[:REFERENCIA_MAX]
    resultado = await db.execute(
        insert(AlertaNotificacion)
        .values(id=uuid4(), **valores)
        .on_conflict_do_nothing(constraint="uq_alerta_origen_tipo")
        .returning(AlertaNotificacion.id)
    )
    return resultado.scalar_one_or_none() is not None


async def crear_alerta(db, log, tipo, ahora=None, referencia_correlacion=None):
    """Alerta de correo, idempotente por (origen, ciclo, tipo); usa la transacción del fallo."""
    numero = await db.scalar(
        select(Departamento.numero).where(Departamento.id == log.departamento_id)
    )
    return await _insertar(
        db,
        notificacion_id=log.id,
        condominio_id=log.condominio_id,
        departamento_id=log.departamento_id,
        origen_tipo=ORIGEN_CORREO,
        origen_id=str(log.id),
        referencia_correlacion=referencia_correlacion,
        ciclo=log.ciclo,
        tipo=tipo,
        mensaje=(
            mensaje_alerta(tipo, log.canal, numero)
            if numero
            else f"Aviso de identidad: {tipo}. Revise el proveedor y la elegibilidad antes de reenviar."
        ),
        creada_en=ahora or datetime.now(UTC),
    )


def mensaje_alerta_job(nombre, intentos):
    return (
        f"El proceso programado «{nombre}» falló tras {intentos} "
        f"{'intento' if intentos == 1 else 'intentos'}. Revise el diagnóstico y ejecútelo de nuevo."
    )


async def crear_alerta_job(
    db, nombre, intentos, maximo_intentos, ahora=None, referencia_correlacion=None
):
    """Alerta de un job que agotó sus reintentos; no hace nada si aún le quedan.

    Idempotente por (JOB, nombre, ciclo AAAAMMDD, tipo). El job es transversal, así que la
    alerta no tiene condominio y no se lista en la consulta por condominio. El mensaje no
    incluye la causa técnica. Devuelve True solo si creó una alerta nueva.
    """
    if intentos < maximo_intentos:
        return False
    ahora = ahora or datetime.now(UTC)
    return await _insertar(
        db,
        notificacion_id=None,
        condominio_id=None,
        departamento_id=None,
        origen_tipo=ORIGEN_JOB,
        origen_id=nombre,
        referencia_correlacion=referencia_correlacion,
        ciclo=ciclo_job(ahora),
        tipo=TIPO_JOB,
        mensaje=mensaje_alerta_job(nombre, intentos),
        creada_en=ahora,
    )
