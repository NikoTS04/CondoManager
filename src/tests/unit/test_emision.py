"""Invariantes del cierre contable y contrato público de CON-11."""

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.modules.cuotas.emision import cerrar_centavos
from src.modules.cuotas.schemas import EmitirLoteRequest


@pytest.mark.parametrize(
    "cantidad,total,individual",
    [
        (3, "100.00", "33.33"),
        (3, "0.02", "0.01"),
        (139, "0.70", "0.01"),
        (139, "0.01", "0.00"),
        (139, "20850.00", "150.00"),
    ],
)
def test_cierre_exacto_no_negativo_determinista(cantidad, total, individual):
    montos = {UUID(int=i + 1): Decimal(individual) for i in range(cantidad)}
    resultado = cerrar_centavos(montos, Decimal(total))
    assert sum(resultado.values()) == Decimal(total)
    assert min(resultado.values()) >= 0
    assert resultado == cerrar_centavos(dict(reversed(list(montos.items()))), Decimal(total))
    assert set(montos.values()) == {Decimal(individual)}


@pytest.mark.parametrize("periodo", ["2026-00", "2026-13", "0000-10", "26-10", "2026-1"])
def test_rechaza_periodo_invalido(periodo):
    with pytest.raises(ValidationError):
        EmitirLoteRequest(condominio_id=UUID(int=1), periodo=periodo)


def test_cliente_no_puede_sustituir_presupuesto():
    with pytest.raises(ValidationError):
        EmitirLoteRequest(condominio_id=UUID(int=1), periodo="2026-10", presupuesto_total="1.00")
