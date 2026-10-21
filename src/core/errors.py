"""Errores públicos consistentes, sin entradas sensibles en validaciones."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ErrorResponse(BaseModel):
    error_code: str
    mensaje: str
    detalles: dict[str, Any] | None = None


class APIError(Exception):
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
    payload = {"error_code": exc.error_code, "mensaje": exc.mensaje}
    if exc.detalles is not None:
        payload["detalles"] = exc.detalles
    return JSONResponse(status_code=exc.status_code, content=payload)


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    defaults = {
        401: ("NO_AUTENTICADO", "Autenticación requerida."),
        403: ("ACCESO_DENEGADO", "No tiene acceso al recurso."),
        404: ("RECURSO_NO_ENCONTRADO", "No existe el recurso."),
        405: ("METODO_NO_PERMITIDO", "Método no permitido."),
        413: ("ARCHIVO_DEMASIADO_GRANDE", "La solicitud excede el límite permitido."),
    }
    codigo, mensaje = defaults.get(
        exc.status_code, ("SOLICITUD_INVALIDA", "No se pudo completar la solicitud.")
    )
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    error = APIError(
        exc.status_code,
        detail.get("error_code", codigo),
        detail.get("mensaje", mensaje),
        detail.get("detalles") if isinstance(detail.get("detalles"), dict) else None,
    )
    response = await api_error_handler(request, error)
    response.headers.update(exc.headers or {})
    return response


async def unexpected_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    return await api_error_handler(
        request, APIError(500, "ERROR_INTERNO", "No se pudo completar la operación.")
    )


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    path = request.url.path
    codigo = "DATOS_INVALIDOS"
    if path.startswith("/api/v1/pagos"):
        codigo = "DATOS_COMPROBANTE_INVALIDOS"
    elif path.startswith("/api/v1/reservas"):
        codigo = "DATOS_RESERVA_INVALIDOS"
    elif path.startswith("/api/v1/notificaciones"):
        codigo = "DATOS_NOTIFICACION_INVALIDOS"
    elif path.startswith("/api/v1/areas/") and path.endswith("/disponibilidad"):
        codigo = "DATOS_DISPONIBILIDAD_INVALIDOS"
    elif (
        path == "/api/v1/areas"
        or path.startswith("/api/v1/areas/")
        or (path.startswith("/api/v1/condominios/") and path.split("/")[5:6] == ["areas"])
    ):
        codigo = "DATOS_AREA_INVALIDOS"
    elif "/usuarios/" in path and "/departamentos" in path:
        codigo = "DATOS_VINCULO_INVALIDOS"
    elif path.endswith("/rol"):
        codigo = "DATOS_ROL_INVALIDOS"
    elif path.startswith(("/api/v1/usuarios", "/api/v1/auth")) or path.endswith("/usuarios"):
        codigo = "DATOS_USUARIO_INVALIDOS"
    elif path == "/api/v1/cuotas/emitir-lote":
        codigo = "DATOS_EMISION_INVALIDOS"
    elif "/presupuestos" in path:
        codigo = "DATOS_PRESUPUESTO_INVALIDOS"
    elif path.startswith("/api/v1/condominios"):
        codigo = (
            "DATOS_ESTRUCTURA_INVALIDOS"
            if any(p in path for p in ("/edificios", "/departamentos", "/importaciones"))
            else "DATOS_CONDOMINIO_INVALIDOS"
        )
    return await api_error_handler(
        request,
        APIError(
            422,
            codigo,
            "Revise los campos y el formato de la solicitud.",
            {"errores": [{"campo": list(e["loc"]), "tipo": e["type"]} for e in exc.errors()]},
        ),
    )
