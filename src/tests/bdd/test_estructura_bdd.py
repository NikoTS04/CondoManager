"""Escenarios ejecutables de CON-3 sobre los casos de uso; persistencia en test_estructura_db."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from pytest_bdd import given, scenarios, then, when

from src.core.errors import APIError
from src.modules.condominios.estructura.schemas import (
    CrearDepartamentoRequest,
    CrearEdificioRequest,
)
from src.modules.condominios.estructura.service import ActorEstructura, EstructuraService

scenarios(
    str(
        Path(__file__).resolve().parents[3]
        / "specs/02-domains/05-usuarios-rbac/features/estructura.feature"
    )
)


class RepositorioEscenario:
    def __init__(self):
        self.id = uuid4()
        self.torres = []
        self.unidades = []
        self.auditorias = []

    async def contexto(self, cid, escritura=False):
        return self if cid == self.id else None

    async def edificios(self, cid):
        return self.torres

    async def edificio(self, cid, eid):
        return next((e for e in self.torres if e.id == eid and e.condominio_id == cid), None)

    async def departamentos(self, cid, eid=None, activo=None):
        return [
            d
            for d in self.unidades
            if (eid is None or d.edificio_id == eid) and (activo is None or d.activo == activo)
        ]

    async def departamento(self, cid, did):
        return next((d for d in self.unidades if d.id == did), None)

    async def ultimo_hash(self, cid):
        return self.auditorias[-1].hash_actual if self.auditorias else None

    async def guardar(self, recurso, auditoria):
        coleccion = self.unidades if hasattr(recurso, "numero") else self.torres
        if recurso not in coleccion:
            coleccion.append(recurso)
        self.auditorias.append(auditoria)
        return recurso


@given("un administrador con dos edificios en su condominio", target_fixture="contexto")
def contexto():
    repo = RepositorioEscenario()
    service = EstructuraService(repo)
    actor = ActorEstructura("administrador", "ADMIN_JUNTA", repo.id)
    for nombre in ("Norte", "Sur"):
        asyncio.run(
            service.crear_edificio(
                repo.id, CrearEdificioRequest(nombre_bloque=nombre, total_pisos=2), actor
            )
        )
    return {"repo": repo, "service": service, "actor": actor}


def registrar(contexto, indice=0):
    r = contexto["repo"]
    return asyncio.run(
        contexto["service"].crear_departamento(
            r.id,
            r.torres[indice].id,
            CrearDepartamentoRequest(numero="101", piso=1, coeficiente_participacion="50.0000"),
            contexto["actor"],
        )
    )


@when("registra el departamento 101 en ambos edificios")
def dos_unidades(contexto):
    registrar(contexto)
    registrar(contexto, 1)


@then("ambas unidades tienen UUID diferentes")
def diferentes(contexto):
    assert len({d.id for d in contexto["repo"].unidades}) == 2


@then("repetir el número en el primer edificio produce conflicto")
def duplicado(contexto):
    with pytest.raises(APIError) as error:
        registrar(contexto)
    assert error.value.status_code == 409


def importar(contexto):
    contenido = b"numero,piso,edificio,coeficiente\n101,1,Norte,50\n102,3,Norte,50\n"
    return asyncio.run(
        contexto["service"].importar(contexto["repo"].id, contenido, contexto["actor"], True)
    )


@when("importa un CSV con una unidad válida y otra con piso inválido")
def importar_csv(contexto):
    contexto["resultado"] = importar(contexto)


@then("se crea una unidad y se informa una fila inválida")
def parcial(contexto):
    assert contexto["resultado"].creadas == contexto["resultado"].rechazadas == 1


@then("reintentar el archivo no duplica la unidad válida")
def reintento(contexto):
    resultado = importar(contexto)
    assert resultado.creadas == 0 and resultado.ya_existentes == 1
    assert len(contexto["repo"].unidades) == 1


@when("registra y desactiva un departamento")
def desactivar(contexto):
    d = registrar(contexto)
    contexto["uuid"] = d.id
    for _ in range(2):
        asyncio.run(
            contexto["service"].cambiar_estado(contexto["repo"].id, d.id, False, contexto["actor"])
        )


@then("conserva su UUID y registra un único cambio de estado")
def estado(contexto):
    d = contexto["repo"].unidades[0]
    assert d.id == contexto["uuid"] and d.activo is False
    assert (
        sum(
            a.accion_ejecutada == "DEPARTAMENTO_ESTADO_CAMBIADO"
            for a in contexto["repo"].auditorias
        )
        == 1
    )
