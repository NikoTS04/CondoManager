"""Punto de entrada principal de la API de CondoManager."""

from fastapi import FastAPI
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


@app.get("/health", tags=["Sistema"])
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
