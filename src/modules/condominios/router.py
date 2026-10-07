"""Router FastAPI para el Dominio de Condominios y Departamentos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.condominios.schemas import CondominioDTO, CrearCondominioRequest
from src.modules.condominios.service import (
    CondominiosService,
    ConfiguracionMoraInvalidaException,
)

router = APIRouter(prefix="/condominio", tags=["Condominios y Departamentos"])


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
    return condominio
