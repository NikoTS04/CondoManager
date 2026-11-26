"""Módulo de Proveedores y Contratos (CON-48, CON-49)."""

from src.modules.proveedores.models import (
    ContratoProveedor,
    DocumentoContratoVersion,
    Proveedor,
)
from src.modules.proveedores.router import router as proveedores_router

__all__ = [
    "Proveedor",
    "ContratoProveedor",
    "DocumentoContratoVersion",
    "proveedores_router",
]
