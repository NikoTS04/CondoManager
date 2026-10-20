"""Errores controlados de la distribución de cuotas."""

from typing import Any


class DistribucionError(Exception):
    error_code: str

    def __init__(self, mensaje: str, detalles: dict[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles


class AccesoDistribucionDenegadoError(DistribucionError):
    error_code = "DISTRIBUCION_ACCESO_DENEGADO"


class CondominioNoEncontradoError(DistribucionError):
    error_code = "CONDOMINIO_NO_ENCONTRADO"


class DistribucionNoEncontradaError(DistribucionError):
    error_code = "DISTRIBUCION_NO_CONFIGURADA"


class SinDepartamentosError(DistribucionError):
    error_code = "DISTRIBUCION_SIN_DEPARTAMENTOS"


class CoeficientesInvalidosError(DistribucionError):
    error_code = "DISTRIBUCION_COEFICIENTES_INVALIDOS"


class DatosDistribucionInvalidosError(DistribucionError):
    error_code = "DATOS_DISTRIBUCION_INVALIDOS"
