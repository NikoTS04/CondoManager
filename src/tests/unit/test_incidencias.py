from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.incidencias.schemas import (
    ClasificarIncidencia,
    CrearIncidencia,
    RechazarIncidencia,
)


def test_ubicacion_vacia_es_invalida():
    with pytest.raises(ValidationError) as error:
        CrearIncidencia(
            departamento_id=uuid4(),
            ubicacion="  ",
            categoria="Iluminación",
            descripcion="Luminaria averiada",
            urgencia="MEDIA",
        )
    assert [detalle["loc"] for detalle in error.value.errors()] == [("ubicacion",)]


def test_rechazo_exige_un_motivo_con_texto():
    with pytest.raises(ValidationError) as error:
        RechazarIncidencia(accion="RECHAZAR", version=1, motivo="   ")
    assert [detalle["loc"] for detalle in error.value.errors()] == [("motivo",)]


def test_clasificacion_rechaza_una_prioridad_fuera_del_catalogo():
    with pytest.raises(ValidationError) as error:
        ClasificarIncidencia(
            accion="CLASIFICAR", version=1, categoria="Mantenimiento", prioridad="CRITICA"
        )
    assert [detalle["loc"] for detalle in error.value.errors()] == [("prioridad",)]
