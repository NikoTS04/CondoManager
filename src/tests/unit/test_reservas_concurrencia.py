"""Pruebas unitarias de control de solvencia y concurrencia de reservas (CON-41 / CON-43 / Brandon)."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.modules.reservas.models import Reserva
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
def area_comun_fixture():
    return {
        "id": uuid.uuid4(),
        "condominio_id": uuid.uuid4(),
        "nombre": "Zona de Parrillas Terraza",
        "esta_activa": True,
        "costo_reserva": Decimal("30.00"),
        "hora_apertura": time(8, 0),
        "hora_cierre": time(23, 0),
        "tiempo_maximo_horas": 4,
        "moneda": "PEN",
        "zona_horaria": "America/Lima",
    }


def test_solvencia_rechazo_con_mora_activa(area_comun_fixture):
    """CON-41: Una unidad con deuda vencida en mora debe ser rechazada de inmediato."""
    depto_id = uuid.uuid4()
    req = CrearReservaRequest(
        condominio_id=area_comun_fixture["condominio_id"],
        area_id=area_comun_fixture["id"],
        departamento_id=depto_id,
        fecha_reserva=date(2026, 11, 20),
        hora_inicio=time(14, 0),
        hora_fin=time(18, 0),
    )

    with pytest.raises(DeudaMoraActivaException) as exc_info:
        ReservasService.procesar_reserva(
            request=req,
            area=area_comun_fixture,
            estado_financiero_depto="EN_MORA",
            saldo_mora_depto=Decimal("210.00"),
            reservas_existentes=[],
        )

    assert exc_info.value.error_code == "DEUDA_MORA_ACTIVA"
    assert exc_info.value.saldo_vencido == Decimal("210.00")
    assert str(depto_id) in exc_info.value.mensaje


def test_solvencia_aprobacion_residente_al_dia(area_comun_fixture):
    """CON-41: Un residente solvente (saldo mora 0.00, AL_DIA) reserva con éxito."""
    depto_id = uuid.uuid4()
    req = CrearReservaRequest(
        condominio_id=area_comun_fixture["condominio_id"],
        area_id=area_comun_fixture["id"],
        departamento_id=depto_id,
        fecha_reserva=date(2026, 11, 20),
        hora_inicio=time(10, 0),
        hora_fin=time(14, 0),
    )

    reserva, audit = ReservasService.procesar_reserva(
        request=req,
        area=area_comun_fixture,
        estado_financiero_depto="AL_DIA",
        saldo_mora_depto=Decimal("0.00"),
        reservas_existentes=[],
    )

    assert reserva.estado == "CONFIRMADA"
    assert reserva.costo_reserva == Decimal("30.00")
    assert audit.accion_ejecutada == "RESERVA_CONFIRMADA"
    assert audit.resultado == "EXITOSO"


def test_concurrencia_solapamiento_bloqueado(area_comun_fixture):
    """CON-43: Intervalos que se cruzan parcialmente deben ser rechazados."""
    fecha = date(2026, 11, 20)
    reserva_existente = {
        "id": uuid.uuid4(),
        "area_id": area_comun_fixture["id"],
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": fecha,
        "hora_inicio": time(14, 0),
        "hora_fin": time(18, 0),
        "estado": "CONFIRMADA",
    }

    # Intento 1: Empieza antes pero termina dentro (13:00 - 15:00)
    req1 = CrearReservaRequest(
        condominio_id=area_comun_fixture["condominio_id"],
        area_id=area_comun_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=fecha,
        hora_inicio=time(13, 0),
        hora_fin=time(15, 0),
    )
    with pytest.raises(ConflictoHorarioException) as exc1:
        ReservasService.procesar_reserva(
            request=req1,
            area=area_comun_fixture,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[reserva_existente],
        )
    assert exc1.value.error_code == "HORARIO_NO_DISPONIBLE"

    # Intento 2: Empieza dentro y termina después (17:00 - 20:00)
    req2 = CrearReservaRequest(
        condominio_id=area_comun_fixture["condominio_id"],
        area_id=area_comun_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=fecha,
        hora_inicio=time(17, 0),
        hora_fin=time(20, 0),
    )
    with pytest.raises(ConflictoHorarioException) as exc2:
        ReservasService.procesar_reserva(
            request=req2,
            area=area_comun_fixture,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[reserva_existente],
        )
    assert exc2.value.error_code == "HORARIO_NO_DISPONIBLE"


def test_concurrencia_horarios_contiguos_permitidos(area_comun_fixture):
    """CON-43: Turnos contiguos (ej. 10:00-14:00 y 14:00-18:00) no deben colisionar."""
    fecha = date(2026, 11, 20)
    reserva_existente = {
        "id": uuid.uuid4(),
        "area_id": area_comun_fixture["id"],
        "departamento_id": uuid.uuid4(),
        "fecha_reserva": fecha,
        "hora_inicio": time(10, 0),
        "hora_fin": time(14, 0),
        "estado": "CONFIRMADA",
    }

    req = CrearReservaRequest(
        condominio_id=area_comun_fixture["condominio_id"],
        area_id=area_comun_fixture["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=fecha,
        hora_inicio=time(14, 0),
        hora_fin=time(18, 0),
    )

    reserva, _ = ReservasService.procesar_reserva(
        request=req,
        area=area_comun_fixture,
        estado_financiero_depto="AL_DIA",
        saldo_mora_depto=Decimal("0.00"),
        reservas_existentes=[reserva_existente],
    )
    assert reserva.estado == "CONFIRMADA"


@pytest.mark.asyncio
async def test_concurrencia_diez_solicitudes_simultaneas(area_comun_fixture):
    """CON-43: 10 solicitudes concurrentes al mismo horario exacto resultan en 1 confirmada y 9 rechazadas."""
    fecha = date(2026, 11, 25)
    hora_ini = time(16, 0)
    hora_fin = time(20, 0)

    # Simulación de repositorio en base de datos con bloqueo pesimista
    reservas_db = []
    lock = asyncio.Lock()

    class FakeReservasRepository:
        async def buscar_solapamientos(self, area_id, fecha, hora_inicio, hora_fin, bloquear=False):
            # En base de datos real SELECT ... FOR UPDATE serializa la verificación
            return [
                r for r in reservas_db
                if r.area_id == area_id
                and r.fecha_reserva == fecha
                and r.estado == "CONFIRMADA"
                and r.hora_inicio < hora_fin
                and r.hora_fin > hora_inicio
            ]

        async def guardar(self, reserva):
            reservas_db.append(reserva)
            return reserva

    repo = FakeReservasRepository()

    async def intentar_reserva(dept_idx):
        async with lock:  # Simula el aislamiento transaccional pesimista de PostgreSQL
            req = CrearReservaRequest(
                condominio_id=area_comun_fixture["condominio_id"],
                area_id=area_comun_fixture["id"],
                departamento_id=uuid.uuid4(),
                fecha_reserva=fecha,
                hora_inicio=hora_ini,
                hora_fin=hora_fin,
            )
            return await ReservasService.procesar_reserva_persistente(
                request=req,
                area=area_comun_fixture,
                estado_financiero_depto="AL_DIA",
                saldo_mora_depto=Decimal("0.00"),
                repository=repo,
            )

    exitos = 0
    conflictos = 0

    tareas = [intentar_reserva(i) for i in range(10)]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    for r in resultados:
        if isinstance(r, ConflictoHorarioException):
            conflictos += 1
        elif hasattr(r, "estado") and r.estado == "CONFIRMADA":
            exitos += 1

    # Exactamente 1 reserva confirmada y 9 conflictos
    assert exitos == 1
    assert conflictos == 9
    assert len(reservas_db) == 1
