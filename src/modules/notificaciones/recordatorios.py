"""CON-33: recordatorios de vencimiento por EMAIL.

Contrato:

- **Programación.** Una pasada diaria (desde `RECORDATORIO_HORA_LIMA`) selecciona por SQL las
  cuotas con saldo cuyo vencimiento cae entre hoy y hoy + `RECORDATORIO_DIAS_ANTICIPACION`
  (calendario de America/Lima). La ventana recupera días perdidos por un worker caído sin
  enviar jamás recordatorios de fechas ya vencidas.
- **Identidad estable.** `evento_id` = id de la cuota y `operacion_id` = uuid5(cuota,
  vencimiento). Con `uq_notificacion_logica` (evento, operación, destinatario, canal), dos
  workers, reintentos o reinicios producen un único mensaje lógico por cuota, fecha,
  destinatario y canal. Si la junta cambia el vencimiento, corresponde un recordatorio nuevo.
- **Elegibilidad al despachar.** El worker revalida la cuota con `FOR SHARE` inmediatamente
  antes del intento: una aprobación de pago en curso (que bloquea la cuota `FOR UPDATE`)
  termina primero y su resultado decide. Si la cuota ya no tiene saldo, la fila queda
  `SUPRIMIDO` con su motivo, sin tocar el transporte. Un voucher en revisión no modifica
  `monto_pagado`, por lo que no suprime el aviso.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.templates import PlantillasService
from src.modules.usuarios.models import Usuario

TIPO_RECORDATORIO = "NOTIF_RECORDATORIO_PREVIO"
LIMA = ZoneInfo("America/Lima")
# Espacio de nombres fijo: cambiarlo rompería la deduplicación de recordatorios ya encolados.
NS_RECORDATORIO = UUID("6f2f4f0e-3c5b-4f53-9a43-0c3a3b9e7d33")


def fecha_lima_de(ahora):
    return (ahora or datetime.now(UTC)).astimezone(LIMA).date()


def operacion_recordatorio(cuota_id, fecha_vencimiento):
    return uuid5(NS_RECORDATORIO, f"recordatorio-previo:{cuota_id}:{fecha_vencimiento.isoformat()}")


def _fecha(valor):
    return valor.strftime("%d/%m/%Y")


def contexto_recordatorio(usuario, departamento, condominio, cuota):
    gracia = (
        cuota.dias_gracia_aplicados
        if cuota.dias_gracia_aplicados is not None
        else condominio.dias_gracia
    )
    return {
        "nombre": usuario.nombre,
        "dpto": departamento.numero,
        "periodo": cuota.periodo,
        "fecha_corte": _fecha(cuota.fecha_vencimiento),
        "fecha_limite_mora": _fecha(cuota.fecha_vencimiento + timedelta(days=gracia)),
        "monto_pendiente": f"{cuota.monto_total_exigible - cuota.monto_pagado:.2f}",
        "moneda": "S/" if condominio.moneda == "PEN" else "USD",
    }


def _consulta_cuotas():
    return (
        select(CuotaMantenimiento, Departamento, Condominio)
        .join(Departamento, Departamento.id == CuotaMantenimiento.departamento_id)
        .join(Edificio, Edificio.id == Departamento.edificio_id)
        .join(Condominio, Condominio.id == Edificio.condominio_id)
    )


async def programar_recordatorios(session_factory=AsyncSessionLocal, ahora=None, dias=None):
    """Encola los recordatorios del día. Idempotente: devuelve cuántos mensajes nuevos creó."""
    hoy = fecha_lima_de(ahora)
    dias = settings.RECORDATORIO_DIAS_ANTICIPACION if dias is None else dias
    async with session_factory() as db, db.begin():
        repo = NotificacionesRepository(db)
        filas = (
            await db.execute(
                _consulta_cuotas()
                .where(
                    CuotaMantenimiento.fecha_vencimiento >= hoy,
                    CuotaMantenimiento.fecha_vencimiento <= hoy + timedelta(days=dias),
                    CuotaMantenimiento.monto_pagado < CuotaMantenimiento.monto_total_exigible,
                    Departamento.activo.is_(True),
                    Condominio.activo.is_(True),
                )
                .order_by(CuotaMantenimiento.id)
            )
        ).all()
        nuevos = 0
        for cuota, departamento, condominio in filas:
            operacion = operacion_recordatorio(cuota.id, cuota.fecha_vencimiento)
            for usuario, depto, contacto in await repo.destinatarios(
                condominio.id, departamento.id, "EMAIL"
            ):
                nuevo_id = uuid4()
                creado = await repo.encolar(
                    id=nuevo_id,
                    cid=condominio.id,
                    did=departamento.id,
                    usuario=usuario,
                    contacto=contacto,
                    evento=cuota.id,
                    operacion=operacion,
                    tipo=TIPO_RECORDATORIO,
                    canal="EMAIL",
                    contexto=contexto_recordatorio(usuario, depto, condominio, cuota),
                )
                nuevos += creado.id == nuevo_id
        return nuevos


async def motivo_supresion(db, log, ahora):
    """Revalida la cuota bajo `FOR SHARE`; devuelve el motivo para suprimir o None.

    Si sigue elegible, actualiza el cuerpo con el saldo vigente (un abono parcial posterior
    al encolado no debe anunciar el monto anterior).
    """
    fila = (
        await db.execute(
            _consulta_cuotas()
            .where(CuotaMantenimiento.id == log.evento_id)
            .with_for_update(read=True, of=CuotaMantenimiento)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if fila is None:
        return "SUPRIMIDO_CUOTA_INEXISTENTE"
    cuota, departamento, condominio = fila
    if operacion_recordatorio(cuota.id, cuota.fecha_vencimiento) != log.operacion_id:
        return "SUPRIMIDO_VENCIMIENTO_MODIFICADO"
    if cuota.fecha_vencimiento < fecha_lima_de(ahora):
        return "SUPRIMIDO_VENCIMIENTO_PASADO"
    if cuota.monto_pagado >= cuota.monto_total_exigible:
        return "SUPRIMIDO_CUOTA_PAGADA"
    if not (departamento.activo and condominio.activo):
        return "SUPRIMIDO_CONTEXTO_INACTIVO"
    usuario = await db.get(Usuario, log.usuario_destinatario_id)
    log.asunto, log.cuerpo = PlantillasService.renderizar(
        TIPO_RECORDATORIO, contexto_recordatorio(usuario, departamento, condominio, cuota)
    )
    return None


class ProgramadorDiario:
    """Ejecuta la programación una vez por fecha de Lima a partir de la hora configurada.

    El estado en memoria solo evita consultas repetidas; la deduplicación real está en SQL,
    por eso un reinicio o un segundo worker vuelven a programar sin duplicar.
    """

    def __init__(self, session_factory=AsyncSessionLocal):
        self.session_factory = session_factory
        self.ultima_fecha = None

    async def tick(self, ahora=None):
        if not settings.RECORDATORIOS_ACTIVOS:
            return None
        local = (ahora or datetime.now(UTC)).astimezone(LIMA)
        if local.hour < settings.RECORDATORIO_HORA_LIMA or self.ultima_fecha == local.date():
            return None
        nuevos = await programar_recordatorios(self.session_factory, ahora)
        self.ultima_fecha = local.date()
        return nuevos
