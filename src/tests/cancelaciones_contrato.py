"""Adaptador exclusivamente de pruebas para contratos históricos sin PostgreSQL."""

from src.core.authorization import autorizar_departamento
from src.core.errors import APIError
from src.modules.reservas.service import CancelacionInvalidaException, ReservasService


class CancelacionesContrato:
    def __init__(self):
        self.resultados = {}

    async def historial(self, cid, actor, area_id=None, fecha=None):
        return []

    async def cancelar(self, rid, request, actor, piloto=None):
        if piloto is None:
            raise APIError(404, "RESERVA_NO_ENCONTRADA", "Reserva no encontrada.")
        autorizar_departamento(
            actor, piloto["departamento_id"], piloto["condominio_id"], escritura=True
        )
        if rid in self.resultados:
            return self.resultados[rid]
        try:
            resultado, _ = ReservasService.procesar_cancelacion(piloto, request, actor=actor)
        except CancelacionInvalidaException as exc:
            # Conserva el formato de las pruebas históricas de autorización.
            from fastapi import HTTPException

            raise HTTPException(422, detail={"error_code": exc.error_code}) from exc
        self.resultados[rid] = resultado
        return resultado
