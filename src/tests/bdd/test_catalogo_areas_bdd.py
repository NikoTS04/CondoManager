"""Especificación ejecutable CON-39 contra las rutas y PostgreSQL reales."""

import asyncio
from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from src.tests.bdd.test_alta_usuarios_bdd import ingresar
from src.tests.integration.test_alta_usuarios_db import otro_condominio
from src.tests.integration.test_catalogo_areas_db import auditorias, datos_area, ruta, turno

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/04-reservas/features/catalogo_areas.feature"
    )
)


@given("un condominio y una administración persistentes para áreas", target_fixture="areas")
def contexto(cliente_usuarios):
    client, base = cliente_usuarios
    return {
        "client": client,
        "base": base,
        "admin": ingresar(client),
        "residente": ingresar(client, "residente102@villabonita3.pe", "Residente123!"),
    }


@when("la administración crea un área con costo y horarios")
def crear(areas):
    response = areas["client"].post(ruta(areas["base"]), headers=areas["admin"], json=datos_area())
    assert response.status_code == 201
    areas["area"] = response.json()


@then("el residente consulta sus condiciones desde el catálogo SQL")
def catalogo(areas):
    response = areas["client"].get("/api/v1/areas", headers=areas["residente"])
    assert response.status_code == 200
    area = next(a for a in response.json() if a["id"] == areas["area"]["id"])
    assert area["costo_reserva"] == "35.75" and area["hora_apertura"] == "08:00"
    assert area["hora_cierre"] == "22:00" and area["zona_horaria"] == "America/Lima"


@when("un Auditor intenta crear un área")
def auditor(areas):
    headers = ingresar(areas["client"], "auditor@villabonita3.pe", "Auditor123!")
    areas["resultado"] = areas["client"].post(
        ruta(areas["base"]), headers=headers, json=datos_area()
    )
    assert areas["client"].get(ruta(areas["base"]), headers=headers).status_code == 200


@then("la API rechaza la escritura del catálogo")
@then("la API rechaza la operación ajena")
def denegado(areas):
    assert areas["resultado"].status_code == 403


@when("una Junta intenta consultar el catálogo de otro condominio")
def ajeno(areas):
    otro = asyncio.run(otro_condominio(areas["base"]))
    junta = ingresar(areas["client"], "admin@villabonita3.pe", "Admin123!")
    areas["resultado"] = areas["client"].get(f"/api/v1/condominios/{otro}/areas", headers=junta)


@when("se desactiva un área registrada")
def desactivar(areas):
    crear(areas)
    response = areas["client"].patch(
        ruta(areas["base"], areas["area"]["id"]) + "/estado",
        headers=areas["admin"],
        json={"esta_activa": False},
    )
    assert response.status_code == 200


@then("desaparece del catálogo activo pero conserva su registro administrativo")
def inactiva(areas):
    catalogo = areas["client"].get("/api/v1/areas", headers=areas["residente"]).json()
    assert areas["area"]["id"] not in {a["id"] for a in catalogo}
    assert (
        areas["client"]
        .get(ruta(areas["base"], areas["area"]["id"]), headers=areas["admin"])
        .json()["esta_activa"]
        is False
    )


@then("una nueva reserva en esa área es rechazada")
def rechazar(areas):
    response = areas["client"].post(
        "/api/v1/reservas",
        headers=areas["residente"],
        json=turno(areas["base"], areas["area"]["id"]),
    )
    assert response.status_code == 409 and response.json()["error_code"] == "AREA_INACTIVA"


@when("se solicita un turno fuera del horario permitido")
def horario(areas):
    crear(areas)
    areas["resultado"] = areas["client"].post(
        "/api/v1/reservas",
        headers=areas["residente"],
        json=turno(areas["base"], areas["area"]["id"], "07:00", "09:00"),
    )


@then("la API rechaza el turno sin ocupar el calendario")
def libre(areas):
    assert areas["resultado"].status_code == 400
    assert areas["resultado"].json()["detail"]["error_code"] == "HORARIO_INVALIDO"
    fecha = turno(areas["base"], areas["area"]["id"])["fecha_reserva"]
    assert (
        areas["client"]
        .get(
            f"/api/v1/areas/{areas['area']['id']}/disponibilidad?fecha={fecha}",
            headers=areas["residente"],
        )
        .json()
        == []
    )


@when("la administración repite la configuración del área")
def repetir(areas):
    crear(areas)
    assert (
        areas["client"]
        .put(ruta(areas["base"], areas["area"]["id"]), headers=areas["admin"], json=datos_area())
        .status_code
        == 200
    )


@then("solo el alta queda registrada en auditoría")
def unica(areas):
    logs = asyncio.run(auditorias(areas["base"]))
    assert len(logs) == 1 and logs[0].accion_ejecutada == "AREA_CREADA"
