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


# ============================================================================
# Pruebas Avanzadas para ReservasService (SDD Completo - Brandon PROC-04)
# ============================================================================

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from src.modules.reservas.schemas import (
    CancelarReservaRequest,
    CrearReservaRequest,
)
from src.modules.reservas.service import (
    AreaInactivaException,
    CancelacionInvalidaException,
    ConflictoHorarioException,
    DeudaMoraActivaException,
    HorarioInvalidoException,
    ReservasService,
)


@pytest.fixture
def area_parrilla_fixture():
    return {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111101"),
        "condominio_id": uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        "nombre": "Zona de Parrilla 1 (Terraza)",
        "descripcion": "Parrilla acero inoxidable",
        "aforo_maximo": 12,
        "costo_reserva": Decimal("25.00"),
        "esta_activa": True,
    }


def test_reservas_service_rechazo_por_mora_activa(area_parrilla_fixture):
    """Valida que un departamento con saldo vencido en mora sea rechazado con 403 / DeudaMoraActivaException."""
    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(19, 0),
        hora_fin=time(22, 0),
    )

    with pytest.raises(DeudaMoraActivaException) as exc_info:
        ReservasService.procesar_reserva(
            request=req,
            area=area_parrilla_fixture,
            estado_financiero_depto="EN_MORA",
            saldo_mora_depto=Decimal("170.00"),
            reservas_existentes=[],
        )

    assert exc_info.value.error_code == "DEUDA_MORA_ACTIVA"
    assert exc_info.value.saldo_vencido == Decimal("170.00")
    assert "cuotas vencidas pendientes en mora" in exc_info.value.mensaje


def test_reservas_service_aprobacion_solvente_y_auditoria(area_parrilla_fixture):
    """Valida la reserva exitosa para residente al día con emisión de los 7 campos de auditoría."""
    depto_id = uuid.uuid4()
    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=depto_id,
        fecha_reserva=date(2026, 11, 15),
        hora_inicio=time(16, 0),
        hora_fin=time(20, 0),
    )

    reserva, audit = ReservasService.procesar_reserva(
        request=req,
        area=area_parrilla_fixture,
        estado_financiero_depto="AL_DIA",
        saldo_mora_depto=Decimal("0.00"),
        reservas_existentes=[],
    )

    # Verificación de la reserva confirmada
    assert reserva.estado == "CONFIRMADA"
    assert reserva.costo_reserva == Decimal("25.00")
    assert reserva.area_id == area_parrilla_fixture["id"]
    assert reserva.departamento_id == depto_id

    # Verificación de los 7 campos obligatorios de auditoría inmutable
    assert audit.departamento_id == str(depto_id)
    assert audit.timestamp is not None
    assert audit.accion_ejecutada == "RESERVA_CONFIRMADA"
    assert "Reserva aprobada" in audit.motivo
    assert audit.resultado == "EXITOSO"
    assert audit.estado_anterior["estado"] == "SOLICITADA"
    assert audit.estado_posterior["estado"] == "CONFIRMADA"
    assert audit.calcular_hash() is not None


def test_reservas_service_conflicto_solapamiento(area_parrilla_fixture):
    """Valida que solapamientos de horario en la misma área y fecha sean bloqueados con ConflictoHorarioException."""
    fecha_reserva = date(2026, 10, 31)
    reserva_existente = {
        "id": uuid.uuid4(),
        "area_id": area_parrilla_fixture["id"],
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": fecha_reserva,
        "hora_inicio": time(14, 0),
        "hora_fin": time(18, 0),
        "estado": "CONFIRMADA",
    }

    # Solicitud con solapamiento parcial (16:00 a 20:00)
    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=fecha_reserva,
        hora_inicio=time(16, 0),
        hora_fin=time(20, 0),
    )

    with pytest.raises(ConflictoHorarioException) as exc_info:
        ReservasService.procesar_reserva(
            request=req,
            area=area_parrilla_fixture,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[reserva_existente],
        )

    assert exc_info.value.error_code == "HORARIO_NO_DISPONIBLE"
    assert exc_info.value.fecha == fecha_reserva


def test_reservas_service_horarios_adyacentes_sin_conflicto(area_parrilla_fixture):
    """Valida que un horario consecutivo exacto (ej. 14:00-18:00 y 18:00-21:00) NO genere conflicto."""
    fecha_reserva = date(2026, 10, 31)
    reserva_existente = {
        "id": uuid.uuid4(),
        "area_id": area_parrilla_fixture["id"],
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": fecha_reserva,
        "hora_inicio": time(14, 0),
        "hora_fin": time(18, 0),
        "estado": "CONFIRMADA",
    }

    # Inicia exactamente cuando termina la anterior
    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=fecha_reserva,
        hora_inicio=time(18, 0),
        hora_fin=time(21, 0),
    )

    reserva, _ = ReservasService.procesar_reserva(
        request=req,
        area=area_parrilla_fixture,
        estado_financiero_depto="AL_DIA",
        saldo_mora_depto=Decimal("0.00"),
        reservas_existentes=[reserva_existente],
    )

    assert reserva.estado == "CONFIRMADA"


def test_reservas_service_horario_invalido(area_parrilla_fixture):
    """Valida que una reserva donde hora_fin <= hora_inicio sea rechazada."""
    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(20, 0),
        hora_fin=time(19, 0),
    )

    with pytest.raises(HorarioInvalidoException) as exc_info:
        ReservasService.procesar_reserva(
            request=req,
            area=area_parrilla_fixture,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[],
        )

    assert exc_info.value.error_code == "HORARIO_INVALIDO"


def test_reservas_service_area_inactiva(area_parrilla_fixture):
    """Valida que un área en mantenimiento o inactiva no permita reservas."""
    area_inactiva = dict(area_parrilla_fixture)
    area_inactiva["esta_activa"] = False

    req = CrearReservaRequest(
        condominio_id=area_parrilla_fixture["condominio_id"],
        area_id=area_parrilla_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(10, 0),
        hora_fin=time(12, 0),
    )

    with pytest.raises(AreaInactivaException) as exc_info:
        ReservasService.procesar_reserva(
            request=req,
            area=area_inactiva,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[],
        )

    assert exc_info.value.error_code == "AREA_INACTIVA"


def test_reservas_service_cancelacion_exitosa_24h():
    """Valida que una cancelación con >24h de anticipación sea procesada y auditada."""
    fecha_res = date.today() + timedelta(days=5)
    reserva = {
        "id": uuid.uuid4(),
        "condominio_id": uuid.uuid4(),
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": fecha_res,
        "hora_inicio": time(18, 0),
        "hora_fin": time(21, 0),
        "estado": "CONFIRMADA",
    }

    req = CancelarReservaRequest(motivo="Viaje imprevisto de trabajo", es_admin=False)
    ahora = datetime.now(timezone.utc)

    respuesta, audit = ReservasService.procesar_cancelacion(
        reserva=reserva, request=req, momento_actual=ahora
    )

    assert respuesta.estado == "CANCELADA"
    assert audit.accion_ejecutada == "RESERVA_CANCELADA"
    assert audit.resultado == "EXITOSO"
    assert audit.estado_anterior["estado"] == "CONFIRMADA"
    assert audit.estado_posterior["estado"] == "CANCELADA"


def test_reservas_service_cancelacion_rechazada_menos_24h():
    """Valida que una cancelación voluntaria con menos de 24h sea rechazada."""
    ahora = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    # Reserva es hoy a las 18:00 (a solo 8 horas)
    reserva = {
        "id": uuid.uuid4(),
        "condominio_id": uuid.uuid4(),
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": date(2026, 10, 20),
        "hora_inicio": time(18, 0),
        "hora_fin": time(21, 0),
        "estado": "CONFIRMADA",
    }

    req = CancelarReservaRequest(motivo="Cancelación tardía", es_admin=False)

    with pytest.raises(CancelacionInvalidaException) as exc_info:
        ReservasService.procesar_cancelacion(
            reserva=reserva, request=req, momento_actual=ahora
        )

    assert "requiere al menos 24 horas de anticipación" in exc_info.value.mensaje


def test_reservas_service_cancelacion_admin_sin_restriccion_24h():
    """Valida que un administrador de la Junta sí pueda cancelar con menos de 24h por fuerza mayor."""
    ahora = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    reserva = {
        "id": uuid.uuid4(),
        "condominio_id": uuid.uuid4(),
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": date(2026, 10, 20),
        "hora_inicio": time(18, 0),
        "hora_fin": time(21, 0),
        "estado": "CONFIRMADA",
    }

    req = CancelarReservaRequest(motivo="Cierre de emergencia por tubería rota", es_admin=True)

    respuesta, audit = ReservasService.procesar_cancelacion(
        reserva=reserva, request=req, momento_actual=ahora
    )

    assert respuesta.estado == "CANCELADA"
    assert audit.accion_ejecutada == "RESERVA_CANCELADA"
    assert "Cierre de emergencia" in audit.motivo
