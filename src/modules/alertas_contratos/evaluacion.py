"""Evaluación pura de umbrales de aviso; sin base de datos ni reloj."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

UMBRALES = (60, 30)
PRIORIDADES = {60: "INFORMATIVA", 30: "PRIORITARIA"}
MOTIVO_OMITIDO = "OMITIDO_POR_PRIORIDAD"
MOTIVO_GENERADO = "UMBRAL_ALCANZADO"

Estado = Literal["GENERADO", "OMITIDO"]


@dataclass(frozen=True)
class DecisionAviso:
    umbral_dias: int
    estado: Estado
    prioridad: str
    motivo: str
    dias_restantes: int
    omitido_por_umbral: int | None = None


def dias_restantes(fecha_fin: date, hoy: date) -> int:
    return (fecha_fin - hoy).days


def evaluar_umbrales(
    fecha_fin: date, hoy: date, registrados: Iterable[int] = ()
) -> list[DecisionAviso]:
    """Decide qué avisos generar u omitir para una vigencia.

    `registrados` son los umbrales que ya tienen aviso (generado u omitido) en esa vigencia.
    Un umbral está vencido si 0 <= días restantes <= umbral. Entre los pendientes se genera
    solo el de menor umbral y los de umbral mayor se omiten por prioridad.
    """
    dias = dias_restantes(fecha_fin, hoy)
    if dias < 0:
        return []
    ya = set(registrados)
    pendientes = sorted(u for u in UMBRALES if dias <= u and u not in ya)
    if not pendientes:
        return []
    prioritario, *omitidos = pendientes
    decisiones = [
        DecisionAviso(
            umbral_dias=prioritario,
            estado="GENERADO",
            prioridad=PRIORIDADES[prioritario],
            motivo=MOTIVO_GENERADO,
            dias_restantes=dias,
        )
    ]
    decisiones += [
        DecisionAviso(
            umbral_dias=umbral,
            estado="OMITIDO",
            prioridad=PRIORIDADES[umbral],
            motivo=MOTIVO_OMITIDO,
            dias_restantes=dias,
            omitido_por_umbral=prioritario,
        )
        for umbral in omitidos
    ]
    return sorted(decisiones, key=lambda d: -d.umbral_dias)
