"""Adaptador de los BDD iniciales; no implementa operaciones de producción."""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SolicitudReservaDTO(BaseModel):
    condominio_id: str
    departamento_id: str
    usuario_id: str
    area_id: str
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time


class ResultadoReservaDTO(BaseModel):
    es_exitosa: bool
    reserva_id: Optional[str] = None
    motivo: str
    bloqueado_por_mora: bool = False


class GestorReservasService:
    @staticmethod
    def validar_y_procesar_reserva(
        solicitud: SolicitudReservaDTO,
        deuda_vencida_departamento: Decimal,
        esta_horario_disponible: bool,
    ) -> ResultadoReservaDTO:
        if deuda_vencida_departamento > Decimal("0.00"):
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: Su departamento mantiene cuotas vencidas pendientes en mora.",
                bloqueado_por_mora=True,
            )
        if not esta_horario_disponible:
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: El área común seleccionada ya se encuentra reservada en ese horario.",
                bloqueado_por_mora=False,
            )
        return ResultadoReservaDTO(
            es_exitosa=True,
            reserva_id=f"res-{uuid.uuid4()}",
            motivo="Reserva confirmada exitosamente.",
            bloqueado_por_mora=False,
        )
