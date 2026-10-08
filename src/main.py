"""Punto de entrada principal de la API de CondoManager."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CondoManager API",
    description="Sistema Automatizado de Gestión de Pagos, Morosidad y Reservas para Condominios (SDD)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.core.errors import APIError, api_error_handler, request_validation_handler

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)


from src.modules.condominios.router import router as condominios_router
from src.modules.cuotas.router import router as cuotas_router
from src.modules.notificaciones.router import router as notificaciones_router
from src.modules.pagos.router import router as pagos_router
from src.modules.reservas.router import router as reservas_router
from src.modules.usuarios.router import router as usuarios_router

app.include_router(usuarios_router, prefix="/api/v1")
app.include_router(condominios_router, prefix="/api/v1")
app.include_router(cuotas_router, prefix="/api/v1")
app.include_router(pagos_router, prefix="/api/v1")
app.include_router(reservas_router, prefix="/api/v1")
app.include_router(notificaciones_router, prefix="/api/v1")


@app.get("/health", tags=["Sistema"])
@app.get("/api/v1/health", tags=["Sistema"])
async def health_check():
    """Endpoint de comprobación de salud del servicio."""
    return {
        "status": "ok",
        "service": "CondoManager Core API",
        "methodology": "Spec-Driven Development (SDD)",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
