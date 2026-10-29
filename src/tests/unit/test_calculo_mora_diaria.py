from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from src.core.errors import APIError
from src.modules.pagos.calculo_diario import CuotaCalculo, reconstruir


def cuota(**cambios):
    datos = dict(
        id=UUID(int=1),
        periodo="2026-10",
        fecha_emision=date(2026, 10, 1),
        fecha_vencimiento=date(2026, 10, 10),
        monto_total_exigible=Decimal("100.00"),
        monto_extraordinario=Decimal("0.00"),
        monto_mora=Decimal("0.00"),
        monto_pagado=Decimal("0.00"),
        politica_mora_aplicada={
            "modalidad": "MONTO_DIARIO",
            "monto_diario": "1.00",
            "dias_gracia": 0,
            "zona_horaria": "America/Lima",
            "version": 1,
        },
    )
    return CuotaCalculo(**(datos | cambios))


def pago(dia, importe, id=10):
    return SimpleNamespace(
        id=UUID(int=id), fecha_operacion=date(2026, 10, dia), monto=Decimal(importe)
    )


@pytest.mark.parametrize("dia,esperado", [(10, "0.00"), (11, "1.00"), (15, "5.00")])
def test_calendario_y_entradas_inmutables(dia, esperado):
    c = cuota()
    anterior = deepcopy(c)
    r = reconstruir([c], [], date(2026, 10, dia))
    assert r["cuotas"][c.id]["mora"] == Decimal(esperado)
    assert c == anterior


def test_por_cuota_y_gracia_historica():
    a = cuota()
    b = cuota(
        id=UUID(int=2),
        politica_mora_aplicada=a.politica_mora_aplicada
        | {"dias_gracia": 2, "monto_diario": "2.50"},
    )
    r = reconstruir([a, b], [], date(2026, 10, 15))
    assert r["cuotas"][a.id]["mora"] == Decimal("5.00")
    assert r["cuotas"][b.id]["mora"] == Decimal("7.50")
    assert len(r["devengos"]) == 8


def test_no_devenga_antes_de_emision_ni_reconstruye_legacy():
    a = cuota(fecha_emision=date(2026, 10, 14))
    b = cuota(id=UUID(int=2), politica_mora_aplicada=None)
    r = reconstruir([a, b], [], date(2026, 10, 15))
    assert len(r["devengos"]) == 2
    assert r["cuotas"][b.id]["mora"] == 0


@pytest.mark.parametrize("p,esperado", [(pago(10, "100.00"), "0.00"), (pago(12, "102.00"), "2.00")])
def test_dia_bancario_inclusivo_y_cese_al_pagar_principal(p, esperado):
    c = cuota()
    r = reconstruir([c], [p], date(2026, 11, 30))
    assert r["cuotas"][c.id]["mora"] == Decimal(esperado)
    assert r["cuotas"][c.id]["total"] == r["cuotas"][c.id]["pagado"]


def test_pago_parcial_no_reduce_cargo_fijo_ni_capitaliza():
    c = cuota()
    r = reconstruir([c], [pago(12, "50.00")], date(2026, 10, 20))
    assert r["cuotas"][c.id] == {
        "mora": Decimal("10.00"),
        "total": Decimal("110.00"),
        "pagado": Decimal("50.00"),
    }
    assert r["movimientos"][UUID(int=10), c.id, "MORA"] == Decimal("2.00")
    assert r["movimientos"][UUID(int=10), c.id, "ORDINARIA"] == Decimal("48.00")


def test_retroactivo_reordena_imputaciones_y_devengos():
    c = cuota()
    temprano, tardio = pago(10, "100.00", 11), pago(12, "50.00", 12)
    a = reconstruir([c], [tardio, temprano], date(2026, 10, 25))
    b = reconstruir([c], [temprano, tardio], date(2026, 10, 25))
    assert a == b
    assert not a["devengos"]
    assert a["movimientos"][tardio.id, None, "CREDITO"] == Decimal("50.00")


def test_empates_fecha_por_uuid_no_por_orden_de_aprobacion():
    c = cuota()
    primero, segundo = pago(10, "100.00", 11), pago(10, "100.00", 12)
    r = reconstruir([c], [segundo, primero], date(2026, 10, 25))
    assert r["movimientos"][primero.id, c.id, "ORDINARIA"] == Decimal("100.00")
    assert r["movimientos"][segundo.id, None, "CREDITO"] == Decimal("100.00")


def test_credito_no_se_reimputa_a_cuotas_emitidas_despues_del_pago():
    c = cuota(fecha_emision=date(2026, 10, 15))
    p = pago(10, "100.00")
    r = reconstruir([c], [p], date(2026, 10, 20))
    assert r["movimientos"][p.id, None, "CREDITO"] == Decimal("100.00")
    assert r["cuotas"][c.id]["pagado"] == 0


def test_pausa_solo_limita_devengos_no_extingue_principal():
    c = cuota()
    r = reconstruir([c], [], date(2026, 10, 20), {c.id: date(2026, 10, 12)})
    assert len(r["devengos"]) == 2 and r["cuotas"][c.id]["pagado"] == 0


@pytest.mark.parametrize(
    "cambios",
    [
        {"monto_diario": "NaN"},
        {"monto_diario": "0.00"},
        {"monto_diario": "1.001"},
        {"dias_gracia": True},
        {"zona_horaria": "UTC"},
        {"monto_diario": None},
    ],
)
def test_snapshot_invalido_se_bloquea(cambios):
    c = cuota()
    c.politica_mora_aplicada.update(cambios)
    with pytest.raises(APIError, match="política histórica"):
        reconstruir([c], [], date(2026, 10, 15))


def test_fecha_futura_y_overflow_no_producen_plan():
    with pytest.raises(APIError) as exc:
        reconstruir([cuota()], [pago(20, "10.00")], date(2026, 10, 19))
    assert exc.value.error_code == "FECHA_BANCARIA_FUTURA"
    c = cuota(monto_total_exigible=Decimal("9999999999.99"))
    with pytest.raises(APIError) as exc:
        reconstruir([c], [], date(2026, 10, 11))
    assert exc.value.error_code == "MORA_FUERA_DE_RANGO"
