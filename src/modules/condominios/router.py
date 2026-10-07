"""Router FastAPI para el Dominio de Condominios y Departamentos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.schemas import (
    CondominioDTO,
    CrearCondominioRequest,
    CrearDepartamentoRequest,
    DepartamentoDTO,
)
from src.modules.condominios.service import (
    CondominioNoEncontradoException,
    CondominiosService,
    ConfiguracionMoraInvalidaException,
    DepartamentoDuplicadoException,
)

router = APIRouter(prefix="/condominio", tags=["Condominios y Departamentos"])

# Router hermano sin prefijo para que las unidades se publiquen en /api/v1/departamentos/...
departamentos_router = APIRouter(tags=["Condominios y Departamentos"])


@router.post(
    "/crear",
    response_model=CondominioDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de condominio con su configuración de mora",
)
async def crear_condominio(
    request: CrearCondominioRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Crea un condominio validando la coherencia entre la regla de mora y sus parámetros."""
    try:
        condominio, _ = await CondominiosService.crear_condominio(session=session, request=request)
    except ConfiguracionMoraInvalidaException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "CONFIGURACION_MORA_INVALIDA",
                "mensaje": exc.mensaje,
                "detalles": {"regla_mora_tipo": request.regla_mora_tipo.value},
            },
        )
    await session.commit()
    return condominio


@departamentos_router.post(
    "/departamentos/crear",
    response_model=DepartamentoDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de un departamento (unidad inmobiliaria)",
)
async def crear_departamento(
    request: CrearDepartamentoRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Registra una unidad inmobiliaria validando la existencia del condominio y la unicidad del número."""
    try:
        departamento, _ = await CondominiosService.crear_departamento(
            session=session, request=request
        )
    except CondominioNoEncontradoException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    except DepartamentoDuplicadoException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": exc.error_code, "mensaje": exc.mensaje},
        )
    await session.commit()
    return departamento
