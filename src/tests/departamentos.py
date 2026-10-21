"""Catálogo aislado para probar otros dominios sin sustituir las pruebas SQL de CON-05."""

from copy import deepcopy
from uuid import uuid5

from src.core.authorization import puede_ver_departamento
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, DEPARTAMENTOS_PILOTO


class CatalogoDepartamentosFake:
    def __init__(self):
        self.datos = deepcopy(DEPARTAMENTOS_PILOTO)
        for departamento in self.datos.values():
            departamento.update(
                edificio_id=uuid5(CONDOMINIO_PILOTO_ID, "edificio:piloto"),
                edificio_nombre="Torre piloto",
            )

    async def listar(self, cid, actor):
        return [
            d
            for d in self.datos.values()
            if d["condominio_id"] == cid and d["activo"] and puede_ver_departamento(actor, d["id"])
        ]

    async def obtener(self, did):
        return self.datos.get(str(did))
