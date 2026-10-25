"""Condiciones por vínculo con locks y sesiones PostgreSQL independientes."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.core.errors import APIError
from src.modules.condominios.condiciones_pago import CondicionesPagoRequest, CondicionesPagoService
from src.modules.condominios.models import Departamento, Edificio
from src.modules.cuotas.distribucion.models import ConfiguracionDistribucion
from src.modules.cuotas.emision import EmisionCuotasService
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.cuotas.presupuestos.models import PresupuestoMensual
from src.modules.cuotas.saldos.service import ActorSaldoFavor
from src.modules.cuotas.schemas import EmitirLoteRequest
from src.modules.usuarios.models import UsuarioDepartamento

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


async def test_version_concurrente_y_sin_sobrescritura(db_usuarios):
    cid = UUID(db_usuarios.cid)
    async with db_usuarios.sessions() as db:
        vinculo = await db.scalar(
            select(UsuarioDepartamento)
            .join(Departamento, UsuarioDepartamento.departamento_id == Departamento.id)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .where(Edificio.condominio_id == cid, UsuarioDepartamento.es_activo.is_(True))
            .order_by(UsuarioDepartamento.id).limit(1)
        )
        did, vid = vinculo.departamento_id, vinculo.id
    actor = {"rol": "ADMIN_JUNTA", "sub": str(uuid4()), "condominio_id": str(cid)}

    async def cambiar(gracia):
        async with db_usuarios.sessions() as db:
            try:
                return await CondicionesPagoService(db).procesar(did, actor, CondicionesPagoRequest(
                    vinculo_responsable_id=vid, dias_gracia_override=gracia,
                    version_esperada=1, motivo="Prueba concurrente",
                ))
            except APIError as exc:
                return exc

    resultados = await asyncio.gather(cambiar(0), cambiar(5))
    assert sum(isinstance(r, APIError) and r.status_code == 409 for r in resultados) == 1
    async with db_usuarios.sessions() as db:
        actual = await CondicionesPagoService(db).procesar(did, actor)
    assert actual.version == 2 and actual.dias_gracia_efectivos in (0, 5)
    assert actual.vinculo_responsable_id == vid


async def test_rechaza_vinculo_de_otra_unidad(db_usuarios):
    async with db_usuarios.sessions() as db:
        vinculos = list(await db.scalars(
            select(UsuarioDepartamento).where(UsuarioDepartamento.es_activo.is_(True))
        ))
    primero = vinculos[0]
    otro = next(v for v in vinculos if v.departamento_id != primero.departamento_id)
    actor = {"rol": "SUPERADMIN", "sub": str(uuid4())}
    async with db_usuarios.sessions() as db:
        with pytest.raises(APIError) as exc:
            await CondicionesPagoService(db).procesar(primero.departamento_id, actor, CondicionesPagoRequest(
                vinculo_responsable_id=otro.id, dias_gracia_override=10,
                version_esperada=1, motivo="Cruce inválido",
            ))
        assert exc.value.error_code == "RESPONSABLE_INVALIDO"


async def test_emision_conserva_override_y_snapshot_tras_cambio(db_usuarios):
    cid, actor_id = UUID(db_usuarios.cid), str(uuid4())
    actor = {"rol": "SUPERADMIN", "sub": actor_id}
    async with db_usuarios.sessions() as db, db.begin():
        vinculo = await db.scalar(select(UsuarioDepartamento).where(
            UsuarioDepartamento.es_activo.is_(True)
        ).order_by(UsuarioDepartamento.id).limit(1))
        did, vid = vinculo.departamento_id, vinculo.id
        db.add(ConfiguracionDistribucion(condominio_id=cid, metodo="EQUITATIVA",
                                        actualizado_por=actor_id, actualizado_en=datetime.now(UTC)))
        db.add(PresupuestoMensual(condominio_id=cid, periodo="2026-10", moneda="PEN",
                                 monto_total=Decimal("1000.00"), fecha_vencimiento=datetime(2026, 10, 10).date(),
                                 estado="APROBADO", creado_por=actor_id, aprobado_por=actor_id,
                                 aprobado_en=datetime.now(UTC)))
    req = CondicionesPagoRequest(vinculo_responsable_id=vid, dias_gracia_override=0,
                                version_esperada=1, motivo="Excepción aprobada")
    async with db_usuarios.sessions() as db:
        await CondicionesPagoService(db).procesar(did, actor, req)
    async with db_usuarios.sessions() as db:
        await EmisionCuotasService(db).emitir(
            EmitirLoteRequest(condominio_id=cid, periodo="2026-10"),
            ActorSaldoFavor(actor_id, "SUPERADMIN", cid),
        )
    async with db_usuarios.sessions() as db:
        await CondicionesPagoService(db).procesar(did, actor, req.model_copy(update={
            "version_esperada": 2, "dias_gracia_override": 5,
        }))
    async with db_usuarios.sessions() as db:
        cuota = await db.scalar(select(CuotaMantenimiento).where(
            CuotaMantenimiento.departamento_id == did, CuotaMantenimiento.periodo == "2026-10"
        ))
        assert cuota.dias_gracia_aplicados == 0
        assert cuota.politica_mora_aplicada["dias_gracia"] == 0
        assert cuota.politica_mora_aplicada["responsable_vinculo_id"] == str(vid)
        assert cuota.politica_mora_aplicada["zona_horaria"] == "America/Lima"
