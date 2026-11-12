"""Diez casos críticos de CON-46; reloj fijo, sin red ni PostgreSQL."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.reservas.schemas import CancelarReservaRequest
from src.modules.reservas.service import CancelacionInvalidaException, ReservasService

INICIO_UTC = datetime(2030, 1, 10, 15, tzinfo=UTC)  # 10:00 Lima


def reserva(**extra):
    return {
        "id": uuid4(),
        "condominio_id": uuid4(),
        "departamento_id": uuid4(),
        "fecha_reserva": date(2030, 1, 10),
        "hora_inicio": time(10),
        "hora_fin": time(12),
        "zona_horaria": "America/Lima",
        "estado": "CONFIRMADA",
        **extra,
    }


def actor(rol="RESIDENTE"):
    return {"sub": str(uuid4()), "rol": rol}


@pytest.mark.parametrize("desfase", [-1, 0, 1])
def test_frontera_de_24_horas(desfase):
    ahora = INICIO_UTC - timedelta(hours=24) + timedelta(seconds=desfase)
    if desfase > 0:
        with pytest.raises(CancelacionInvalidaException, match="24 horas"):
            ReservasService.procesar_cancelacion(
                reserva(), CancelarReservaRequest(), ahora, actor=actor()
            )
    else:
        respuesta, auditoria = ReservasService.procesar_cancelacion(
            reserva(), CancelarReservaRequest(), ahora, actor=actor()
        )
        assert respuesta.fecha_cancelacion == ahora and respuesta.estado == "CANCELADA"
        assert auditoria.estado_anterior["estado"] == "CONFIRMADA"


def test_historico_sin_zona_conserva_utc():
    registro = reserva()
    registro.pop("zona_horaria")
    # Para un histórico 10:00 UTC, 10:01 UTC del día previo ya está fuera de plazo.
    with pytest.raises(CancelacionInvalidaException):
        ReservasService.procesar_cancelacion(
            registro,
            CancelarReservaRequest(),
            datetime(2030, 1, 9, 10, 1, tzinfo=UTC),
            actor=actor(),
        )


def test_administrador_autorizado_exceptua_plazo_y_registra_actor():
    admin = actor("ADMIN_JUNTA")
    resultado, auditoria = ReservasService.procesar_cancelacion(
        reserva(),
        CancelarReservaRequest(es_admin=False),
        INICIO_UTC - timedelta(hours=1),
        actor=admin,
    )
    assert resultado.estado == "CANCELADA"
    assert auditoria.actor_id == admin["sub"] and auditoria.actor_tipo == "ADMIN_JUNTA"


def test_es_admin_del_cliente_no_eleva_al_residente():
    with pytest.raises(CancelacionInvalidaException):
        ReservasService.procesar_cancelacion(
            reserva(),
            CancelarReservaRequest(es_admin=True),
            INICIO_UTC - timedelta(hours=1),
            actor=actor(),
        )


def test_estado_completado_no_puede_cancelarse():
    with pytest.raises(CancelacionInvalidaException) as exc:
        ReservasService.procesar_cancelacion(
            reserva(estado="COMPLETADA"), CancelarReservaRequest(), actor=actor("ADMIN_JUNTA")
        )
    assert exc.value.error_code == "ESTADO_RESERVA_INVALIDO"


@pytest.mark.parametrize(
    "cobro,estado,monto",
    [
        (None, "NO_APLICA", "0.00"),
        (
            {"monto": Decimal("50.00"), "monto_compensado": Decimal("10.00"), "reembolsable": True},
            "PENDIENTE",
            "40.00",
        ),
        (
            {"monto": Decimal("50.00"), "monto_compensado": Decimal("50.00"), "reembolsable": True},
            "NO_APLICA",
            "0.00",
        ),
    ],
)
def test_ajuste_depende_del_cobro_efectivo_no_de_la_tarifa(cobro, estado, monto):
    ajuste = ReservasService.ajuste_cancelacion(cobro)
    assert ajuste.estado == estado and ajuste.monto == Decimal(monto)
    assert ajuste.referencia is None  # Nunca afirmar una devolución aplicada.
