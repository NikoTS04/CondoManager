"""Router FastAPI para el Dominio de Reservas de Áreas Comunes (Brandon - PROC-04).

Persistencia real en PostgreSQL: `areas_comunes`, `departamentos` y `reservas`.
La invariante de solvencia se evalúa con `departamentos.estado_financiero` y la
colisión de horarios se previene con bloqueo pesimista (`SELECT ... FOR UPDATE`
sobre la fila del área) tal como exige `specs/01-architecture/concurrency-and-locking.md`.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.models import Departamento
from src.modules.cuotas.models import CuotaMantenimiento
from src.modules.reservas.models import AreaComun, Reserva
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearAreaRequest,
    CrearReservaRequest,
    ReservaResponseDTO,
)
from src.modules.reservas.service import (
    AreaDuplicadaException,
    AreaInactivaException,
    CancelacionInvalidaException,
    CondominioNoEncontradoException,
    ConflictoHorarioException,
    DeudaMoraActivaException,
    HorarioInvalidoException,
    ReservasService,
)

router = APIRouter(tags=["Reservas de Áreas Comunes"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# ============================================================================
# Utilidades de acceso a datos
# ============================================================================

async def _obtener_departamento(
    session: AsyncSession, identificador: uuid.UUID | str
) -> Departamento | None:
    """Resuelve un departamento por UUID o, si el valor no es un UUID, por su número."""
    if isinstance(identificador, uuid.UUID):
        return await session.get(Departamento, identificador)

    texto = str(identificador).strip()
    try:
        return await session.get(Departamento, uuid.UUID(texto))
    except ValueError:
        return await session.scalar(
            select(Departamento).where(Departamento.numero == texto)
        )


async def _saldo_mora_informativo(session: AsyncSession, departamento_id: uuid.UUID) -> Decimal:
    """Suma el pendiente de las cuotas vencidas. Solo informativo: el bloqueo lo define `estado_financiero`."""
    pendiente = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    CuotaMantenimiento.monto_total_exigible - CuotaMantenimiento.monto_pagado
                ),
                Decimal("0.00"),
            )
        ).where(
            CuotaMantenimiento.departamento_id == departamento_id,
            CuotaMantenimiento.estado.in_(("VENCIDA", "EN_MORA")),
        )
    )
    return Decimal(pendiente or "0.00")


def _dto_reserva_desde_fila(
    reserva: Reserva, area_nombre: str, condominio_id: uuid.UUID
) -> ReservaResponseDTO:
    return ReservaResponseDTO(
        id=reserva.id,
        condominio_id=condominio_id,
        area_id=reserva.area_id,
        area_nombre=area_nombre,
        departamento_id=reserva.departamento_id,
        fecha_reserva=reserva.fecha_reserva,
        hora_inicio=reserva.hora_inicio,
        hora_fin=reserva.hora_fin,
        costo_reserva=reserva.costo_reserva,
        estado=reserva.estado,
        creado_en=reserva.creado_en,
    )


# ============================================================================
# Endpoints de Áreas Comunes
# ============================================================================

@router.get(
    "/areas",
    response_model=list[AreaComunDTO],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de áreas comunes activas",
)
async def listar_areas(session: SessionDep):
    """Retorna desde la tabla `areas_comunes` las áreas habilitadas para reserva."""
    areas = await session.scalars(
        select(AreaComun)
        .where(AreaComun.esta_activa.is_(True))
        .order_by(AreaComun.nombre)
    )
    return [AreaComunDTO.model_validate(area) for area in areas.all()]


@router.post(
    "/areas/crear",
    response_model=AreaComunDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de un área común en el catálogo",
)
async def crear_area(request: CrearAreaRequest, session: SessionDep):
    """Registra una nueva área común validando la existencia del condominio y la unicidad del nombre."""
    try:
        area_dto, _ = await ReservasService.crear_area(session=session, request=request)
    except CondominioNoEncontradoException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    except AreaDuplicadaException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    await session.commit()
    return area_dto


# ============================================================================
# Endpoints de Reservas
# ============================================================================

@router.get(
    "/reservas",
    response_model=list[ReservaResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar reservas y disponibilidad por área y fecha",
)
async def listar_reservas(
    session: SessionDep,
    area_id: uuid.UUID = Query(..., description="ID del área común a consultar"),
    fecha: date | None = Query(None, description="Fecha específica para filtrar reservas"),
):
    """Permite a los residentes ver los horarios ocupados de un área común (solo `CONFIRMADA`)."""
    existe_area = await session.scalar(
        select(AreaComun.id).where(AreaComun.id == area_id)
    )
    if existe_area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AREA_NO_ENCONTRADA", "mensaje": "Área común no encontrada."},
        )

    stmt = (
        select(Reserva, AreaComun.nombre, AreaComun.condominio_id)
        .join(AreaComun, Reserva.area_id == AreaComun.id)
        .where(Reserva.area_id == area_id, Reserva.estado == "CONFIRMADA")
        .order_by(Reserva.fecha_reserva, Reserva.hora_inicio)
    )
    if fecha is not None:
        stmt = stmt.where(Reserva.fecha_reserva == fecha)

    filas = (await session.execute(stmt)).all()
    return [
        _dto_reserva_desde_fila(reserva, nombre, condominio_id)
        for reserva, nombre, condominio_id in filas
    ]


@router.post(
    "/reservas",
    response_model=ReservaResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitud de reserva de área común (con filtro de solvencia)",
)
async def crear_reserva(request: CrearReservaRequest, session: SessionDep):
    """Crea una reserva validando la solvencia financiera del departamento y la disponibilidad de horario."""
    # 1. Bloqueo pesimista del área: serializa a todos los solicitantes del mismo espacio
    area = (
        await session.execute(
            select(AreaComun).where(AreaComun.id == request.area_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AREA_NO_ENCONTRADA", "mensaje": f"Área común '{request.area_id}' no encontrada."},
        )

    # 2. Departamento titular (por UUID o por número, compatibilidad con el frontend)
    departamento = await _obtener_departamento(session, request.departamento_id)
    if departamento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "DEPARTAMENTO_NO_ENCONTRADO",
                "mensaje": f"Departamento '{request.departamento_id}' no encontrado.",
            },
        )
    if departamento.condominio_id != area.condominio_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "DEPARTAMENTO_NO_PERTENECE_AL_CONDOMINIO",
                "mensaje": "El departamento no pertenece al condominio del área común seleccionada.",
            },
        )

    # 3. Invariante de solvencia basada en `departamentos.estado_financiero`
    estado_financiero = departamento.estado_financiero
    saldo_mora = Decimal("0.00")
    if estado_financiero == "EN_MORA":
        saldo_mora = await _saldo_mora_informativo(session, departamento.id)

    # 4. Reservas confirmadas del área (se restringe por el FOR UPDATE del paso 1)
    existentes = (
        await session.scalars(
            select(Reserva).where(
                Reserva.area_id == area.id,
                Reserva.estado == "CONFIRMADA",
            )
        )
    ).all()
    reservas_existentes = [
        {
            "area_id": r.area_id,
            "fecha_reserva": r.fecha_reserva,
            "estado": r.estado,
            "hora_inicio": r.hora_inicio,
            "hora_fin": r.hora_fin,
        }
        for r in existentes
    ]

    # 5. Normalización: la fuente de verdad del condominio es el área
    solicitud = request.model_copy(
        update={
            "condominio_id": area.condominio_id,
            "departamento_id": departamento.id,
        }
    )
    area_contexto = {
        "id": area.id,
        "condominio_id": area.condominio_id,
        "nombre": area.nombre,
        "descripcion": area.descripcion,
        "aforo_maximo": area.aforo_maximo,
        "costo_reserva": str(area.costo_reserva),
        "esta_activa": area.esta_activa,
    }

    try:
        reserva_dto, _ = ReservasService.procesar_reserva(
            request=solicitud,
            area=area_contexto,
            estado_financiero_depto=estado_financiero,
            saldo_mora_depto=saldo_mora,
            reservas_existentes=reservas_existentes,
        )
    except DeudaMoraActivaException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": exc.error_code,
                "mensaje": exc.mensaje,
                "detalles": {"departamento_id": exc.departamento_id, "saldo_vencido": str(exc.saldo_vencido)},
            },
        )
    except ConflictoHorarioException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": exc.error_code,
                "mensaje": exc.mensaje,
                "detalles": {"area_id": exc.area_id, "fecha": str(exc.fecha)},
            },
        )
    except HorarioInvalidoException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    except AreaInactivaException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )

    reserva = Reserva(
        id=reserva_dto.id,
        area_id=area.id,
        departamento_id=departamento.id,
        fecha_reserva=reserva_dto.fecha_reserva,
        hora_inicio=reserva_dto.hora_inicio,
        hora_fin=reserva_dto.hora_fin,
        costo_reserva=reserva_dto.costo_reserva,
        estado=reserva_dto.estado,
        creado_en=reserva_dto.creado_en,
    )
    session.add(reserva)
    await session.flush()
    await session.commit()
    return reserva_dto


@router.post(
    "/reservas/{reserva_id}/cancelar",
    response_model=CancelarReservaResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva confirmada",
)
async def cancelar_reserva(
    reserva_id: uuid.UUID,
    session: SessionDep,
    request: CancelarReservaRequest | None = None,
):
    """Permite al residente o administrador cancelar una reserva con al menos 24h de anticipación."""
    reserva = (
        await session.execute(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESERVA_NO_ENCONTRADA", "mensaje": "Reserva no encontrada."},
        )

    area = await session.get(AreaComun, reserva.area_id)
    reserva_contexto = {
        "id": reserva.id,
        "estado": reserva.estado,
        "fecha_reserva": reserva.fecha_reserva,
        "hora_inicio": reserva.hora_inicio,
        "hora_fin": reserva.hora_fin,
        "area_id": reserva.area_id,
        "departamento_id": reserva.departamento_id,
        "condominio_id": area.condominio_id if area else None,
    }
    req = request or CancelarReservaRequest()

    try:
        cancelar_dto, _ = ReservasService.procesar_cancelacion(
            reserva=reserva_contexto,
            request=req,
        )
    except CancelacionInvalidaException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )

    reserva.estado = "CANCELADA"
    await session.flush()
    await session.commit()
    return cancelar_dto
