"""Router FastAPI para el Dominio de Reservas de Áreas Comunes (Brandon - PROC-04)."""

import uuid
from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from scripts.seed_condominio_piloto import generar_datos_areas_comunes
from src.core.authorization import (
    autorizar_condominio,
    autorizar_departamento,
    contexto_consulta,
    puede_ver_departamento,
)
from src.core.roles import ROLES_ADMINISTRATIVOS
from src.core.security import get_current_user
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
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
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, DEPARTAMENTOS_PILOTO

router = APIRouter(tags=["Reservas de Áreas Comunes"])

# ============================================================================
# Almacén de Estado en Memoria (Simulación y Desarrollo)
# ============================================================================

# Inicialización de áreas comunes del piloto
AREAS_REGISTRADAS: Dict[uuid.UUID, Dict] = {}
_raw_areas = generar_datos_areas_comunes()
_fixed_uuids = [
    uuid.UUID("11111111-1111-1111-1111-111111111101"),
    uuid.UUID("11111111-1111-1111-1111-111111111102"),
    uuid.UUID("11111111-1111-1111-1111-111111111103"),
    uuid.UUID("11111111-1111-1111-1111-111111111104"),
]

for idx, area_data in enumerate(_raw_areas):
    area_uuid = _fixed_uuids[idx] if idx < len(_fixed_uuids) else uuid.uuid4()
    AREAS_REGISTRADAS[area_uuid] = {
        "id": area_uuid,
        "condominio_id": CONDOMINIO_PILOTO_ID,
        "nombre": area_data["nombre"],
        "descripcion": area_data.get("descripcion", ""),
        "aforo_maximo": area_data["aforo_maximo"],
        "costo_reserva": area_data["costo_reserva"],
        "esta_activa": True,
    }

# Almacén de reservas confirmadas / canceladas
RESERVAS_REGISTRADAS: Dict[uuid.UUID, Dict] = {}

# El contrato recibe UUID, no números: indexar por número dejaba la mora
# inalcanzable y trataba incluso al piloto moroso como AL_DIA. UUID5 mantiene
# identidades estables en este almacén simulado; no sustituye el catálogo de BD.
DEPARTAMENTOS_MAP = DEPARTAMENTOS_PILOTO


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
    user: dict = Depends(get_current_user), condominio_id: uuid.UUID | None = None
):
    """Retorna las áreas comunes disponibles para reserva en el condominio."""
    cid = contexto_consulta(user, condominio_id)
    return [
        AreaComunDTO(**area)
        for area in AREAS_REGISTRADAS.values()
        if area.get("esta_activa", True) and area["condominio_id"] == cid
    ]


@router.get("/areas/{area_id}/disponibilidad")
async def disponibilidad_area(
    area_id: uuid.UUID, fecha: date, user: dict = Depends(get_current_user)
):
    area = AREAS_REGISTRADAS.get(area_id)
    if not area:
        raise HTTPException(404, detail={"error_code": "AREA_NO_ENCONTRADA"})
    autorizar_condominio(user, area["condominio_id"])
    return [
        {"hora_inicio": r["hora_inicio"], "hora_fin": r["hora_fin"]}
        for r in RESERVAS_REGISTRADAS.values()
        if r["area_id"] == area_id and r["fecha_reserva"] == fecha and r["estado"] == "CONFIRMADA"
    ]


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
):
    """Permite a los residentes ver los horarios ocupados de un área común."""
    cid = contexto_consulta(user, condominio_id)
    if area_id is not None and area_id not in AREAS_REGISTRADAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AREA_NO_ENCONTRADA", "mensaje": "Área común no encontrada."},
        )

    if area_id is not None:
        autorizar_condominio(user, AREAS_REGISTRADAS[area_id]["condominio_id"])
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
):
    """Crea una reserva validando la solvencia financiera del departamento y la disponibilidad de horario."""
    autorizar_departamento(user, request.departamento_id, request.condominio_id, escritura=True)
    # 1. Comprobar existencia del área
    area = AREAS_REGISTRADAS.get(request.area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "AREA_NO_ENCONTRADA",
                "mensaje": f"Área común '{request.area_id}' no encontrada.",
            },
        )

    if area["condominio_id"] != request.condominio_id:
        raise HTTPException(
            403, detail={"error_code": "ACCESO_DENEGADO", "mensaje": "Área de otro condominio."}
        )

    try:
        # CON-42: consultar deuda real; el guard admite persistir CON-41 con su sesión.
        async with solvencia.para_reserva(request, user) as evaluacion:
            reserva_dto, _ = ReservasService.procesar_reserva(
                request=request,
                area=area,
                estado_financiero_depto="AL_DIA",
                saldo_mora_depto=evaluacion.saldo_vencido,
                reservas_existentes=list(RESERVAS_REGISTRADAS.values()),
            )
        # Se conserva el calendario existente: su persistencia corresponde a CON-73.
        RESERVAS_REGISTRADAS[reserva_dto.id] = reserva_dto.model_dump()
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
            status_code=status.HTTP_400_BAD_REQUEST,
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
):
    """Permite al residente o administrador cancelar una reserva con al menos 24h de anticipación."""
    reserva = RESERVAS_REGISTRADAS.get(reserva_id)
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESERVA_NO_ENCONTRADA", "mensaje": "Reserva no encontrada."},
        )

    autorizar_departamento(
        user, reserva["departamento_id"], reserva["condominio_id"], escritura=True
    )
    req = (request or CancelarReservaRequest()).model_copy(
        update={"es_admin": user["rol"] in ROLES_ADMINISTRATIVOS}
    )

    try:
        cancelar_dto, _ = ReservasService.procesar_cancelacion(
            reserva=reserva,
            request=req,
        )
        # Actualizar en memoria
        reserva["estado"] = "CANCELADA"
        return cancelar_dto
    except CancelacionInvalidaException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
