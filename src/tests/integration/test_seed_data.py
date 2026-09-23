from decimal import Decimal
from scripts.seed_condominio_piloto import (
    generar_datos_areas_comunes,
    generar_datos_departamentos,
)


def test_seed_dataset_departamentos_completo():
    """Valida que el dataset piloto contenga 139 departamentos con alícuotas sumando 100%."""
    deptos = generar_datos_departamentos()

    # 1. Total de unidades
    assert len(deptos) == 139

    # 2. Unicidad de numeración
    numeros = [d["numero"] for d in deptos]
    assert len(numeros) == len(set(numeros))

    # 3. Suma exacta de alícuotas
    suma_alicuotas = sum(d["coeficiente"] for d in deptos)
    assert suma_alicuotas == Decimal("100.0000")


def test_seed_dataset_casos_prototipo():
    """Valida los estados financieros iniciales de los casos de prueba en el dataset."""
    deptos_map = {d["numero"]: d for d in generar_datos_departamentos()}

    # Dpto 101: Residente regular al día
    assert deptos_map["101"]["estado_financiero"] == "AL_DIA"
    assert deptos_map["101"]["saldo_a_favor"] == Decimal("0.00")

    # Dpto 302: Residente con saldo a favor para pruebas de amortización automática
    assert deptos_map["302"]["saldo_a_favor"] == Decimal("200.00")

    # Dpto 402: Residente en mora para pruebas de bloqueo de reservas
    assert deptos_map["402"]["estado_financiero"] == "EN_MORA"

    # Dpto 504: Residente con voucher en revisión para pruebas de congelamiento de mora
    assert deptos_map["504"]["estado_financiero"] == "OBSERVADO"


def test_seed_dataset_areas_comunes():
    """Valida que se generen las 4 áreas comunes con aforos mayores a cero."""
    areas = generar_datos_areas_comunes()
    assert len(areas) == 4

    for area in areas:
        assert area["aforo_maximo"] > 0
        assert area["costo_reserva"] >= Decimal("0.00")
