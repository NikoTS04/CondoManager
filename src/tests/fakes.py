"""Dobles de prueba compartidos por las verificaciones de integración."""

from uuid import UUID

from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio
from src.modules.cuotas.presupuestos.exceptions import PresupuestoPeriodoDuplicadoError
from src.modules.cuotas.presupuestos.models import PresupuestoMensual


class FakeCondominioRepository:
    def __init__(self) -> None:
        self.condominios: dict[UUID, Condominio] = {}
        self.auditorias: list[AuditoriaLogORM] = []

    async def agregar(self, condominio: Condominio, auditoria: AuditoriaLogORM) -> Condominio:
        self.condominios[condominio.id] = condominio
        self.auditorias.append(auditoria)
        return condominio

    async def obtener_por_id(self, condominio_id: UUID) -> Condominio | None:
        return self.condominios.get(condominio_id)


class FakePresupuestoRepository:
    """Persistencia en memoria con las mismas reglas observables que CON-9."""

    def __init__(self) -> None:
        self.condominios: dict[UUID, Condominio] = {}
        self.presupuestos: dict[UUID, PresupuestoMensual] = {}
        self.auditorias: list[AuditoriaLogORM] = []
        self.bloqueos_solicitados: list[UUID] = []

    async def obtener_condominio(self, condominio_id: UUID) -> Condominio | None:
        return self.condominios.get(condominio_id)

    async def obtener_por_id(
        self,
        presupuesto_id: UUID,
        condominio_id: UUID | None,
        *,
        bloquear: bool,
    ) -> PresupuestoMensual | None:
        if bloquear:
            self.bloqueos_solicitados.append(presupuesto_id)
        presupuesto = self.presupuestos.get(presupuesto_id)
        if presupuesto is None:
            return None
        if condominio_id is not None and presupuesto.condominio_id != condominio_id:
            return None
        return presupuesto

    async def obtener_por_condominio_periodo(
        self,
        condominio_id: UUID,
        periodo: str,
    ) -> PresupuestoMensual | None:
        return next(
            (
                presupuesto
                for presupuesto in self.presupuestos.values()
                if presupuesto.condominio_id == condominio_id
                and presupuesto.periodo == periodo
            ),
            None,
        )

    async def obtener_aprobado_por_periodo(
        self,
        condominio_id: UUID,
        periodo: str,
    ) -> PresupuestoMensual | None:
        presupuesto = await self.obtener_por_condominio_periodo(condominio_id, periodo)
        if presupuesto is None or presupuesto.estado != "APROBADO":
            return None
        return presupuesto

    async def obtener_ultimo_hash_auditoria(self, condominio_id: UUID) -> str | None:
        for auditoria in reversed(self.auditorias):
            if auditoria.condominio_id == condominio_id:
                return auditoria.hash_actual
        return None

    async def agregar(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual:
        self._asegurar_periodo_unico(presupuesto)
        self.presupuestos[presupuesto.id] = presupuesto
        self.auditorias.append(auditoria)
        return presupuesto

    async def guardar_cambio(
        self,
        presupuesto: PresupuestoMensual,
        auditoria: AuditoriaLogORM,
    ) -> PresupuestoMensual:
        self._asegurar_periodo_unico(presupuesto)
        self.presupuestos[presupuesto.id] = presupuesto
        self.auditorias.append(auditoria)
        return presupuesto

    def _asegurar_periodo_unico(self, candidato: PresupuestoMensual) -> None:
        duplicado = any(
            presupuesto.id != candidato.id
            and presupuesto.condominio_id == candidato.condominio_id
            and presupuesto.periodo == candidato.periodo
            for presupuesto in self.presupuestos.values()
        )
        if duplicado:
            raise PresupuestoPeriodoDuplicadoError(
                "Ya existe un presupuesto para el condominio y periodo indicados."
            )
