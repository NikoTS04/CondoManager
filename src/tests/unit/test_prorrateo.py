from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.cuotas.presupuestos.schemas import CrearPresupuestoRequest
from src.modules.cuotas.prorrateo import calcular_prorrateo
from src.modules.cuotas.prorrateo_schemas import ItemPresupuesto


def padron():
    edificios = [SimpleNamespace(id=UUID(int=i + 1), nombre_bloque=f"Edificio {i + 1}", total_pisos=p)
                 for i, p in enumerate((14, 14, 10, 10))]
    departamentos = [SimpleNamespace(id=UUID(int=1000 + i * 200 + n), edificio_id=e.id,
                                    numero=str(n), coeficiente_participacion=Decimal("1.0000"))
                     for i, e in enumerate(edificios) for n in range(1, 140 if i == 0 else 2)]
    concepto = SimpleNamespace(id=uuid4(), activo=True, codigo="MAN-01", categoria="MANTENIMIENTO_PREVENTIVO", descripcion="Ascensores")
    return edificios, departamentos, {concepto.id: concepto}


def item(concepto, **cambios):
    return ItemPresupuesto(concepto_id=next(iter(concepto)), seccion="AACC", **({"monto_periodo": "4800.00"} | cambios))


def test_pisos_exactos_y_139_unidades():
    edificios, departamentos, conceptos = padron()
    snapshot = calcular_prorrateo([item(conceptos)], edificios, departamentos, conceptos)
    asignaciones = snapshot["items"][0]["asignaciones"]
    assert [a["monto"] for a in asignaciones] == ["1400.00", "1400.00", "1000.00", "1000.00"]
    assert asignaciones[0]["unidades"] == 139
    assert sum(map(Decimal, snapshot["cuotas"].values())) == Decimal("4800.00")


def test_directo_y_cierre_individual_no_reparte_a_otras_torres():
    edificios, departamentos, conceptos = padron()
    snapshot = calcular_prorrateo([item(conceptos, monto_periodo="500.00", metodo_asignacion="DIRECTO_EDIFICIO", edificio_id=edificios[0].id)], edificios, departamentos, conceptos)
    cargos = snapshot["items"][0]["asignaciones"][0]["cuotas"]
    assert sum(c["monto"] == "3.60" for c in cargos) == 99
    assert sum(c["monto"] == "3.59" for c in cargos) == 40
    assert snapshot["cuotas"][str(departamentos[-1].id)] == "0.00"
    assert sum(Decimal(c["ajuste"]) for c in cargos) == Decimal("-0.40")


def test_abono_compensa_exactamente_y_neto_cero():
    edificios, departamentos, conceptos = padron()
    snapshot = calcular_prorrateo([item(conceptos), item(conceptos, tipo_movimiento="ABONO")], edificios, departamentos, conceptos)
    assert snapshot["monto_total"] == "0.00"
    assert all(Decimal(v) == 0 for v in snapshot["cuotas"].values())


def test_abono_que_crea_cuota_negativa_se_rechaza():
    edificios, departamentos, conceptos = padron()
    with pytest.raises(APIError) as exc:
        calcular_prorrateo([item(conceptos), item(conceptos, monto_periodo="1500.00", tipo_movimiento="ABONO", metodo_asignacion="DIRECTO_EDIFICIO", edificio_id=edificios[0].id)], edificios, departamentos, conceptos)
    assert exc.value.error_code == "CUOTA_NEGATIVA"


def test_concepto_inactivo_o_ajeno_y_edificio_ajeno():
    edificios, departamentos, conceptos = padron()
    for request in (ItemPresupuesto(concepto_id=uuid4(), seccion="AACC", monto_periodo="1.00"),
                    item(conceptos, metodo_asignacion="DIRECTO_EDIFICIO", edificio_id=uuid4())):
        with pytest.raises(APIError):
            calcular_prorrateo([request], edificios, departamentos, conceptos)
    next(iter(conceptos.values())).activo = False
    with pytest.raises(APIError):
        calcular_prorrateo([item(conceptos)], edificios, departamentos, conceptos)


@pytest.mark.parametrize("valor", [1.0, "1.001", "NaN", "-1.00", "10000000000.00"])
def test_dinero_en_limite_externo(valor):
    with pytest.raises(ValidationError):
        ItemPresupuesto(concepto_id=uuid4(), seccion="AACC", monto_periodo=valor)


def test_no_permite_cobertura_ficticia_ni_asignacion_sin_sustento():
    for cambios in ({"monto_cubierto_moras": "1.00"}, {"metodo_asignacion": "ASIGNACION_EXPLICITA", "asignaciones_explicitas": {uuid4(): "2.00"}}, {"numero_cuota": 2, "total_cuotas": 1}):
        with pytest.raises(ValidationError):
            ItemPresupuesto(concepto_id=uuid4(), seccion="AACC", monto_periodo="2.00", **cambios)


def test_asignacion_explicita_y_coeficientes_locales():
    edificios, departamentos, conceptos = padron()
    request = item(conceptos, monto_periodo="1.00", metodo_asignacion="ASIGNACION_EXPLICITA",
                   asignaciones_explicitas={edificios[0].id: "1.00"}, motivo_asignacion="Acta",
                   referencia_documento="Acta 01", metodo_unitario="POR_ALICUOTA")
    snapshot = calcular_prorrateo([request], edificios, departamentos, conceptos)
    assert sum(map(Decimal, snapshot["cuotas"].values())) == Decimal("1.00")


def test_total_servidor_no_acepta_control_inconsistente_ni_ids_repetidos():
    id = uuid4()
    datos = {"condominio_id": uuid4(), "periodo": "2026-10", "moneda": "PEN", "fecha_vencimiento": "2026-10-10"}
    linea = {"id": id, "concepto_id": uuid4(), "seccion": "AACC", "monto_periodo": "2.00"}
    assert CrearPresupuestoRequest(**datos, items=[linea]).monto_total == Decimal("2.00")
    with pytest.raises(ValidationError):
        CrearPresupuestoRequest(**datos, items=[linea], monto_total="3.00")
    with pytest.raises(ValidationError):
        CrearPresupuestoRequest(**datos, items=[linea, linea])


@pytest.mark.parametrize("texto", ["Dato\x00privado", "Descripción\x01inválida"])
def test_textos_exportables_sin_controles_xml(texto):
    with pytest.raises(ValidationError):
        ItemPresupuesto(concepto_id=uuid4(), seccion="AACC", monto_periodo="1.00", descripcion=texto)
