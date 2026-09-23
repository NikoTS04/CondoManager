"""Router FastAPI para el Dominio de Reservas de Áreas Comunes (Brandon - PROC-04)."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from scripts.seed_condominio_piloto import generar_datos_areas_comunes, generar_datos_departamentos
from src.modules.reservas.schemas import (
    AreaComunDTO,
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
    ReservaResponseDTO,
)
from src.modules.reservas.service import (
    AreaInactivaException,
    AreaNoEncontradaException,
    CancelacionInvalidaException,
    ConflictoHorarioException,
    DeudaMoraActivaException,
    HorarioInvalidoException,
    ReservasService,
)

router = APIRouter(tags=["Reservas de Áreas Comunes"])

# ============================================================================
# Almacén de Estado en Memoria (Simulación y Desarrollo)
# ============================================================================

CONDOMINIO_PILOTO_ID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

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

# Mapa de departamentos con estado y moras
DEPARTAMENTOS_MAP: Dict[str, Dict] = {}
for d in generar_datos_departamentos():
    DEPARTAMENTOS_MAP[d["numero"]] = d


# ============================================================================
# Endpoints de Áreas Comunes
# ============================================================================

@router.get(
    "/areas",
    response_model=List[AreaComunDTO],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de áreas comunes activas",
)
async def listar_areas():
    """Retorna las áreas comunes disponibles para reserva en el condominio."""
    return [
        AreaComunDTO(**area)
        for area in AREAS_REGISTRADAS.values()
        if area.get("esta_activa", True)
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
    area_id: uuid.UUID = Query(..., description="ID del área común a consultar"),
    fecha: Optional[date] = Query(None, description="Fecha específica para filtrar reservas"),
):
    """Permite a los residentes ver los horarios ocupados de un área común."""
    if area_id not in AREAS_REGISTRADAS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AREA_NO_ENCONTRADA", "mensaje": "Área común no encontrada."},
        )

    resultados = []
    for r in RESERVAS_REGISTRADAS.values():
        if r["area_id"] == area_id and r["estado"] == "CONFIRMADA":
            if fecha is None or r["fecha_reserva"] == fecha:
                resultados.append(ReservaResponseDTO(**r))
    return resultados


@router.post(
    "/reservas",
    response_model=ReservaResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitud de reserva de área común (con filtro de solvencia)",
)
async def crear_reserva(request: CrearReservaRequest):
    """Crea una reserva validando la solvencia financiera del departamento y la disponibilidad de horario."""
    # 1. Comprobar existencia del área
    area = AREAS_REGISTRADAS.get(request.area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AREA_NO_ENCONTRADA", "mensaje": f"Área común '{request.area_id}' no encontrada."},
        )

    # 2. Consultar estado financiero del departamento
    # Buscamos en el dataset piloto o asumimos AL_DIA si es un UUID nuevo
    depto_id_str = str(request.departamento_id)
    estado_financiero = "AL_DIA"
    saldo_mora = Decimal("0.00")

    # Si se pasó un número de departamento piloto (ej. 402 moroso)
    if depto_id_str in DEPARTAMENTOS_MAP:
        depto = DEPARTAMENTOS_MAP[depto_id_str]
        estado_financiero = depto.get("estado_financiero", "AL_DIA")
        if estado_financiero == "EN_MORA":
            saldo_mora = Decimal("170.00")

    try:
        reserva_dto, _ = ReservasService.procesar_reserva(
            request=request,
            area=area,
            estado_financiero_depto=estado_financiero,
            saldo_mora_depto=saldo_mora,
            reservas_existentes=list(RESERVAS_REGISTRADAS.values()),
        )
        # Guardar en memoria
        RESERVAS_REGISTRADAS[reserva_dto.id] = reserva_dto.model_dump()
        return reserva_dto

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


@router.post(
    "/reservas/{reserva_id}/cancelar",
    response_model=CancelarReservaResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva confirmada",
)
async def cancelar_reserva(reserva_id: uuid.UUID, request: Optional[CancelarReservaRequest] = None):
    """Permite al residente o administrador cancelar una reserva con al menos 24h de anticipación."""
    reserva = RESERVAS_REGISTRADAS.get(reserva_id)
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESERVA_NO_ENCONTRADA", "mensaje": "Reserva no encontrada."},
        )

    req = request or CancelarReservaRequest()

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
