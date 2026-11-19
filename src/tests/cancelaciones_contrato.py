"""Adaptador exclusivamente de pruebas para contratos históricos sin PostgreSQL."""

from src.core.authorization import autorizar_departamento, puede_ver_departamento
from src.core.errors import APIError
from src.modules.reservas.schemas import ReservaResponseDTO
from src.modules.reservas.service import CancelacionInvalidaException, ReservasService
<<<<<<< HEAD
from src.tests import reservas_contrato
=======
from src.tests.reservas_contrato import RESERVAS_REGISTRADAS
>>>>>>> origin/develop


class CancelacionesContrato:
    def __init__(self):
        self.resultados = {}

    async def historial(self, cid, actor, area_id=None, fecha=None):
        return [
<<<<<<< HEAD
            ReservaResponseDTO(**r)
            for r in reservas_contrato.RESERVAS_REGISTRADAS.values()
=======
            ReservaResponseDTO(**r) for r in RESERVAS_REGISTRADAS.values()
>>>>>>> origin/develop
            if r["condominio_id"] == cid
            and puede_ver_departamento(actor, r["departamento_id"])
            and (area_id is None or r["area_id"] == area_id)
            and (fecha is None or r["fecha_reserva"] == fecha)
        ]

    async def cancelar(self, rid, request, actor):
<<<<<<< HEAD
        piloto = reservas_contrato.RESERVAS_REGISTRADAS.get(rid)
=======
        piloto = RESERVAS_REGISTRADAS.get(rid)
>>>>>>> origin/develop
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
        piloto["estado"] = "CANCELADA"
        return resultado
