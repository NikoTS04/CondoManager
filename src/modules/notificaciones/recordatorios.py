"""Recordatorios del día: claves deterministas, sin recuperar días históricos."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.notificaciones.repository import NotificacionesRepository


async def generar_recordatorios(session_factory=AsyncSessionLocal, ahora=None):
    local = (ahora or datetime.now(UTC)).astimezone(ZoneInfo("America/Lima"))
    if not settings.MAILJET_ENABLED or local.hour < 8:
        return
    async with session_factory() as db, db.begin():
        cuotas = (
            await db.execute(
                select(CuotaMantenimiento, Condominio)
                .join(Departamento, Departamento.id == CuotaMantenimiento.departamento_id)
                .join(Edificio, Edificio.id == Departamento.edificio_id)
                .join(Condominio, Condominio.id == Edificio.condominio_id)
                .where(
                    Condominio.activo.is_(True),
                    Departamento.activo.is_(True),
                    CuotaMantenimiento.fecha_vencimiento.in_(
                        [local.date(), local.date() + timedelta(days=3)]
                    ),
                    CuotaMantenimiento.monto_total_exigible > CuotaMantenimiento.monto_pagado,
                )
            )
        ).all()
        repo = NotificacionesRepository(db)
        for cuota, condominio in cuotas:
            tipo = (
                "NOTIF_CORTE_HOY" if cuota.fecha_vencimiento == local.date()
                else "NOTIF_RECORDATORIO_PREVIO"
            )
            evento = uuid5(NAMESPACE_URL, f"condomanager:{cuota.id}:{tipo}")
            for usuario, departamento, contacto in await repo.destinatarios(
                condominio.id, cuota.departamento_id
            ):
                await repo.encolar(
                    cid=condominio.id, did=departamento.id, usuario=usuario,
                    contacto=contacto, evento=evento, operacion=cuota.id, tipo=tipo,
                    canal="EMAIL", contexto={
                        "nombre": usuario.nombre, "dpto": departamento.numero,
                        "fecha_corte": cuota.fecha_vencimiento.isoformat(),
                        "monto_pendiente": f"{cuota.monto_pendiente:.2f}",
                        "moneda": condominio.moneda,
                    },
                )
