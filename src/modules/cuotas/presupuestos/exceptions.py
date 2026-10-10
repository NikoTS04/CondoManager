"""Errores de negocio controlados del presupuesto mensual."""

from typing import Any
from uuid import UUID


class PresupuestoError(Exception):
    """Base para errores que el router convierte al contrato HTTP de CON-9."""

    error_code: str

    def __init__(self, mensaje: str, detalles: dict[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles


class AccesoPresupuestoDenegadoError(PresupuestoError):
    error_code = "PRESUPUESTO_ACCESO_DENEGADO"


class CondominioNoEncontradoError(PresupuestoError):
    error_code = "CONDOMINIO_NO_ENCONTRADO"

    def __init__(self, condominio_id: UUID) -> None:
        super().__init__(
            "No existe un condominio con el identificador solicitado.",
            {"condominio_id": str(condominio_id)},
        )


class PresupuestoNoEncontradoError(PresupuestoError):
    error_code = "PRESUPUESTO_NO_ENCONTRADO"


class PresupuestoPeriodoDuplicadoError(PresupuestoError):
    error_code = "PRESUPUESTO_PERIODO_DUPLICADO"


class PresupuestoNoEditableError(PresupuestoError):
    error_code = "PRESUPUESTO_NO_EDITABLE"


class DatosPresupuestoInvalidosError(PresupuestoError):
    error_code = "DATOS_PRESUPUESTO_INVALIDOS"
