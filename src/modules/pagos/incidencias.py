"""Destinos explícitos de comprobantes; el llamador posee locks y transacción."""

from sqlalchemy import select

from src.core.errors import APIError
from src.modules.incidencias.reparto_models import (
    CargoIncidencia,
    DestinoPagoIncidencia,
)
from src.shared.decimal_types import Decimal

CERO = Decimal("0.00")


async def seleccionar_cargos(session, ids, did, monto):
    cargos = list(
        await session.scalars(
            select(CargoIncidencia)
            .where(CargoIncidencia.id.in_(ids), CargoIncidencia.departamento_id == did)
            .order_by(CargoIncidencia.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if len(cargos) != len(ids) or any(c.pagado >= c.monto for c in cargos):
        raise APIError(
            409, "CARGOS_NO_DISPONIBLES", "Revise los cargos pendientes de su departamento."
        )
    if sum((c.monto - c.pagado for c in cargos), CERO) != monto:
        raise APIError(
            422, "TOTAL_CARGOS_INVALIDO", "El importe debe coincidir con los cargos elegidos."
        )
    return cargos


async def aplicar_cargos(session, comprobante):
    destinos = list(
        await session.scalars(
            select(DestinoPagoIncidencia)
            .where(DestinoPagoIncidencia.comprobante_id == comprobante.id)
            .order_by(DestinoPagoIncidencia.cargo_id)
        )
    )
    if {str(d.cargo_id) for d in destinos} != set(comprobante.cargos_incidencia_ids) or (
        sum((d.monto for d in destinos), CERO) != comprobante.monto
    ):
        raise APIError(409, "DESTINOS_INVALIDOS", "El comprobante no coincide con sus destinos.")
    cargos = await seleccionar_cargos(
        session,
        [d.cargo_id for d in destinos],
        comprobante.departamento_id,
        comprobante.monto,
    )
    importes = {d.cargo_id: d.monto for d in destinos}
    for cargo in cargos:
        if cargo.monto - cargo.pagado != importes[cargo.id]:
            raise APIError(409, "CARGO_YA_PAGADO", "Un cargo cambió; revise el comprobante.")
        cargo.pagado += importes[cargo.id]
    await session.flush()
    return comprobante.monto


async def pendiente_incidencias(session, did):
    from sqlalchemy import func

    return await session.scalar(
        select(func.coalesce(func.sum(CargoIncidencia.monto - CargoIncidencia.pagado), 0)).where(
            CargoIncidencia.departamento_id == did
        )
    )
