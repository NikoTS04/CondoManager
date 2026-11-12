"""Router FastAPI para el Dominio de Reservas de Áreas Comunes (Brandon - PROC-04)."""

import logging
import uuid
from datetime import date, time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import (
    autorizar_departamento,
    contexto_consulta,
    puede_ver_departamento,
)
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.reservas.areas.repository import AreasRepository, get_areas_repository
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.cancelaciones import get_cancelaciones_service
from src.modules.reservas.disponibilidad import DisponibilidadRepository, DisponibilidadService
from src.modules.reservas.persistencia import ReservasPersistentesService
from src.modules.reservas.repository import ReservasRepository
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
    ErrorResponse,
    HorarioOcupado,
    ReservaResponseDTO,
)
from src.modules.reservas.service import (
    AreaInactivaException,
    ConflictoHorarioException,
    DeudaMoraActivaException,
    HorarioInvalidoException,
    ReservasService,
)
from src.modules.usuarios.departamentos import get_departamentos_portal_repository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Reservas de Áreas Comunes"])

# ============================================================================
# Almacén de Estado en Memoria (Simulación y Desarrollo)
# ============================================================================

# Almacén de reservas confirmadas / canceladas
RESERVAS_REGISTRADAS: Dict[uuid.UUID, Dict] = {}

# ============================================================================
# Endpoints de Áreas Comunes
# ============================================================================


@router.get(
    "/areas",
    response_model=List[AreaComunDTO],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de áreas comunes activas",
)
async def listar_areas(
    user: dict = Depends(get_current_user),
    condominio_id: uuid.UUID | None = None,
    areas_repository=Depends(get_areas_repository),
):
    """Retorna las áreas comunes disponibles para reserva en el condominio."""
    return await AreasService(areas_repository).catalogo(user, condominio_id)


@router.get(
    "/areas/{area_id}/disponibilidad",
    response_model=List[HorarioOcupado],
    summary="Horarios ocupados del área sin datos de otros residentes",
    responses={503: {"model": ErrorResponse, "description": "Calendario no disponible."}},
)
async def disponibilidad_area(
    area_id: uuid.UUID,
    fecha: date,
    response: Response,
    user: dict = Depends(get_current_user),
    areas_repository=Depends(get_areas_repository),
    session: AsyncSession = Depends(get_db_session),
):
    DisponibilidadService.validar_fecha(fecha)
    area = await AreasService(areas_repository).publica(area_id, user)
    persistidas = await DisponibilidadRepository(session).reservas_confirmadas(
        area_id, area.condominio_id, fecha
    )
    # SQL es canónico: una cancelación confirmada en otro proceso no puede
    # quedar oculta por una copia piloto todavía marcada CONFIRMADA.
    piloto = [
        dict(r)
        for r in RESERVAS_REGISTRADAS.values()
        if r["area_id"] == area_id and r["condominio_id"] == area.condominio_id
    ]
    ocupaciones = DisponibilidadService.combinar_fuentes(persistidas, piloto)
    response.headers["Cache-Control"] = "no-store"
    return DisponibilidadService.horarios_ocupados(
        fecha, ocupaciones, area.hora_apertura, area.hora_cierre
    )


# ============================================================================
# Endpoints de Reservas
# ============================================================================


@router.get(
    "/reservas",
    response_model=List[ReservaResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar reservas y disponibilidad por área y fecha",
)
async def listar_reservas(
    area_id: Optional[uuid.UUID] = Query(None, description="ID del área común a consultar"),
    fecha: Optional[date] = Query(None, description="Fecha específica para filtrar reservas"),
    condominio_id: uuid.UUID | None = None,
    user: dict = Depends(get_current_user),
    areas_repository=Depends(get_areas_repository),
    cancelaciones=Depends(get_cancelaciones_service),
):
    """Permite a los residentes ver los horarios ocupados de un área común."""
    cid = contexto_consulta(user, condominio_id)
    if area_id is not None:
        await AreasService(areas_repository).verificar_historial(area_id, user)
    resultados = []
    for r in RESERVAS_REGISTRADAS.values():
        if (
            r["condominio_id"] == cid
            and (area_id is None or r["area_id"] == area_id)
            and puede_ver_departamento(user, r["departamento_id"])
        ):
            if fecha is None or r["fecha_reserva"] == fecha:
                resultados.append(ReservaResponseDTO(**r))
    persistidas = await cancelaciones.historial(cid, user, area_id, fecha)
    ids_sql = {r.id for r in persistidas}
    return [r for r in resultados if r.id not in ids_sql] + persistidas


def get_areas_reserva_repository(solvencia=Depends(get_solvencia_service)):
    # Catalogo y solvencia comparten los locks de una sola transaccion financiera.
    if hasattr(solvencia, "session"):
        return AreasRepository(solvencia.session)
    return AreasRepository(None)


def get_creacion_reservas_repository(solvencia=Depends(get_solvencia_service)):
    # CON-41/43 y CON-46 comparten transacción y orden de locks.
    return ReservasRepository(solvencia.session)


@router.post(
    "/reservas",
    response_model=ReservaResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitud de reserva de área común (con filtro de solvencia)",
)
async def crear_reserva(
    request: CrearReservaRequest,
    user: dict = Depends(get_current_user),
    solvencia=Depends(get_solvencia_service),
    repository=Depends(get_departamentos_portal_repository),
    areas_repository=Depends(get_areas_reserva_repository),
    reservas_repository=Depends(get_creacion_reservas_repository),
):
    """Crea una reserva validando la solvencia financiera del departamento y la disponibilidad de horario."""
    autorizar_departamento(user, request.departamento_id, request.condominio_id, escritura=True)
    try:
        async with solvencia.para_reserva(request, user) as evaluacion:
            # 1. Comprobar existencia del área
            area = (
                await AreasService(areas_repository).publica(
                    request.area_id,
                    user,
                    bloquear=True,
                    condominio_id=request.condominio_id,
                )
            ).model_dump()
            area["hora_apertura"] = time.fromisoformat(area["hora_apertura"])
            area["hora_cierre"] = time.fromisoformat(area["hora_cierre"])

            # 2. Validar la unidad activa y su edificio; la solvencia usa deuda real.
            depto = await repository.obtener(request.departamento_id)
            if not depto:
                raise HTTPException(404, detail={"error_code": "DEPARTAMENTO_NO_ENCONTRADO"})
            if depto["condominio_id"] != request.condominio_id or not depto["activo"]:
                raise HTTPException(403, detail={"error_code": "ACCESO_DENEGADO"})
            if area["edificio_id"] is not None and area["edificio_id"] != depto["edificio_id"]:
                raise HTTPException(
                    403,
                    detail={
                        "error_code": "ACCESO_DENEGADO",
                        "mensaje": "La unidad no pertenece al edificio del área.",
                    },
                )
            # Una cancelación SQL debe liberar el turno también al volver a
            # reservar desde un proceso con una copia piloto todavía antigua.
            persistidas = await areas_repository.ocupaciones(
                request.area_id, request.condominio_id, request.fecha_reserva
            )
            piloto = [
                r
                for r in RESERVAS_REGISTRADAS.values()
                if r["area_id"] == request.area_id and r["condominio_id"] == request.condominio_id
            ]
            ocupados = DisponibilidadService.horarios_ocupados(
                request.fecha_reserva,
                DisponibilidadService.combinar_fuentes(persistidas, piloto),
                area["hora_apertura"].isoformat(),
                area["hora_cierre"].isoformat(),
            )
            existentes = [
                {
                    "area_id": request.area_id,
                    "fecha_reserva": request.fecha_reserva,
                    "estado": "CONFIRMADA",
                    "hora_inicio": time.fromisoformat(h.hora_inicio),
                    "hora_fin": time.fromisoformat(h.hora_fin),
                }
                for h in ocupados
            ]
            if isinstance(reservas_repository, ReservasRepository):

                async def auditor(a):
                    await solvencia.repo.auditar(
                        user,
                        request.condominio_id,
                        request.departamento_id,
                        a.accion_ejecutada,
                        a.motivo,
                        a.estado_anterior,
                        a.estado_posterior,
                    )

                reserva_dto = await ReservasService.procesar_reserva_persistente(
                    request=request,
                    area=area,
                    estado_financiero_depto="AL_DIA",
                    saldo_mora_depto=evaluacion.saldo_vencido,
                    repository=reservas_repository,
                    usuario_id=uuid.UUID(user["sub"]),
                    reservas_existentes=existentes,
                    auditor=auditor,
                )
                # Evento durable en la misma transacción que la reserva y su auditoría.
                guardada = await reservas_repository.obtener_por_id(reserva_dto.id)
                ReservasPersistentesService(solvencia).evento(
                    guardada, "ReservaConfirmadaEvent", reserva_dto.area_nombre
                )
                await solvencia.session.flush()
            else:
                # Adaptador explícito de pruebas históricas, sin fallback ante
                # fallos SQL del productor de CON-41.
                reserva_dto, _ = ReservasService.procesar_reserva(
                    request=request,
                    area=area,
                    estado_financiero_depto="AL_DIA",
                    saldo_mora_depto=evaluacion.saldo_vencido,
                    reservas_existentes=existentes,
                )
        # La copia de compatibilidad se actualiza únicamente tras el commit.
        RESERVAS_REGISTRADAS[reserva_dto.id] = {
            **reserva_dto.model_dump(),
            "zona_horaria": area["zona_horaria"],
            "usuario_id": user["sub"],
        }
        return reserva_dto

    except DeudaMoraActivaException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": exc.error_code,
                "mensaje": exc.mensaje,
                "detalles": {
                    "departamento_id": exc.departamento_id,
                    "saldo_vencido": str(exc.saldo_vencido),
                },
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
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    except SQLAlchemyError as exc:
        logger.exception("Fallo SQL al confirmar la reserva")
        raise APIError(
            503,
            "RESERVA_NO_DISPONIBLE",
            "No se pudo confirmar la reserva. Intente nuevamente más tarde.",
        ) from exc


@router.post(
    "/reservas/{reserva_id}/cancelar",
    response_model=CancelarReservaResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva confirmada",
    responses={503: {"model": ErrorResponse, "description": "Cancelación no disponible."}},
)
async def cancelar_reserva(
    reserva_id: uuid.UUID,
    request: Optional[CancelarReservaRequest] = None,
    user: dict = Depends(get_current_user),
    cancelaciones=Depends(get_cancelaciones_service),
):
    """Permite al residente o administrador cancelar una reserva con al menos 24h de anticipación."""
    reserva = RESERVAS_REGISTRADAS.get(reserva_id)
    if reserva is not None:
        autorizar_departamento(
            user, reserva["departamento_id"], reserva["condominio_id"], escritura=True
        )
    resultado = await cancelaciones.cancelar(
        reserva_id, request or CancelarReservaRequest(), user, piloto=reserva
    )
    # El servicio ha completado el commit. Nunca adelantar este cambio al SQL.
    if reserva is not None:
        reserva["estado"] = "CANCELADA"
    return resultado
