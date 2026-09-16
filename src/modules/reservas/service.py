"""Módulo de Reservas de Áreas Comunes (Asignado a: Brandon).

Contiene la validación cruzada obligatoria con el estado financiero del residente:
Si el departamento registra mora o deuda vencida fuera de gracia, la reserva es rechazada.
"""

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
        """Ciclo de Automatización:
        1. Evalúa Regla de Solvencia Financiera.
        2. Evalúa Disponibilidad de Horario.
        3. Decide Aprobación o Rechazo.
        """
        # Regla 1: Control de Solvencia Financiera (PROC-04)
        if deuda_vencida_departamento > Decimal("0.00"):
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: Su departamento mantiene cuotas vencidas pendientes en mora.",
                bloqueado_por_mora=True,
            )

        # Regla 2: Disponibilidad de Horario
        if not esta_horario_disponible:
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: El área común seleccionada ya se encuentra reservada en ese horario.",
                bloqueado_por_mora=False,
            )

        # Decisión y Acción: Confirmar Reserva
        return ResultadoReservaDTO(
            es_exitosa=True,
            reserva_id="res-mock-12345",
            motivo="Reserva confirmada exitosamente.",
            bloqueado_por_mora=False,
        )
