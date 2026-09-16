"""Módulo de Auditoría y Trazabilidad Inmutable (Audit & Traceability).

Implementa los 7 campos mínimos obligatorios para todo evento del sistema:
1. departamento_id
2. timestamp
3. accion_ejecutada
4. motivo
5. resultado
6. estado_anterior
7. estado_posterior
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditoriaPayload(BaseModel):
    condominio_id: str
    departamento_id: Optional[str] = Field(None, description="Departamento involucrado o CONDOMINIO_GENERAL")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accion_ejecutada: str = Field(..., description="Código estándar de la acción")
    motivo: str = Field(..., description="Motivo o regla de negocio aplicada")
    resultado: str = Field(..., description="EXITOSO o FALLIDO")
    actor_tipo: str = Field("SISTEMA_AUTOMATICO", description="SISTEMA_AUTOMATICO, ADMINISTRADOR, RESIDENTE")
    actor_id: str = Field("SYSTEM_WORKER", description="Identificador del usuario o proceso")
    estado_anterior: Dict[str, Any] = Field(default_factory=dict)
    estado_posterior: Dict[str, Any] = Field(default_factory=dict)
    hash_previo: Optional[str] = None
    hash_actual: Optional[str] = None

    def calcular_hash(self) -> str:
        """Genera el hash criptográfico SHA-256 encadenado para garantizar inmutabilidad."""
        payload = {
            "condominio_id": self.condominio_id,
            "departamento_id": self.departamento_id,
            "timestamp": self.timestamp.isoformat(),
            "accion": self.accion_ejecutada,
            "motivo": self.motivo,
            "resultado": self.resultado,
            "anterior": self.estado_anterior,
            "posterior": self.estado_posterior,
            "hash_previo": self.hash_previo or "",
        }
        cadena = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()
