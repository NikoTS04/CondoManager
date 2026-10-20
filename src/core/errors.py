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
    """Adapta validaciones de FastAPI a los contratos públicos de CON-2 y CON-9."""

    if (
        request.url.path.startswith("/api/v1/condominios/")
        and "/usuarios/" in request.url.path
        and "/departamentos" in request.url.path
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_VINCULO_INVALIDOS",
                "mensaje": "Indique UUID válidos y una relación de tenencia válida.",
                "detalles": [{"campo": list(e["loc"]), "tipo": e["type"]} for e in exc.errors()],
            },
        )
    if request.url.path.startswith("/api/v1/condominios/") and request.url.path.endswith("/rol"):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_ROL_INVALIDOS",
                "mensaje": "Indique un rol contextual válido y UUID válidos.",
                "detalles": [{"campo": list(e["loc"]), "tipo": e["type"]} for e in exc.errors()],
            },
        )
    if request.url.path.startswith(
        ("/api/v1/usuarios", "/api/v1/auth")
    ) or request.url.path.endswith("/usuarios"):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_USUARIO_INVALIDOS",
                "mensaje": "Los datos de usuario no cumplen el contrato.",
                "detalles": [{"campo": list(e["loc"]), "tipo": e["type"]} for e in exc.errors()],
            },
        )
    if request.url.path == "/api/v1/cuotas/emitir-lote":
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_EMISION_INVALIDOS",
                "mensaje": "Envíe únicamente un condominio y un periodo YYYY-MM válido.",
                "detalles": {"errores": jsonable_encoder(exc.errors())},
            },
        )
    if request.url.path.startswith("/api/v1/presupuestos") or "/presupuestos/" in request.url.path:
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_PRESUPUESTO_INVALIDOS",
                "mensaje": "Los datos del presupuesto no cumplen el contrato.",
                "detalles": jsonable_encoder(exc.errors()),
            },
        )
    if request.url.path.startswith("/api/v1/condominios") and any(
        segmento in request.url.path
        for segmento in ("/edificios", "/departamentos", "/importaciones")
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "DATOS_ESTRUCTURA_INVALIDOS",
                "mensaje": "Los datos de estructura no cumplen el contrato.",
                "detalles": jsonable_encoder(exc.errors()),
            },
        )
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
