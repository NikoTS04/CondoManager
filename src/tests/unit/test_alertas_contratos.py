"""CON-50: evaluación pura de umbrales de 60 y 30 días."""

from datetime import date, timedelta

import pytest

from src.modules.alertas_contratos.evaluacion import evaluar_umbrales

FIN = date(2027, 3, 31)


def hoy_a(dias: int) -> date:
    return FIN - timedelta(days=dias)


def resumen(decisiones):
    return [(d.umbral_dias, d.estado, d.prioridad) for d in decisiones]


def test_a_60_dias_genera_el_aviso_informativo():
    assert resumen(evaluar_umbrales(FIN, hoy_a(60))) == [(60, "GENERADO", "INFORMATIVA")]


def test_antes_de_60_dias_no_genera_nada():
    assert evaluar_umbrales(FIN, hoy_a(61)) == []


def test_recuperacion_a_59_dias_genera_el_de_60_una_sola_vez():
    assert resumen(evaluar_umbrales(FIN, hoy_a(59))) == [(60, "GENERADO", "INFORMATIVA")]
    assert evaluar_umbrales(FIN, hoy_a(58), registrados=[60]) == []


def test_a_30_dias_con_el_de_60_ya_generado_solo_genera_el_prioritario():
    assert resumen(evaluar_umbrales(FIN, hoy_a(30), registrados=[60])) == [
        (30, "GENERADO", "PRIORITARIA")
    ]


def test_recuperacion_a_29_dias_genera_30_y_omite_60_por_prioridad():
    decisiones = evaluar_umbrales(FIN, hoy_a(29))
    assert resumen(decisiones) == [(60, "OMITIDO", "INFORMATIVA"), (30, "GENERADO", "PRIORITARIA")]
    omitido = decisiones[0]
    assert omitido.motivo == "OMITIDO_POR_PRIORIDAD"
    assert omitido.omitido_por_umbral == 30
    assert decisiones[1].omitido_por_umbral is None


def test_a_29_dias_con_el_de_60_registrado_no_vuelve_a_omitirlo():
    assert resumen(evaluar_umbrales(FIN, hoy_a(29), registrados=[60])) == [
        (30, "GENERADO", "PRIORITARIA")
    ]


def test_un_umbral_omitido_cuenta_como_registrado():
    assert evaluar_umbrales(FIN, hoy_a(20), registrados=[60, 30]) == []


def test_es_idempotente_con_todo_registrado_en_cualquier_dia():
    for dias in range(0, 61):
        assert evaluar_umbrales(FIN, hoy_a(dias), registrados=[60, 30]) == []


def test_el_dia_del_vencimiento_aun_genera_pendientes():
    assert resumen(evaluar_umbrales(FIN, FIN)) == [
        (60, "OMITIDO", "INFORMATIVA"),
        (30, "GENERADO", "PRIORITARIA"),
    ]


def test_contrato_vencido_no_genera_avisos():
    assert evaluar_umbrales(FIN, FIN + timedelta(days=1)) == []


def test_renovacion_inicia_su_propio_calendario():
    # La renovación no hereda lo registrado: el servicio consulta por (contrato, vigencia).
    nueva_fin = FIN + timedelta(days=365)
    assert resumen(evaluar_umbrales(nueva_fin, nueva_fin - timedelta(days=60))) == [
        (60, "GENERADO", "INFORMATIVA")
    ]
    assert evaluar_umbrales(nueva_fin, FIN - timedelta(days=29)) == []


@pytest.mark.parametrize("dias", [60, 59, 31, 30, 29, 1, 0])
def test_registra_los_dias_restantes_observados(dias):
    assert {d.dias_restantes for d in evaluar_umbrales(FIN, hoy_a(dias))} == {dias}
