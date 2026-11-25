"""Contrato de avisos del Sprint 4: plantillas, variables obligatorias y claves."""

from pathlib import Path
from uuid import uuid4

import pytest

from src.modules.notificaciones.avisos_contrato import (
    AVISO_ASIGNACION_PROVEEDOR,
    AVISO_ASIGNACION_RESIDENTE,
    AVISO_INCIDENCIA_REGISTRADA,
    AVISO_RESERVA_AFECTADA,
    RolAvisoAsignacion,
    clave_asignacion,
    clave_incidencia_registrada,
    clave_reserva_afectada,
)
from src.modules.notificaciones.templates import PlantillaIncompletaError, PlantillasService

RAIZ = Path(__file__).resolve().parents[3]

CONTEXTOS = {
    AVISO_INCIDENCIA_REGISTRADA: {"incidencia_id": "inc-1", "enlace": "https://portal.example/i/1"},
    AVISO_RESERVA_AFECTADA: {
        "nombre": "Ana",
        "dpto": "502",
        "area": "Parrilla 1",
        "fecha": "2026-12-05",
        "horario": "19:00–22:00 (America/Lima)",
        "motivo": "Mantenimiento de la red de gas",
        "enlace": "https://portal.example/reservas",
    },
    AVISO_ASIGNACION_RESIDENTE: {
        "nombre": "Ana",
        "dpto": "502",
        "codigo_ticket": "inc-1",
        "estado": "ASIGNADO",
        "enlace": "https://portal.example/incidencias/inc-1",
    },
    AVISO_ASIGNACION_PROVEEDOR: {
        "proveedor": "Servicios Eléctricos SAC",
        "codigo_ticket": "inc-1",
        "condominio": "Villa Bonita 3",
        "ubicacion": "Pasillo piso 2",
        "categoria": "Iluminación",
        "prioridad": "ALTA",
        "descripcion": "Luminaria averiada",
        "plazo": "2026-12-05",
    },
}


@pytest.mark.parametrize("tipo", sorted(CONTEXTOS))
def test_cada_aviso_renderiza_con_todas_sus_variables(tipo):
    asunto, cuerpo = PlantillasService.renderizar(tipo, CONTEXTOS[tipo])
    assert asunto and cuerpo
    assert "{" not in asunto and "}" not in cuerpo


@pytest.mark.parametrize("tipo", sorted(CONTEXTOS))
def test_las_variables_obligatorias_son_exactamente_las_del_contrato(tipo):
    assert PlantillasService.variables_requeridas(tipo) == sorted(CONTEXTOS[tipo])


@pytest.mark.parametrize(
    ("tipo", "variable"),
    [(t, v) for t, ctx in sorted(CONTEXTOS.items()) for v in sorted(ctx)],
)
def test_un_dato_faltante_impide_el_aviso_sin_filtrar_valores(tipo, variable):
    contexto = {**CONTEXTOS[tipo], variable: "   "}
    with pytest.raises(PlantillaIncompletaError) as error:
        PlantillasService.renderizar(tipo, contexto)
    assert error.value.faltantes == [variable]
    assert "Parrilla 1" not in str(error.value)


def test_el_aviso_al_proveedor_trae_codigo_datos_y_plazo():
    _, cuerpo = PlantillasService.renderizar(
        AVISO_ASIGNACION_PROVEEDOR, CONTEXTOS[AVISO_ASIGNACION_PROVEEDOR]
    )
    for dato in ("inc-1", "Pasillo piso 2", "Luminaria averiada", "2026-12-05"):
        assert dato in cuerpo


def test_el_aviso_al_proveedor_no_expone_datos_del_residente():
    assert not {"nombre", "dpto", "reportante", "telefono", "email"} & set(
        PlantillasService.variables_requeridas(AVISO_ASIGNACION_PROVEEDOR)
    )


def test_clave_de_incidencia_usa_el_id_como_evento_y_operacion():
    incidencia = uuid4()
    clave = clave_incidencia_registrada(incidencia)
    assert clave.evento_id == clave.operacion_id == incidencia


def test_clave_de_reserva_afectada_es_estable_y_distingue_reservas_y_bloqueos():
    bloqueo, reserva = uuid4(), uuid4()
    assert clave_reserva_afectada(bloqueo, reserva) == clave_reserva_afectada(bloqueo, reserva)
    assert clave_reserva_afectada(bloqueo, reserva) != clave_reserva_afectada(bloqueo, uuid4())
    assert clave_reserva_afectada(bloqueo, reserva) != clave_reserva_afectada(uuid4(), reserva)


def test_clave_de_asignacion_es_estable_y_distingue_rol_y_asignacion():
    asignacion = uuid4()
    residente = clave_asignacion(asignacion, RolAvisoAsignacion.RESIDENTE)
    proveedor = clave_asignacion(asignacion, "PROVEEDOR")
    assert residente == clave_asignacion(asignacion, "RESIDENTE")
    assert residente.evento_id == proveedor.evento_id == asignacion
    assert residente.operacion_id != proveedor.operacion_id
    assert clave_asignacion(uuid4(), "RESIDENTE").operacion_id != residente.operacion_id


def test_clave_de_asignacion_rechaza_un_rol_desconocido():
    with pytest.raises(ValueError):
        clave_asignacion(uuid4(), "VECINO")


def test_el_catalogo_y_los_escenarios_documentan_cada_aviso():
    catalogo = (RAIZ / "specs/03-contracts/events/domain-events-catalog.md").read_text("utf-8")
    escenarios = (RAIZ / "specs/04-acceptance-criteria/avisos-sprint-4.feature.md").read_text(
        "utf-8"
    )
    for tipo in CONTEXTOS:
        assert tipo in catalogo, tipo
        assert tipo in escenarios, tipo
