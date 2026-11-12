"""CON-14: invariantes monetarias, fechas y proyección sin doble contabilización."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace as N
from uuid import uuid4

import pytest

from src.core.errors import APIError
from src.modules.cuotas.estado_cuenta import EstadoCuentaResponse, proyectar_cuenta, rango_consulta

AHORA = datetime(2026, 10, 20, 15, tzinfo=UTC)


def fila(**datos):
    return N(**{"id": uuid4(), "creado_en": AHORA, **datos})


def base(**overrides):
    cuota = fila(
        periodo="2026-10",
        monto_total_exigible=Decimal("100.00"),
        monto_pagado=Decimal("0.00"),
        fecha_emision=date(2026, 10, 1),
        fecha_vencimiento=date(2026, 10, 10),
        dias_gracia_aplicados=0,
        estado="EN_MORA",
    )
    return {
        "depto": fila(saldo_a_favor=Decimal("0.00")),
        "condominio": fila(moneda="PEN", dias_gracia=0),
        "cuotas": [cuota],
        "pagos": [],
        "imputaciones": [],
        "gestionados": set(),
        "devengos": [],
        "ajustes": [],
        "distribuciones": [],
        "aplicaciones": [],
        "desde": date(2026, 10, 1),
        "hasta": date(2026, 10, 31),
        "hoy": date(2026, 10, 20),
        **overrides,
    }


def pago(monto, **extras):
    return fila(
        monto=Decimal(monto),
        estado="APROBADO",
        conciliado_en=AHORA,
        fecha_operacion=date(2026, 10, 10),
        **extras,
    )


def test_parcial_excedente_y_revision_separados():
    b = base()
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("100.00")
    b["depto"].saldo_a_favor = Decimal("20.00")
    p1, p2 = pago("40.00"), pago("80.00")
    pendiente = fila(
        monto=Decimal("999.99"),
        estado="EN_REVISION",
        banco_origen="BCP",
        numero_operacion="REVISION",
        fecha_operacion=date(2026, 10, 15),
    )
    b["pagos"] = [p1, p2, pendiente]
    b["imputaciones"] = [
        fila(comprobante_id=p.id, cuota_id=c.id, monto_aplicado=Decimal(m))
        for p, m in ((p1, "40.00"), (p2, "60.00"))
    ]
    data = EstadoCuentaResponse.model_validate(proyectar_cuenta(**b))
    assert data.cargos_periodo == "100.00" and data.abonos_periodo == "120.00"
    assert data.saldo_final == "-20.00" and data.deuda_actual == "0.00"
    assert data.saldo_a_favor_actual == "20.00" and not data.base_historica_sin_fecha
    assert data.pagos_en_revision[0].monto == "999.99"


def test_credito_consumido_no_se_cuenta_como_otro_ingreso():
    b = base()
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("30.00")
    b["aplicaciones"] = [fila(cuota_id=c.id, monto_aplicado=Decimal("30.00"))]
    data = proyectar_cuenta(**b)
    assert data["credito_inicial_sin_desglose"] == "30.00"
    assert data["saldo_inicial"] == "-30.00" and data["saldo_final"] == "70.00"
    assert data["abonos_periodo"] == "0.00"
    [detalle] = [m for m in data["movimientos"] if m["tipo"] == "APLICACION_CREDITO"]
    assert detalle["importe"] == "30.00" and detalle["abono"] == "0.00"


def test_retroactivo_conserva_devengo_y_compensaciones_sin_duplicar_recibo():
    b = base()
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("100.00")
    b["depto"].saldo_a_favor = Decimal("50.00")
    p1, p2 = pago("50.00"), pago("100.00")
    b["pagos"], b["gestionados"] = [p1, p2], {p1.id, p2.id}
    d = fila(cuota_id=c.id, importe=Decimal("10.00"), fecha_local=date(2026, 10, 11))
    b["devengos"] = [d]
    b["ajustes"] = [fila(devengo_id=d.id, importe=Decimal("-10.00"), comprobante_causante_id=p2.id)]
    b["distribuciones"] = [
        fila(comprobante_id=p.id, cuota_id=cid, componente=comp, importe=Decimal(m))
        for p, cid, comp, m in (
            (p1, c.id, "MORA", "10.00"),
            (p1, c.id, "ORDINARIA", "40.00"),
            (p1, c.id, "MORA", "-10.00"),
            (p1, c.id, "ORDINARIA", "-40.00"),
            (p1, None, "CREDITO", "50.00"),
            (p2, c.id, "ORDINARIA", "100.00"),
        )
    ]
    # Los recibos iniciales también existen, pero no son la imputación diaria vigente.
    b["imputaciones"] = [fila(comprobante_id=p1.id, cuota_id=c.id, monto_aplicado=Decimal("50.00"))]
    data = proyectar_cuenta(**b)
    assert data["saldo_final"] == "-50.00" and not data["base_historica_sin_fecha"]
    assert {m["tipo"] for m in data["movimientos"]} >= {"DEVENGO_MORA", "AJUSTE_MORA"}
    assert sum(m["tipo"] == "PAGO_APROBADO" for m in data["movimientos"]) == 2
    assert len([m for m in data["movimientos"] if m["tipo"] == "DISTRIBUCION_PAGO"]) == 6


def test_paginacion_y_rango_no_recortan_los_saldos():
    b = base(desde=date(2026, 10, 20), limite=1)
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("40.00")
    p = pago("40.00")
    b["pagos"] = [p]
    b["imputaciones"] = [fila(comprobante_id=p.id, cuota_id=c.id, monto_aplicado=p.monto)]
    primero = proyectar_cuenta(**b)
    siguiente = proyectar_cuenta(**{**b, "offset": 1})
    assert primero["saldo_inicial"] == "100.00" and primero["saldo_final"] == "60.00"
    assert siguiente["saldo_final"] == "60.00" and siguiente["movimientos"] == []


def test_base_anterior_se_declara_y_no_se_inventa_un_pago():
    b = base()
    b["depto"].saldo_a_favor = Decimal("25.00")
    b["cuotas"][0].monto_pagado = Decimal("10.00")
    data = proyectar_cuenta(**b)
    assert data["base_historica_sin_fecha"] and data["saldo_base_historico"] == "-35.00"
    assert data["saldo_final"] == "65.00" and len(data["movimientos"]) == 1


def test_no_cuadra_un_historial_inconsistente_con_un_ajuste_inventado():
    b = base()
    b["pagos"] = [pago("100.00")]
    with pytest.raises(APIError) as e:
        proyectar_cuenta(**b)
    assert e.value.status_code == 409 and e.value.error_code == "ESTADO_CUENTA_INCONSISTENTE"


def test_registro_utc_se_filtra_por_fecha_local_lima():
    b = base(desde=date(2026, 10, 19), hasta=date(2026, 10, 19))
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("40.00")
    p = pago("40.00")
    p.conciliado_en = datetime(2026, 10, 20, 2, tzinfo=UTC)
    b["pagos"] = [p]
    b["imputaciones"] = [fila(comprobante_id=p.id, cuota_id=c.id, monto_aplicado=p.monto)]
    data = proyectar_cuenta(**b)
    assert data["abonos_periodo"] == "40.00" and data["movimientos"][0]["fecha"] == date(
        2026, 10, 19
    )


@pytest.mark.parametrize(
    "desde,hasta",
    [
        (None, date(2026, 1, 1)),
        (date(2026, 2, 2), date(2026, 2, 1)),
        (date(2025, 1, 1), date(2026, 12, 31)),
    ],
)
def test_rango_incompleto_invertido_o_excesivo(desde, hasta):
    with pytest.raises(APIError):
        rango_consulta(desde, hasta, date(2026, 2, 1))


def test_mes_predeterminado_usa_calendario_y_ultimo_dia():
    assert rango_consulta(None, None, date(2028, 2, 15)) == (date(2028, 2, 1), date(2028, 2, 29))


def test_totales_que_cuadran_no_ocultan_imputaciones_erroneas_por_pago():
    b = base()
    c = b["cuotas"][0]
    c.monto_pagado = Decimal("100.00")
    p1, p2 = pago("50.00"), pago("50.00")
    b["pagos"], b["gestionados"] = [p1, p2], {p1.id, p2.id}
    b["distribuciones"] = [
        fila(comprobante_id=p.id, cuota_id=c.id, componente="ORDINARIA", importe=Decimal(m))
        for p, m in ((p1, "60.00"), (p2, "40.00"))
    ]
    with pytest.raises(APIError) as e:
        proyectar_cuenta(**b)
    assert e.value.status_code == 409


def test_compensacion_no_puede_dejar_credito_neto_negativo():
    b = base()
    c = b["cuotas"][0]
    c.monto_total_exigible = c.monto_pagado = Decimal("110.00")
    p = pago("100.00")
    b["pagos"], b["gestionados"] = [p], {p.id}
    b["distribuciones"] = [
        fila(comprobante_id=p.id, cuota_id=c.id, componente="ORDINARIA", importe=Decimal("110.00")),
        fila(comprobante_id=p.id, cuota_id=None, componente="CREDITO", importe=Decimal("-10.00")),
    ]
    with pytest.raises(APIError):
        proyectar_cuenta(**b)
