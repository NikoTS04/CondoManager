"""Errores controlados del contrato interno de amortización."""

from typing import Any


class SaldoFavorError(Exception):
    error_code = "SALDO_FAVOR_ERROR"

    def __init__(self, mensaje: str, detalles: dict[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles


class DatosSaldoInvalidosError(SaldoFavorError):
    error_code = "DATOS_SALDO_INVALIDOS"


class CuotaNoAplicableError(SaldoFavorError):
    error_code = "CUOTA_NO_APLICABLE"


class AccesoSaldoDenegadoError(SaldoFavorError):
    error_code = "SALDO_ACCESO_DENEGADO"
