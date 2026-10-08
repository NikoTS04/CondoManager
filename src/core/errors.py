"""Errores de API con el formato público definido por los contratos SDD."""

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Error controlado que se serializa sin envoltorios ajenos al contrato."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        mensaje: str,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.error_code = error_code
        self.mensaje = mensaje
        self.detalles = detalles


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    payload: dict[str, Any] = {
        "error_code": exc.error_code,
        "mensaje": exc.mensaje,
    }
    if exc.detalles is not None:
        payload["detalles"] = exc.detalles
    return JSONResponse(status_code=exc.status_code, content=payload)


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Conserva el comportamiento existente salvo para el contrato de CON-2."""

    if request.url.path.startswith("/api/v1/condominios"):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_CONDOMINIO_INVALIDOS",
                "mensaje": "Los datos del condominio no cumplen el contrato.",
                "detalles": jsonable_encoder(exc.errors()),
            },
        )
    return await request_validation_exception_handler(request, exc)
