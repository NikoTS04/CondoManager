from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.cuotas.estado_cuenta import proyectar_cuenta
from src.modules.incidencias.reparto import ConfigurarReparto, distribuir
from src.modules.pagos.schemas import ReportarPagoRequest
from src.tests.unit.test_estado_cuenta import base, fila, pago

A, B, C = [UUID(int=i) for i in (1, 2, 3)]


def test_centavos_exactos_y_desempate_estable():
    pesos = {C: Decimal("1"), A: Decimal("1"), B: Decimal("1")}
    assert distribuir(Decimal("100.00"), pesos) == {
        A: Decimal("33.34"),
        B: Decimal("33.33"),
        C: Decimal("33.33"),
    }
    assert distribuir(Decimal("0.01"), pesos) == {A: Decimal("0.01"), B: 0, C: 0}


def test_alicuotas_se_normalizan_entre_seleccionados():
    assert distribuir(Decimal("100.01"), {A: Decimal("2.5000"), B: Decimal("7.5000")}) == {
        A: Decimal("25.00"),
        B: Decimal("75.01"),
    }


@pytest.mark.parametrize(
    "monto,pesos",
    [
        ("0.00", {A: Decimal("1")}),
        ("-1", {A: Decimal("1")}),
        ("0.001", {A: Decimal("1")}),
        ("NaN", {A: Decimal("1")}),
        ("1", {}),
        ("1", {A: Decimal("0")}),
        ("1", {A: Decimal("-1")}),
    ],
)
def test_no_distribuye_datos_invalidos(monto, pesos):
    with pytest.raises(APIError):
        distribuir(Decimal(monto), pesos)


@pytest.mark.parametrize(
    "alcance,ids",
    [
        ("TODOS", [A]),
        ("SELECCIONADOS", []),
        ("SELECCIONADOS", [A, A]),
    ],
)
def test_configuracion_exige_seleccion_coherente(alcance, ids):
    with pytest.raises(ValidationError):
        ConfigurarReparto(
            alcance=alcance,
            departamento_ids=ids,
            metodo="EQUITATIVA",
            concepto="Luminaria",
            motivo="Reparación aprobada",
        )


def test_reporte_rechaza_destinos_duplicados():
    with pytest.raises(ValidationError):
        ReportarPagoRequest(
            departamento_id=A,
            cargos_incidencia_ids=[A, A],
            banco="YAPE",
            numero_operacion="1",
            fecha_operacion="2026-11-25",
            monto="20.00",
        )


def test_cuenta_separa_cargo_de_cuota_sin_inventar_credito():
    b = base()
    reparto = fila(concepto="Reparación del portón")
    cargo = fila(reparto_id=reparto.id, monto=Decimal("25.00"), pagado=Decimal("25.00"))
    p = pago("25.00", cargos_incidencia_ids=[str(cargo.id)])
    b.update(
        cargos=[cargo],
        repartos=[reparto],
        pagos=[p],
        destinos=[
            fila(comprobante_id=p.id, cargo_id=cargo.id, monto=Decimal("25.00")),
        ],
    )
    resultado = proyectar_cuenta(**b)
    assert resultado["deuda_actual"] == "100.00"
    assert resultado["saldo_a_favor_actual"] == "0.00"
    assert resultado["cargos_periodo"] == "125.00"
    assert resultado["abonos_periodo"] == "25.00"
    assert any(m["tipo"] == "CARGO_INCIDENCIA" for m in resultado["movimientos"])


def test_cuenta_detecta_pago_de_cargo_sin_imputacion():
    b = base()
    reparto = fila(concepto="Portón")
    b.update(
        repartos=[reparto],
        cargos=[fila(reparto_id=reparto.id, monto=Decimal("25.00"), pagado=Decimal("25.00"))],
    )
    with pytest.raises(APIError):
        proyectar_cuenta(**b)
