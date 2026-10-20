"""Endpoints de configuración y consulta de CON-10."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.cuotas.distribucion.exceptions import (
    AccesoDistribucionDenegadoError,
    CondominioNoEncontradoError,
    DistribucionError,
    DistribucionNoEncontradaError,
)
from src.modules.cuotas.distribucion.repository import (
    DistribucionRepository,
    SQLAlchemyDistribucionRepository,
)
from src.modules.cuotas.distribucion.schemas import (
    ConfigurarDistribucionRequest,
    DistribucionResponse,
)
from src.modules.cuotas.distribucion.service import ActorDistribucion, DistribucionService


class RutaDistribucion(APIRoute):
    """Localiza el contrato de validación sin cambiar el manejador de otros módulos."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        manejador = super().get_route_handler()

        async def validar(request: Request) -> Response:
            try:
                return await manejador(request)
            except RequestValidationError as exc:
                raise APIError(
                    422,
                    "DATOS_DISTRIBUCION_INVALIDOS",
                    "Los datos de distribución no cumplen el contrato.",
                ) from exc

        return validar


router = APIRouter(tags=["Distribución de cuotas"], route_class=RutaDistribucion)


async def require_distribucion_user(
    claims: Annotated[dict[str, Any], Depends(get_current_user)],
) -> ActorDistribucion:
    if not claims.get("sub") or not claims.get("rol"):
        raise APIError(401, "TOKEN_INVALIDO", "El token debe contener identidad y rol.")
    rol = str(claims["rol"])
    condominio_id = None
    if rol != "SUPERADMIN":
        try:
            condominio_id = UUID(str(claims.get("condominio_id")))
        except (TypeError, ValueError) as exc:
            raise APIError(
                403,
                "DISTRIBUCION_ACCESO_DENEGADO",
                "El token no contiene un contexto de condominio válido.",
            ) from exc
    return ActorDistribucion(str(claims["sub"]), rol, condominio_id)


def get_distribucion_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DistribucionRepository:
    return SQLAlchemyDistribucionRepository(session)


def _convertir_error(exc: DistribucionError) -> APIError:
    if isinstance(exc, AccesoDistribucionDenegadoError):
        codigo = 403
    elif isinstance(exc, (CondominioNoEncontradoError, DistribucionNoEncontradaError)):
        codigo = 404
    else:
        codigo = 422
    return APIError(codigo, exc.error_code, exc.mensaje, exc.detalles)


@router.put(
    "/condominios/{condominio_id}/distribucion",
    response_model=DistribucionResponse,
    summary="Configurar el método de distribución",
)
async def configurar_distribucion(
    condominio_id: UUID,
    request: ConfigurarDistribucionRequest,
    actor: Annotated[ActorDistribucion, Depends(require_distribucion_user)],
    repository: Annotated[DistribucionRepository, Depends(get_distribucion_repository)],
) -> DistribucionResponse:
    try:
        configuracion = await DistribucionService(repository).configurar(
            condominio_id, request, actor
        )
    except DistribucionError as exc:
        raise _convertir_error(exc) from exc
    return DistribucionResponse.model_validate(configuracion)


@router.get(
    "/condominios/{condominio_id}/distribucion",
    response_model=DistribucionResponse,
    summary="Consultar el método de distribución vigente",
)
async def obtener_distribucion(
    condominio_id: UUID,
    actor: Annotated[ActorDistribucion, Depends(require_distribucion_user)],
    repository: Annotated[DistribucionRepository, Depends(get_distribucion_repository)],
) -> DistribucionResponse:
    try:
        configuracion = await DistribucionService(repository).obtener(condominio_id, actor)
    except DistribucionError as exc:
        raise _convertir_error(exc) from exc
    return DistribucionResponse.model_validate(configuracion)
