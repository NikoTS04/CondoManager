"""Contrato de avisos de los flujos del Sprint 4 sobre la cola de notificaciones.

Solo fija tipos de plantilla y claves de deduplicación. No encola ni consulta la
base: cada productor (reservas, incidencias) la usa al llamar a
``NotificacionesRepository.encolar``. La unicidad lógica de la cola es
``(evento_id, operacion_id, usuario_destinatario_id, canal)``.
Véase ``specs/03-contracts/events/domain-events-catalog.md``.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

AVISO_INCIDENCIA_REGISTRADA = "NOTIF_INCIDENCIA_REGISTRADA"
AVISO_RESERVA_AFECTADA = "NOTIF_RESERVA_AFECTADA_BLOQUEO"
AVISO_ASIGNACION_RESIDENTE = "NOTIF_INCIDENCIA_ASIGNADA_RESIDENTE"
AVISO_ASIGNACION_PROVEEDOR = "NOTIF_INCIDENCIA_ASIGNADA_PROVEEDOR"

_NAMESPACE_AVISOS = uuid5(NAMESPACE_URL, "https://condomanager.local/avisos/sprint-4")


class RolAvisoAsignacion(StrEnum):
    RESIDENTE = "RESIDENTE"
    PROVEEDOR = "PROVEEDOR"


@dataclass(frozen=True)
class ClaveAviso:
    """Par ``(evento_id, operacion_id)`` de la cola; el destinatario completa la clave."""

    evento_id: UUID
    operacion_id: UUID


def clave_incidencia_registrada(incidencia_id: UUID) -> ClaveAviso:
    """CON-53: el ID de la incidencia identifica evento y operación (un aviso por Junta)."""
    return ClaveAviso(evento_id=incidencia_id, operacion_id=incidencia_id)


def clave_reserva_afectada(bloqueo_id: UUID, reserva_id: UUID) -> ClaveAviso:
    """CON-47: un aviso por reserva afectada; el bloqueo confirmado es el evento."""
    return ClaveAviso(evento_id=bloqueo_id, operacion_id=reserva_id)


def clave_asignacion(asignacion_id: UUID, rol: RolAvisoAsignacion | str) -> ClaveAviso:
    """CON-55: la asignación confirmada es el evento; cada rol tiene su operación.

    Reasignar crea otra asignación y por tanto otros avisos; repetir la
    confirmación de la misma asignación no duplica ninguno.
    """
    rol = RolAvisoAsignacion(rol)
    return ClaveAviso(
        evento_id=asignacion_id,
        operacion_id=uuid5(_NAMESPACE_AVISOS, f"{asignacion_id}:{rol.value}"),
    )
