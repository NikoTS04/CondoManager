"""Endpoints FastAPI del presupuesto mensual de CON-9."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import decode_access_token, security_scheme
from src.modules.cuotas.presupuestos.exceptions import (
    AccesoPresupuestoDenegadoError,
    CondominioNoEncontradoError,
    DatosPresupuestoInvalidosError,
    PresupuestoError,
    PresupuestoNoEditableError,
    PresupuestoNoEncontradoError,
    PresupuestoPeriodoDuplicadoError,
)
from src.modules.cuotas.presupuestos.repository import (
    PresupuestoRepository,
    SQLAlchemyPresupuestoRepository,
)
from src.modules.cuotas.presupuestos.schemas import (
    ActualizarPresupuestoRequest,
    CrearPresupuestoRequest,
    PERIODO_PATTERN,
    PresupuestoResponse,
)
from src.modules.cuotas.presupuestos.service import ActorPresupuesto, PresupuestosService

router = APIRouter(tags=["Presupuestos Mensuales"])


async def require_presupuesto_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> dict[str, Any]:
    if auth is None or not auth.credentials:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            "NO_AUTENTICADO",
            "Se requiere un Bearer Token válido.",
        )
    try:
        return decode_access_token(auth.credentials)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        raise APIError(
            exc.status_code,
            str(detail.get("error_code", "TOKEN_INVALIDO")),
            str(detail.get("mensaje", "Token de autenticación inválido.")),
        ) from exc


def get_presupuesto_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PresupuestoRepository:
    return SQLAlchemyPresupuestoRepository(session)


def _actor_desde_claims(current_user: dict[str, Any]) -> ActorPresupuesto:
    actor_id = current_user.get("sub")
    rol = current_user.get("rol")
    if not actor_id or not rol:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            "TOKEN_INVALIDO",
            "El token no contiene los claims obligatorios de identidad y rol.",
        )

    if rol == "SUPERADMIN":
        return ActorPresupuesto(id=str(actor_id), rol=str(rol), condominio_id=None)

    condominio_claim = current_user.get("condominio_id")
    try:
        condominio_id = UUID(str(condominio_claim))
    except (TypeError, ValueError) as exc:
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            "PRESUPUESTO_ACCESO_DENEGADO",
            "El token no contiene un contexto de condominio válido.",
        ) from exc
    return ActorPresupuesto(
        id=str(actor_id),
        rol=str(rol),
        condominio_id=condominio_id,
    )


def _convertir_error(exc: PresupuestoError) -> APIError:
    if isinstance(exc, AccesoPresupuestoDenegadoError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, (CondominioNoEncontradoError, PresupuestoNoEncontradoError)):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (PresupuestoPeriodoDuplicadoError, PresupuestoNoEditableError)):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, DatosPresupuestoInvalidosError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return APIError(status_code, exc.error_code, exc.mensaje, exc.detalles)


@router.post(
    "/presupuestos",
    response_model=PresupuestoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un presupuesto mensual en borrador",
)
async def crear_presupuesto(
    request: CrearPresupuestoRequest,
    current_user: Annotated[dict[str, Any], Depends(require_presupuesto_user)],
    repository: Annotated[PresupuestoRepository, Depends(get_presupuesto_repository)],
) -> PresupuestoResponse:
    try:
        presupuesto = await PresupuestosService(repository).crear(
            request,
            _actor_desde_claims(current_user),
        )
    except PresupuestoError as exc:
        raise _convertir_error(exc) from exc
    return PresupuestoResponse.model_validate(presupuesto)


@router.put(
    "/presupuestos/{id}",
    response_model=PresupuestoResponse,
    status_code=status.HTTP_200_OK,
    summary="Modificar un presupuesto mensual en borrador",
)
async def actualizar_presupuesto(
    id: UUID,
    request: ActualizarPresupuestoRequest,
    current_user: Annotated[dict[str, Any], Depends(require_presupuesto_user)],
    repository: Annotated[PresupuestoRepository, Depends(get_presupuesto_repository)],
) -> PresupuestoResponse:
    try:
        presupuesto = await PresupuestosService(repository).actualizar(
            id,
            request,
            _actor_desde_claims(current_user),
        )
    except PresupuestoError as exc:
        raise _convertir_error(exc) from exc
    return PresupuestoResponse.model_validate(presupuesto)


@router.post(
    "/presupuestos/{id}/aprobar",
    response_model=PresupuestoResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobar un presupuesto mensual",
)
async def aprobar_presupuesto(
    id: UUID,
    current_user: Annotated[dict[str, Any], Depends(require_presupuesto_user)],
    repository: Annotated[PresupuestoRepository, Depends(get_presupuesto_repository)],
) -> PresupuestoResponse:
    try:
        presupuesto = await PresupuestosService(repository).aprobar(
            id,
            _actor_desde_claims(current_user),
        )
    except PresupuestoError as exc:
        raise _convertir_error(exc) from exc
    return PresupuestoResponse.model_validate(presupuesto)


@router.get(
    "/condominios/{condominio_id}/presupuestos/{periodo}",
    response_model=PresupuestoResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar el presupuesto de un condominio y periodo",
)
async def obtener_presupuesto_por_periodo(
    condominio_id: UUID,
    periodo: Annotated[str, Path(pattern=PERIODO_PATTERN)],
    current_user: Annotated[dict[str, Any], Depends(require_presupuesto_user)],
    repository: Annotated[PresupuestoRepository, Depends(get_presupuesto_repository)],
) -> PresupuestoResponse:
    try:
        presupuesto = await PresupuestosService(repository).obtener_por_periodo(
            condominio_id,
            periodo,
            _actor_desde_claims(current_user),
        )
    except PresupuestoError as exc:
        raise _convertir_error(exc) from exc
    return PresupuestoResponse.model_validate(presupuesto)
