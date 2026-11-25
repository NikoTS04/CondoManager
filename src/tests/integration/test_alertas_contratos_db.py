"""CON-50 sobre PostgreSQL: recuperación a 59/29 días, renovación y dos condominios."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.models_audit import AuditoriaLogORM
from src.modules.alertas_contratos.models import AvisoContrato
from src.modules.alertas_contratos.service import evaluar_contratos
from src.tests.integration.test_alta_usuarios_db import otro_condominio

pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]

FIN = date(2027, 3, 31)


class FuenteFalsa:
    def __init__(self, *contratos):
        self.contratos = list(contratos)

    async def contratos_vigentes(self, db):
        return self.contratos


def contrato(cid, fin=FIN, vigencia="1", id=None):
    return SimpleNamespace(
        id=id or uuid4(), condominio_id=UUID(str(cid)), fecha_fin=fin, vigencia=vigencia
    )


def hoy_a(dias, fin=FIN):
    return fin - timedelta(days=dias)


async def ejecutar(base, fuente, hoy):
    return await evaluar_contratos(fuente, session_factory=base.sessions, hoy=hoy, estricto=True)


async def avisos(base, contrato_id):
    async with base.sessions() as db:
        filas = await db.scalars(
            select(AvisoContrato)
            .where(AvisoContrato.contrato_id == contrato_id)
            .order_by(AvisoContrato.vigencia, AvisoContrato.umbral_dias.desc())
        )
        return [(f.vigencia, f.umbral_dias, f.estado, f.omitido_por_umbral) for f in filas]


async def auditorias(base):
    async with base.sessions() as db:
        return await db.scalar(
            select(func.count()).where(
                AuditoriaLogORM.accion_ejecutada == "ALERTA_VENCIMIENTO_CONTRATO"
            )
        )


async def test_recuperacion_a_59_dias_genera_el_de_60_una_sola_vez(api_usuarios):
    _, base = api_usuarios
    c = contrato(base.cid)
    fuente = FuenteFalsa(c)
    assert await ejecutar(base, fuente, hoy_a(59)) == {"generados": 1, "omitidos": 0}
    assert await ejecutar(base, fuente, hoy_a(58)) == {"generados": 0, "omitidos": 0}
    assert await avisos(base, c.id) == [("1", 60, "GENERADO", None)]
    assert await auditorias(base) == 1


async def test_recuperacion_a_29_dias_omite_el_de_60_por_prioridad(api_usuarios):
    _, base = api_usuarios
    c = contrato(base.cid)
    fuente = FuenteFalsa(c)
    assert await ejecutar(base, fuente, hoy_a(29)) == {"generados": 1, "omitidos": 1}
    assert await ejecutar(base, fuente, hoy_a(29)) == {"generados": 0, "omitidos": 0}
    assert await avisos(base, c.id) == [("1", 60, "OMITIDO", 30), ("1", 30, "GENERADO", None)]
    assert await auditorias(base) == 2
    async with base.sessions() as db:
        log = await db.scalar(
            select(AuditoriaLogORM).where(
                AuditoriaLogORM.accion_ejecutada == "ALERTA_VENCIMIENTO_CONTRATO",
                AuditoriaLogORM.estado_posterior["umbral_dias"].astext == "30",
            )
        )
        assert log.actor_tipo == "SISTEMA_AUTOMATICO"
        assert log.resultado == "EXITOSO"
        assert log.estado_posterior["prioridad"] == "PRIORITARIA"
        assert log.estado_posterior["destinatario_rol"] == "ADMIN_JUNTA"


async def test_renovacion_inicia_su_calendario_y_conserva_el_historial(api_usuarios):
    _, base = api_usuarios
    original = contrato(base.cid)
    await ejecutar(base, FuenteFalsa(original), hoy_a(60))
    nueva_fin = FIN + timedelta(days=365)
    renovado = contrato(base.cid, fin=nueva_fin, vigencia="2", id=original.id)
    assert await ejecutar(base, FuenteFalsa(renovado), hoy_a(29)) == {"generados": 0, "omitidos": 0}
    assert await ejecutar(base, FuenteFalsa(renovado), hoy_a(60, nueva_fin)) == {
        "generados": 1,
        "omitidos": 0,
    }
    assert await avisos(base, original.id) == [
        ("1", 60, "GENERADO", None),
        ("2", 60, "GENERADO", None),
    ]


async def test_dos_condominios_reciben_sus_propios_avisos(api_usuarios):
    _, base = api_usuarios
    otro = await otro_condominio(base)
    mio, ajeno = contrato(base.cid), contrato(otro)
    resultado = await ejecutar(base, FuenteFalsa(mio, ajeno), hoy_a(30))
    assert resultado == {"generados": 2, "omitidos": 2}
    async with base.sessions() as db:
        filas = (
            await db.execute(select(AvisoContrato.contrato_id, AvisoContrato.condominio_id))
        ).all()
    assert {(c, k) for c, k in filas} == {
        (mio.id, mio.condominio_id),
        (ajeno.id, ajeno.condominio_id),
    }
