"""Transporte simulado determinista y textos de alerta, sin base de datos."""

from types import SimpleNamespace

import pytest

from src.modules.notificaciones.alertas import mensaje_alerta
from src.modules.notificaciones.models import TIPOS_ALERTA
from src.modules.notificaciones.worker import transporte_simulado


def log(destinatario, intentos):
    return SimpleNamespace(destinatario=destinatario, intentos=intentos)


@pytest.mark.parametrize(("intentos", "status"), [(1, 503), (2, 503), (3, 200), (4, 200)])
def test_falla_n_responde_503_mientras_intentos_no_superan_n(intentos, status):
    assert transporte_simulado(log("ana+falla2@ejemplo.test", intentos), "k")["status"] == status


def test_falla_1_se_recupera_en_el_segundo_intento():
    assert transporte_simulado(log("ana+falla1@ejemplo.test", 1), "k")["status"] == 503
    assert transporte_simulado(log("ana+falla1@ejemplo.test", 2), "k")["status"] == 200


@pytest.mark.parametrize("intentos", [1, 2, 3, 4])
def test_rebote_es_siempre_550(intentos):
    resultado = transporte_simulado(log("ana+rebote@ejemplo.test", intentos), "k")
    assert resultado["status"] == 550 and resultado["error"] == "550"


@pytest.mark.parametrize("destino", ["ana@ejemplo.test", "ana+otra@ejemplo.test", "+51999000111"])
def test_resto_de_destinos_responde_200_con_clave_estable(destino):
    assert transporte_simulado(log(destino, 1), "clave-1") == {
        "status": 200,
        "message_id": "simulado-clave-1",
    }


def test_mensajes_incluyen_departamento_y_no_contactos():
    for tipo in TIPOS_ALERTA:
        for canal in ("EMAIL", "WHATSAPP", "SMS", "PUSH"):
            texto = mensaje_alerta(tipo, canal, "402")
            assert "402" in texto and "@" not in texto
    assert mensaje_alerta("ERROR_DEFINITIVO", "EMAIL", "402") == (
        "El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."
    )
