"""Router FastAPI para el Dominio de Reservas de Áreas Comunes (Brandon - PROC-04 / CON-41 / CON-43)."""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import (
    autorizar_departamento,
    contexto_consulta,
    puede_ver_departamento,
)
from src.core.database import get_db_session
from src.core.roles import ROLES_ADMINISTRATIVOS
from src.core.security import get_current_user
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.reservas.areas.repository import AreasRepository, get_areas_repository
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.disponibilidad import DisponibilidadRepository, DisponibilidadService
from src.modules.reservas.repository import ReservasRepository, get_reservas_repository
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
    HorarioOcupado,
    ReservaResponseDTO,
)
from src.modules.reservas.service import (
    AreaInactivaException,
    CancelacionInvalidaException,
    ConflictoHorarioException,
    DeudaMoraActivaException,
    HorarioInvalidoException,
    ReservasService,
)
from src.modules.usuarios.departamentos import get_departamentos_portal_repository

router = APIRouter(tags=["Reservas de Áreas Comunes"])

# ============================================================================
# Almacén de Estado en Memoria (Fallback y Pruebas Unitarias Rápidas)
# ============================================================================
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
)
async def disponibilidad_area(
    area_id: uuid.UUID,
    fecha: date,
    response: Response,
    user: dict = Depends(get_current_user),
    areas_repository=Depends(get_areas_repository),
    session: AsyncSession = Depends(get_db_session),
    reservas_repository: Optional[ReservasRepository] = Depends(get_reservas_repository),
):
    DisponibilidadService.validar_fecha(fecha)
    area = await AreasService(areas_repository).publica(area_id, user)
    persistidas = await DisponibilidadRepository(session).reservas_confirmadas(
        area_id, area.condominio_id, fecha
    )
    # Mantiene visibles las operaciones piloto hasta integrar CON-41/46/73.
    piloto = [
        dict(r)
        for r in RESERVAS_REGISTRADAS.values()
        if r["area_id"] == area_id and r["condominio_id"] == area.condominio_id
    ]
    ids_piloto = {str(r["id"]) for r in piloto}
    ocupaciones = [r for r in persistidas if str(r["id"]) not in ids_piloto]
    ocupaciones.extend(r for r in piloto if r["estado"] == "CONFIRMADA")
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
    reservas_repository: ReservasRepository = Depends(get_reservas_repository),
):
    """Permite a los residentes ver los horarios ocupados de un área común."""
    cid = contexto_consulta(user, condominio_id)
    if area_id is not None:
        await AreasService(areas_repository).verificar_historial(area_id, user)

    if isinstance(reservas_repository, ReservasRepository):
        try:
            deptos_usuario = None
            if user.get("rol") == "RESIDENTE":
                deptos_usuario = [
                    uuid.UUID(d["id"])
                    for d in user.get("departamentos", [])
                    if d.get("activo", True)
                ]
            reservas_db = await reservas_repository.listar_reservas(
                condominio_id=uuid.UUID(str(cid)),
                area_id=area_id,
                fecha=fecha,
                departamento_ids=deptos_usuario,
            )
            if reservas_db:
                return [
                    ReservaResponseDTO(
                        id=r.id,
                        condominio_id=uuid.UUID(str(cid)),
                        area_id=r.area_id,
                        area_nombre=area_nombre,
                        departamento_id=r.departamento_id,
                        fecha_reserva=r.fecha_reserva,
                        hora_inicio=r.hora_inicio,
                        hora_fin=r.hora_fin,
                        costo_reserva=r.costo_reserva,
                        moneda="PEN",
                        estado=r.estado,
                        creado_en=r.creado_en,
                    )
                    for r, area_nombre in reservas_db
                    if puede_ver_departamento(user, r.departamento_id)
                ]
        except Exception:
            pass

    resultados = []
    for r in RESERVAS_REGISTRADAS.values():
        if (
            r["condominio_id"] == cid
            and (area_id is None or r["area_id"] == area_id)
            and puede_ver_departamento(user, r["departamento_id"])
        ):
            if fecha is None or r["fecha_reserva"] == fecha:
                resultados.append(ReservaResponseDTO(**r))
    return resultados


def get_areas_reserva_repository(solvencia=Depends(get_solvencia_service)):
    # Catalogo y solvencia comparten los locks de una sola transaccion financiera.
    return AreasRepository(solvencia.session)


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
    reservas_repository: Optional[ReservasRepository] = Depends(get_reservas_repository),
):
    """Crea una reserva validando la solvencia financiera del departamento y la disponibilidad de horario (CON-41/CON-43)."""
    autorizar_departamento(user, request.departamento_id, request.condominio_id, escritura=True)
    try:
        if solvencia is not None and hasattr(solvencia, "para_reserva"):
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

                # 2. Validar la unidad activa y su edificio
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

                if isinstance(reservas_repository, ReservasRepository):
                    try:
                        reserva_dto = await ReservasService.procesar_reserva_persistente(
                            request=request,
                            area=area,
                            estado_financiero_depto="AL_DIA",
                            saldo_mora_depto=evaluacion.saldo_vencido,
                            repository=reservas_repository,
                        )
                        RESERVAS_REGISTRADAS[reserva_dto.id] = {
                            **reserva_dto.model_dump(),
                            "zona_horaria": area.get("zona_horaria", "America/Lima"),
                        }
                        return reserva_dto
                    except (ConnectionRefusedError, OSError):
                        pass

                reserva_dto, _ = ReservasService.procesar_reserva(
                    request=request,
                    area=area,
                    estado_financiero_depto="AL_DIA",
                    saldo_mora_depto=evaluacion.saldo_vencido,
                    reservas_existentes=list(RESERVAS_REGISTRADAS.values()),
                )
                RESERVAS_REGISTRADAS[reserva_dto.id] = {
                    **reserva_dto.model_dump(),
                    "zona_horaria": area["zona_horaria"],
                }
                return reserva_dto
        else:
            # Flujo alternativo sin solvencia contextual
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
            estado_financiero = depto.get("estado_financiero", "AL_DIA")
            saldo_mora = depto.get("deuda_vencida", Decimal("0.00"))

            if isinstance(reservas_repository, ReservasRepository):
                try:
                    reserva_dto = await ReservasService.procesar_reserva_persistente(
                        request=request,
                        area=area,
                        estado_financiero_depto=estado_financiero,
                        saldo_mora_depto=saldo_mora,
                        repository=reservas_repository,
                    )
                    RESERVAS_REGISTRADAS[reserva_dto.id] = {
                        **reserva_dto.model_dump(),
                        "zona_horaria": area.get("zona_horaria", "America/Lima"),
                    }
                    return reserva_dto
                except (ConnectionRefusedError, OSError):
                    pass

            reserva_dto, _ = ReservasService.procesar_reserva(
                request=request,
                area=area,
                estado_financiero_depto=estado_financiero,
                saldo_mora_depto=saldo_mora,
                reservas_existentes=list(RESERVAS_REGISTRADAS.values()),
            )
            RESERVAS_REGISTRADAS[reserva_dto.id] = {
                **reserva_dto.model_dump(),
                "zona_horaria": area.get("zona_horaria", "America/Lima"),
            }
            return reserva_dto
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


@router.post(
    "/reservas/{reserva_id}/cancelar",
    response_model=CancelarReservaResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva confirmada",
)
async def cancelar_reserva(
    reserva_id: uuid.UUID,
    request: Optional[CancelarReservaRequest] = None,
    user: dict = Depends(get_current_user),
    reservas_repository: ReservasRepository = Depends(get_reservas_repository),
):
    """Permite al residente o administrador cancelar una reserva con al menos 24h de anticipación."""
    reserva_db = None
    if isinstance(reservas_repository, ReservasRepository):
        try:
            reserva_db = await reservas_repository.obtener_por_id(reserva_id, bloquear=True)
        except Exception:
            pass

    reserva_dict = None
    if reserva_db:
        reserva_dict = {
            "id": reserva_db.id,
            "condominio_id": user.get("condominio_id"),
            "departamento_id": reserva_db.departamento_id,
            "fecha_reserva": reserva_db.fecha_reserva,
            "hora_inicio": reserva_db.hora_inicio,
            "hora_fin": reserva_db.hora_fin,
            "estado": reserva_db.estado,
            "zona_horaria": "America/Lima",
        }
    elif reserva_id in RESERVAS_REGISTRADAS:
        reserva_dict = RESERVAS_REGISTRADAS[reserva_id]

    if not reserva_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESERVA_NO_ENCONTRADA", "mensaje": "Reserva no encontrada."},
        )

    autorizar_departamento(
        user, reserva_dict["departamento_id"], reserva_dict.get("condominio_id"), escritura=True
    )
    req = (request or CancelarReservaRequest()).model_copy(
        update={"es_admin": user["rol"] in ROLES_ADMINISTRATIVOS}
    )

    try:
        cancelar_dto, _ = ReservasService.procesar_cancelacion(
            reserva=reserva_dict,
            request=req,
        )
        if reserva_db:
            await reservas_repository.actualizar_estado(reserva_db, "CANCELADA")
        if reserva_id in RESERVAS_REGISTRADAS:
            RESERVAS_REGISTRADAS[reserva_id]["estado"] = "CANCELADA"
        return cancelar_dto
    except CancelacionInvalidaException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
