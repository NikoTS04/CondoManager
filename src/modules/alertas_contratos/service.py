"""Revisión diaria de contratos: genera, omite y audita avisos por vigencia."""

import logging
from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.core.database import AsyncSessionLocal
from src.modules.alertas_contratos.contratos import FuenteContratos, obtener_fuente_contratos
from src.modules.alertas_contratos.evaluacion import evaluar_umbrales
from src.modules.alertas_contratos.models import AvisoContrato
from src.modules.condominios.models import Condominio
from src.modules.pagos.repository import SQLAlchemyPagosRepository

logger = logging.getLogger(__name__)

ACTOR = {"sub": "ALERTAS_CONTRATOS_WORKER", "rol": "SISTEMA_AUTOMATICO"}
ACCION = "ALERTA_VENCIMIENTO_CONTRATO"
DESTINATARIO = "ADMIN_JUNTA"


async def evaluar_contratos(
    fuente: FuenteContratos | None = None,
    session_factory=AsyncSessionLocal,
    hoy: date | None = None,
    estricto: bool = False,
) -> dict:
    """Idempotente: repetir la ejecución no duplica avisos ni auditorías."""
    fuente = fuente or obtener_fuente_contratos()
    hoy = hoy or datetime.now(UTC).date()
    async with session_factory() as db:
        contratos = list(await fuente.contratos_vigentes(db))
    por_condominio = defaultdict(list)
    for contrato in contratos:
        por_condominio[contrato.condominio_id].append(contrato)
    resumen = {"generados": 0, "omitidos": 0}
    for cid in sorted(por_condominio):
        try:
            async with session_factory() as db, db.begin():
                # El lock de condominio también serializa la cadena de auditoría.
                condominio = await db.scalar(
                    select(Condominio)
                    .where(Condominio.id == cid, Condominio.activo.is_(True))
                    .with_for_update()
                )
                if condominio is None:
                    continue
                for contrato in sorted(por_condominio[cid], key=lambda c: str(c.id)):
                    await _evaluar_contrato(db, contrato, hoy, resumen)
        except Exception:
            if estricto:
                raise
            logger.exception("Alertas de contratos pendientes: condominio=%s", cid)
    return resumen


async def _evaluar_contrato(db, contrato, hoy, resumen):
    cid = contrato.condominio_id
    vigencia = str(contrato.vigencia)
    registrados = list(
        await db.scalars(
            select(AvisoContrato.umbral_dias).where(
                AvisoContrato.contrato_id == contrato.id, AvisoContrato.vigencia == vigencia
            )
        )
    )
    auditor = SQLAlchemyPagosRepository(db)
    for decision in evaluar_umbrales(contrato.fecha_fin, hoy, registrados):
        creado = await db.scalar(
            insert(AvisoContrato)
            .values(
                condominio_id=cid,
                contrato_id=contrato.id,
                vigencia=vigencia,
                umbral_dias=decision.umbral_dias,
                estado=decision.estado,
                prioridad=decision.prioridad,
                destinatario_rol=DESTINATARIO,
                fecha_fin=contrato.fecha_fin,
                dias_restantes=decision.dias_restantes,
                motivo=decision.motivo,
                omitido_por_umbral=decision.omitido_por_umbral,
                fecha_evaluacion=hoy,
            )
            .on_conflict_do_nothing(constraint="uq_aviso_contrato_umbral")
            .returning(AvisoContrato.id)
        )
        if creado is None:
            continue
        resumen["generados" if decision.estado == "GENERADO" else "omitidos"] += 1
        await auditor.auditar(
            ACTOR,
            cid,
            None,
            ACCION,
            decision.motivo,
            {},
            {
                "aviso_id": str(creado),
                "contrato_id": str(contrato.id),
                "vigencia": vigencia,
                "umbral_dias": decision.umbral_dias,
                "estado": decision.estado,
                "prioridad": decision.prioridad,
                "destinatario_rol": DESTINATARIO,
                "fecha_fin": contrato.fecha_fin.isoformat(),
                "dias_restantes": decision.dias_restantes,
                "omitido_por_umbral": decision.omitido_por_umbral,
                "fecha_evaluacion": hoy.isoformat(),
            },
        )
