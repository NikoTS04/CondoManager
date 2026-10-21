"""Identidades coherentes del catálogo en memoria; no sustituye el padrón SQL."""

from decimal import Decimal
from uuid import UUID, uuid5

from scripts.seed_condominio_piloto import generar_datos_departamentos
from src.core.config import settings

try:
    CONDOMINIO_PILOTO_ID = UUID(settings.CONDOMINIO_PILOTO_ID)
except (ValueError, TypeError, AttributeError):
    CONDOMINIO_PILOTO_ID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

DEPARTAMENTOS_PILOTO = {
    str(uuid5(CONDOMINIO_PILOTO_ID, d["numero"])): {
        **d,
        "id": uuid5(CONDOMINIO_PILOTO_ID, d["numero"]),
        "condominio_id": CONDOMINIO_PILOTO_ID,
        "activo": True,
        "deuda_vencida": Decimal("170.00" if d["estado_financiero"] == "EN_MORA" else "0.00"),
    }
    for d in generar_datos_departamentos()
}


def vinculo_piloto(numero: str, tipo_relacion: str, *, es_activo: bool = True) -> dict:
    return {
        "departamento_id": str(uuid5(CONDOMINIO_PILOTO_ID, numero)),
        "numero": numero,
        "tipo_relacion": tipo_relacion,
        "es_activo": es_activo,
    }
