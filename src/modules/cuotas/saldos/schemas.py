"""Resultado inmutable del cálculo contable de crédito."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class ResultadoSaldoFavor:
    monto_aplicado: Decimal
    monto_pendiente: Decimal
    saldo_restante: Decimal
    estado: Literal["PAGADA", "PENDIENTE"]
