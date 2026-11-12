"""Catálogo aislado para pruebas de otros dominios; CON-39 utiliza PostgreSQL real."""

from types import SimpleNamespace

from scripts.seed_areas_demo import areas_demo
from src.modules.reservas.areas.models import AreaComun
from src.modules.reservas.areas.repository import AreasRepository


class AreasCatalogoFake:
    def __init__(self):
        self.datos = {datos["id"]: AreaComun(**datos) for datos in areas_demo()}
        self.auditorias = []

    async def contexto(self, cid, bloquear=False):
        return SimpleNamespace(id=cid, moneda="PEN", activo=True)

    async def validar_actor(self, actor):
        return actor

    async def area(self, cid, aid, bloquear=False):
        area = self.datos.get(aid)
        return area if area is not None and area.condominio_id == cid else None

    async def area_global(self, aid):
        return self.datos.get(aid)

    async def ocupaciones(self, aid, cid, fecha):
        return []

    async def edificio(self, cid, eid):
        return None

    async def edificios_usuario(self, cid, uid):
        return set()

    async def presentar(self, area, moneda):
        return AreasRepository.representar(area, moneda)

    async def listar(self, cid, moneda, *, activa=None, limit=None, offset=0, residente=None):
        valores = sorted(
            (
                area
                for area in self.datos.values()
                if area.condominio_id == cid and (activa is None or area.esta_activa == activa)
            ),
            key=lambda a: (a.nombre, a.id),
        )
        if limit is not None:
            valores = valores[offset : offset + limit]
        return [await self.presentar(area, moneda) for area in valores]

    async def ultimo_hash(self, cid):
        return self.auditorias[-1].hash_actual if self.auditorias else None

    async def guardar(self, area, auditoria):
        self.datos[area.id] = area
        self.auditorias.append(auditoria)
