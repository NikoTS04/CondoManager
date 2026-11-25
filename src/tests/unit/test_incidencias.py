from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError

from src.modules.incidencias.estados import transicion_permitida
from src.modules.incidencias.schemas import (
    AsignarIncidencia,
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


def test_la_maquina_de_estados_solo_admite_las_transiciones_definidas():
    assert transicion_permitida("REGISTRADO", "ASIGNADO")
    assert transicion_permitida("ASIGNADO", "ASIGNADO")
    assert transicion_permitida("RESUELTO", "EN_PROCESO")
    assert not transicion_permitida("RECHAZADO", "ASIGNADO")
    assert not transicion_permitida("CERRADO", "RESUELTO")


def test_la_asignacion_exige_un_solo_responsable_y_plazo_con_zona():
    plazo = datetime.now(UTC) + timedelta(days=2)
    con_interno = AsignarIncidencia(version=1, responsable_usuario_id=uuid4(), plazo=plazo)
    assert con_interno.responsable_proveedor_id is None
    con_proveedor = AsignarIncidencia(
        version=1,
        responsable_proveedor_id=uuid4(),
        proveedor_nombre="Servicios del Norte",
        correo_proveedor="contacto@ejemplo.test",
        plazo=plazo,
    )
    assert con_proveedor.responsable_usuario_id is None
    with pytest.raises(ValidationError):
        AsignarIncidencia(
            version=1,
            responsable_usuario_id=uuid4(),
            responsable_proveedor_id=uuid4(),
            plazo=plazo,
        )
    sin_correo = AsignarIncidencia(
        version=1,
        responsable_proveedor_id=uuid4(),
        proveedor_nombre="Servicios del Norte",
        plazo=plazo,
    )
    assert sin_correo.correo_proveedor is None
    with pytest.raises(ValidationError):
        AsignarIncidencia(
            version=1, responsable_usuario_id=uuid4(), plazo=plazo.replace(tzinfo=None)
        )


def test_migracion_0027_es_la_cabeza_sobre_la_0026():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_revision("20261127_0027").down_revision == "20261126_0026"
    assert scripts.get_heads() == ["20261127_0027"]
