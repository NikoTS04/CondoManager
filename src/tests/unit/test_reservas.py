from datetime import date, time
from decimal import Decimal
from src.modules.reservas.service import GestorReservasService, SolicitudReservaDTO


def test_rechazo_reserva_por_mora_activa():
    """Valida la invariante del Dominio 04 (Brandon): Si deuda_vencida > 0, se rechaza la reserva."""
    solicitud = SolicitudReservaDTO(
        condominio_id="vb3-condo",
        departamento_id="dpto-501",
        usuario_id="usr-moroso",
        area_id="area-parrilla-1",
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(19, 0),
        hora_fin=time(22, 0),
    )

    resultado = GestorReservasService.validar_y_procesar_reserva(
        solicitud=solicitud,
        deuda_vencida_departamento=Decimal("170.00"),
        esta_horario_disponible=True,
    )

    assert resultado.es_exitosa is False
    assert resultado.bloqueado_por_mora is True
    assert "mantiene cuotas vencidas pendientes" in resultado.motivo


def test_aprobacion_reserva_residente_al_dia():
    """Valida que un residente solvente en horario libre recibe confirmación de reserva."""
    solicitud = SolicitudReservaDTO(
        condominio_id="vb3-condo",
        departamento_id="dpto-102",
        usuario_id="usr-solvente",
        area_id="area-salon-eventos",
        fecha_reserva=date(2026, 11, 15),
        hora_inicio=time(16, 0),
        hora_fin=time(20, 0),
    )

    resultado = GestorReservasService.validar_y_procesar_reserva(
        solicitud=solicitud,
        deuda_vencida_departamento=Decimal("0.00"),
        esta_horario_disponible=True,
    )

    assert resultado.es_exitosa is True
    assert resultado.bloqueado_por_mora is False
    assert resultado.reserva_id is not None


def test_rechazo_reserva_por_conflicto_horario():
    """Valida que no se dupliquen reservas en un horario ya ocupado."""
    solicitud = SolicitudReservaDTO(
        condominio_id="vb3-condo",
        departamento_id="dpto-102",
        usuario_id="usr-solvente",
        area_id="area-parrilla-1",
        fecha_reserva=date(2026, 10, 31),
        hora_inicio=time(13, 0),
        hora_fin=time(17, 0),
    )

    resultado = GestorReservasService.validar_y_procesar_reserva(
        solicitud=solicitud,
        deuda_vencida_departamento=Decimal("0.00"),
        esta_horario_disponible=False,  # Ocupado
    )

    assert resultado.es_exitosa is False
    assert resultado.bloqueado_por_mora is False
    assert "ya se encuentra reservada" in resultado.motivo
