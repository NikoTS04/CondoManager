from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.incidencias.schemas import CrearIncidencia


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
