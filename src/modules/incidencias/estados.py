"""Transiciones permitidas del ciclo de vida de una incidencia (CON-53 a CON-57)."""

from types import MappingProxyType

_TRANSICIONES = {
    "REGISTRADO": frozenset({"RECHAZADO", "ASIGNADO"}),
    "RECHAZADO": frozenset(),
    "ASIGNADO": frozenset({"ASIGNADO", "EN_PROCESO"}),
    "EN_PROCESO": frozenset({"EN_PROCESO", "RESUELTO"}),
    "RESUELTO": frozenset({"CERRADO", "EN_PROCESO"}),
    "CERRADO": frozenset(),
}

TRANSICIONES = MappingProxyType(_TRANSICIONES)
ESTADOS = frozenset(_TRANSICIONES)
ESTADOS_ASIGNABLES = frozenset({"REGISTRADO", "ASIGNADO"})


def transicion_permitida(actual: str, destino: str) -> bool:
    return destino in TRANSICIONES.get(actual, frozenset())
