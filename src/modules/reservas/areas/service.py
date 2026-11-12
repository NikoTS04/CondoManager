"""Catálogo SQL, condiciones de acceso y auditoría atómica de CON-39."""

from uuid import uuid4

from src.core.audit import AuditoriaPayload
from src.core.authorization import autorizar_condominio, contexto_consulta
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.reservas.areas.models import AreaComun


class AreasService:
    def __init__(self, repository):
        self.repo = repository

    async def _contexto(self, cid, actor, escritura=False):
        permitidos = (
            {"SUPERADMIN", "ADMIN_JUNTA"} if escritura else {"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"}
        )
        if actor["rol"] not in permitidos or (
            actor["rol"] != "SUPERADMIN" and str(cid) != actor.get("condominio_id")
        ):
            raise APIError(403, "ACCESO_DENEGADO", "No puede administrar áreas de este condominio.")
        contexto = await self.repo.contexto(cid, bloquear=escritura)
        if contexto is None:
            raise APIError(
                404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo con ese UUID."
            )
        if escritura:
            await self.repo.validar_actor(actor)
        return contexto

    async def _area(self, cid, aid, bloquear=False):
        area = await self.repo.area(cid, aid, bloquear)
        if area is None:
            raise APIError(404, "AREA_NO_ENCONTRADA", "El área no existe en este condominio.")
        return area

    async def _edificio(self, cid, eid):
        if eid is not None and await self.repo.edificio(cid, eid) is None:
            raise APIError(
                404, "EDIFICIO_NO_ENCONTRADO", "El edificio no existe en este condominio."
            )

    async def listar(self, cid, actor, limit=50, offset=0, activa=None):
        contexto = await self._contexto(cid, actor)
        return await self.repo.listar(
            cid, contexto.moneda, activa=activa, limit=limit, offset=offset
        )

    async def consultar(self, cid, aid, actor):
        contexto = await self._contexto(cid, actor)
        return await self.repo.presentar(await self._area(cid, aid), contexto.moneda)

    async def _guardar(self, contexto, area, actor, accion, anterior):
        posterior = await self.repo.presentar(area, contexto.moneda)
        payload = AuditoriaPayload(
            condominio_id=str(contexto.id),
            departamento_id=None,
            accion_ejecutada=accion,
            motivo="GESTION_CATALOGO_AREAS",
            resultado="EXITOSO",
            actor_tipo=actor["rol"],
            actor_id=actor["sub"],
            estado_anterior=anterior,
            estado_posterior=posterior.model_dump(mode="json"),
            hash_previo=await self.repo.ultimo_hash(contexto.id),
        )
        auditoria = AuditoriaLogORM(
            condominio_id=contexto.id,
            departamento_id=None,
            timestamp=payload.timestamp,
            accion_ejecutada=accion,
            motivo=payload.motivo,
            resultado=payload.resultado,
            actor_tipo=payload.actor_tipo,
            actor_id=payload.actor_id,
            estado_anterior=payload.estado_anterior,
            estado_posterior=payload.estado_posterior,
            hash_previo=payload.hash_previo,
            hash_actual=payload.calcular_hash(),
        )
        await self.repo.guardar(area, auditoria)
        return posterior

    async def crear(self, cid, request, actor):
        contexto = await self._contexto(cid, actor, True)
        await self._edificio(cid, request.edificio_id)
        area = AreaComun(id=uuid4(), condominio_id=cid, esta_activa=True, **request.datos_orm())
        return await self._guardar(contexto, area, actor, "AREA_CREADA", {})

    async def configurar(self, cid, aid, request, actor):
        contexto = await self._contexto(cid, actor, True)
        area = await self._area(cid, aid, True)
        await self._edificio(cid, request.edificio_id)
        datos = request.datos_orm()
        anterior = await self.repo.presentar(area, contexto.moneda)
        if all(getattr(area, campo) == valor for campo, valor in datos.items()):
            return anterior
        for campo, valor in datos.items():
            setattr(area, campo, valor)
        return await self._guardar(
            contexto, area, actor, "AREA_ACTUALIZADA", anterior.model_dump(mode="json")
        )

    async def estado(self, cid, aid, activa, actor):
        contexto = await self._contexto(cid, actor, True)
        area = await self._area(cid, aid, True)
        anterior = await self.repo.presentar(area, contexto.moneda)
        if area.esta_activa == activa:
            return anterior
        area.esta_activa = activa
        return await self._guardar(
            contexto, area, actor, "AREA_ESTADO_CAMBIADO", anterior.model_dump(mode="json")
        )

    async def catalogo(self, actor, condominio_id=None):
        cid = contexto_consulta(actor, condominio_id)
        contexto = await self.repo.contexto(cid)
        if contexto is None:
            raise APIError(
                404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo con ese UUID."
            )
        return await self.repo.listar(
            cid,
            contexto.moneda,
            activa=True,
            residente=actor["sub"] if actor["rol"] == "RESIDENTE" else None,
        )

    async def publica(self, aid, actor, *, bloquear=False, condominio_id=None):
        area = await self.repo.area_global(aid)
        if area is None:
            raise APIError(404, "AREA_NO_ENCONTRADA", "El área no existe.")
        autorizar_condominio(actor, area.condominio_id)
        if condominio_id is not None and area.condominio_id != condominio_id:
            raise APIError(403, "ACCESO_DENEGADO", "El área pertenece a otro condominio.")
        contexto = await self.repo.contexto(area.condominio_id, bloquear=bloquear)
        if contexto is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "El condominio no está activo.")
        if bloquear:
            await self.repo.validar_actor(actor)
        area = await self._area(area.condominio_id, aid, bloquear)
        if not area.esta_activa:
            raise APIError(
                409, "AREA_INACTIVA", "El área está inactiva y no admite nuevas reservas."
            )
        if (
            actor["rol"] == "RESIDENTE"
            and area.edificio_id is not None
            and area.edificio_id
            not in await self.repo.edificios_usuario(area.condominio_id, actor["sub"])
        ):
            raise APIError(403, "ACCESO_DENEGADO", "El área es exclusiva de otro edificio.")
        return await self.repo.presentar(area, contexto.moneda)

    async def verificar_historial(self, aid, actor):
        area = await self.repo.area_global(aid)
        if area is None:
            raise APIError(404, "AREA_NO_ENCONTRADA", "El área no existe.")
        autorizar_condominio(actor, area.condominio_id)
