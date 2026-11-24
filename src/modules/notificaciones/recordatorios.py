"""Cursor durable por condominio, sin inventar campañas previas a su activación."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.models import PoliticaNotificaciones
from src.modules.notificaciones.repository import NotificacionesRepository


async def generar_recordatorios(session_factory=AsyncSessionLocal, ahora=None):
    local = (ahora or datetime.now(UTC)).astimezone(ZoneInfo("America/Lima"))
    if not settings.MAILJET_ENABLED:
        return
    async with session_factory() as db:
        ids = list(await db.scalars(select(Condominio.id).where(Condominio.activo.is_(True))))
    for cid in ids:
        async with session_factory() as db, db.begin():
            condominio = await db.scalar(
                select(Condominio).where(Condominio.id == cid, Condominio.activo.is_(True)).with_for_update()
            )
            if condominio is None:
                continue
            await db.execute(insert(PoliticaNotificaciones).values(
                condominio_id=cid, dias=[3, 0], hora=8, habilitado=True,
            ).on_conflict_do_nothing())
            politica = await db.get(PoliticaNotificaciones, cid)
            if not politica.habilitado:
                continue
            limite = local.date() if local.hour >= politica.hora else local.date() - timedelta(days=1)
            if politica.ultima_fecha is None:
                politica.ultima_fecha = local.date() - timedelta(days=1)
            dia = politica.ultima_fecha + timedelta(days=1)
            repo = NotificacionesRepository(db)
            # Lotes acotados; el cursor no salta los días que queden pendientes.
            for _ in range(31):
                if dia > limite:
                    break
                cuotas = list(await db.scalars(
                    select(CuotaMantenimiento)
                    .join(Departamento).join(Edificio)
                    .where(
                        Edificio.condominio_id == cid, Departamento.activo.is_(True),
                        CuotaMantenimiento.fecha_vencimiento.in_(
                            [dia + timedelta(days=d) for d in politica.dias]
                        ),
                        CuotaMantenimiento.monto_total_exigible > CuotaMantenimiento.monto_pagado,
                    )
                ))
                for cuota in cuotas:
                    dias = (cuota.fecha_vencimiento - dia).days
                    tipo = "NOTIF_CORTE_HOY" if dias == 0 else "NOTIF_RECORDATORIO_PREVIO"
                    evento = uuid5(NAMESPACE_URL, f"condomanager:{cuota.id}:{cuota.fecha_vencimiento}:{dias}")
                    for usuario, departamento, contacto in await repo.destinatarios(cid, cuota.departamento_id):
                        await repo.encolar(
                            cid=cid, did=departamento.id, usuario=usuario, contacto=contacto,
                            evento=evento, operacion=cuota.id, tipo=tipo, canal="EMAIL",
                            recordatorio_vencimiento=cuota.fecha_vencimiento, recordatorio_dias=dias,
                            contexto={
                                "nombre": usuario.nombre, "dpto": departamento.numero,
                                "fecha_corte": cuota.fecha_vencimiento.isoformat(),
                                "monto_pendiente": f"{cuota.monto_pendiente:.2f}",
                                "moneda": condominio.moneda,
                            },
                        )
                politica.ultima_fecha = dia
                dia += timedelta(days=1)
