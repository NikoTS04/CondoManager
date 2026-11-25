"""Interfaz mínima que CON-50 necesita del módulo de contratos (CON-48/CON-49).

CON-49 aún no existe. En lugar de acoplar CON-50 a una tabla inexistente, se declara aquí
el contrato que la fuente de contratos debe cumplir. Cuando CON-49 exista, bastará una
implementación de `FuenteContratos` que lea sus contratos con vigencia activa.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class ContratoVigente(Protocol):
    """Una vigencia activa de un contrato. Una renovación cambia `vigencia` y `fecha_fin`."""

    @property
    def id(self) -> UUID: ...

    @property
    def condominio_id(self) -> UUID: ...

    @property
    def fecha_fin(self) -> date: ...

    @property
    def vigencia(self) -> str: ...


class FuenteContratos(Protocol):
    async def contratos_vigentes(self, db: AsyncSession) -> Sequence[ContratoVigente]: ...


class FuenteContratosVacia:
    """Marcador hasta que CON-49 aporte contratos: la revisión diaria no encuentra ninguno."""

    async def contratos_vigentes(self, db: AsyncSession) -> Sequence[ContratoVigente]:
        return []


def obtener_fuente_contratos() -> FuenteContratos:
    # TODO(CON-49): devolver la fuente respaldada por la tabla de contratos.
    return FuenteContratosVacia()
