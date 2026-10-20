"""Altas, estado operativo e importación reintentable de la estructura inmobiliaria."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from src.core.audit import AuditoriaPayload
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.estructura.importacion import leer_csv
from src.modules.condominios.estructura.repository import EstructuraRepository
from src.modules.condominios.estructura.schemas import (
    CrearDepartamentoRequest,
    CrearEdificioRequest,
    DepartamentoResponse,
    EdificioResponse,
    ImportacionResponse,
)
from src.modules.condominios.models import Departamento, Edificio


@dataclass(frozen=True)
class ActorEstructura:
    id: str
    rol: str
    condominio_id: UUID | None


class EstructuraService:
    def __init__(self, repository: EstructuraRepository):
        self.repo = repository

    async def autorizar(self, condominio_id, actor, escritura=False):
        roles = (
            {"SUPERADMIN", "ADMIN_JUNTA"} if escritura else {"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"}
        )
        if actor.rol not in roles or (
            actor.rol != "SUPERADMIN" and actor.condominio_id != condominio_id
        ):
            raise APIError(403, "ESTRUCTURA_ACCESO_DENEGADO", "No puede operar en este condominio.")
        if await self.repo.contexto(condominio_id, escritura) is None:
            raise APIError(
                404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo con ese UUID."
            )

    async def listar_edificios(self, condominio_id, actor):
        await self.autorizar(condominio_id, actor)
        return await self.repo.edificios(condominio_id)

    async def listar_departamentos(self, condominio_id, actor, edificio_id=None, activo=None):
        await self.autorizar(condominio_id, actor)
        if edificio_id is not None:
            await self._edificio(condominio_id, edificio_id)
        return await self.repo.departamentos(condominio_id, edificio_id, activo)

    async def _edificio(self, condominio_id, edificio_id):
        edificio = await self.repo.edificio(condominio_id, edificio_id)
        if edificio is None:
            raise APIError(
                404, "EDIFICIO_NO_ENCONTRADO", "El edificio no existe en este condominio."
            )
        return edificio

    async def _guardar(self, condominio_id, actor, recurso, accion, anterior=None):
        es_departamento = isinstance(recurso, Departamento)
        esquema = DepartamentoResponse if es_departamento else EdificioResponse
        payload = AuditoriaPayload(
            condominio_id=str(condominio_id),
            departamento_id=str(recurso.id) if es_departamento else None,
            accion_ejecutada=accion,
            motivo="GESTION_ESTRUCTURA_INMOBILIARIA",
            resultado="EXITOSO",
            actor_tipo=actor.rol,
            actor_id=actor.id,
            estado_anterior=anterior or {},
            estado_posterior=esquema.model_validate(recurso).model_dump(mode="json"),
            hash_previo=await self.repo.ultimo_hash(condominio_id),
        )
        auditoria = AuditoriaLogORM(
            condominio_id=condominio_id,
            departamento_id=recurso.id if es_departamento else None,
            timestamp=payload.timestamp,
            accion_ejecutada=accion,
            motivo=payload.motivo,
            resultado=payload.resultado,
            actor_tipo=actor.rol,
            actor_id=actor.id,
            estado_anterior=payload.estado_anterior,
            estado_posterior=payload.estado_posterior,
            hash_previo=payload.hash_previo,
            hash_actual=payload.calcular_hash(),
        )
        try:
            return await self.repo.guardar(recurso, auditoria)
        except IntegrityError as exc:
            # Solo las colisiones de identidad se presentan como errores de datos;
            # fallos de auditoría/checks inesperados deben revertir la solicitud.
            nombre = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", "") or ""
            if nombre in {
                "uq_edificio_condominio_bloque",
                "uq_edificio_departamento",
                "uq_edificio_nombre_normalizado",
                "uq_departamento_numero_normalizado",
            }:
                raise APIError(
                    409, "ESTRUCTURA_DUPLICADA", "El edificio o departamento ya existe."
                ) from exc
            raise

    async def crear_edificio(self, condominio_id, request, actor):
        await self.autorizar(condominio_id, actor, True)
        if any(
            e.nombre_bloque.strip().lower() == request.nombre_bloque.lower()
            for e in await self.repo.edificios(condominio_id)
        ):
            raise APIError(409, "EDIFICIO_DUPLICADO", "Ya existe un edificio con ese nombre.")
        edificio = Edificio(id=uuid4(), condominio_id=condominio_id, **request.model_dump())
        return await self._guardar(condominio_id, actor, edificio, "EDIFICIO_CREADO")

    async def crear_departamento(self, condominio_id, edificio_id, request, actor):
        await self.autorizar(condominio_id, actor, True)
        edificio = await self._edificio(condominio_id, edificio_id)
        if request.piso > edificio.total_pisos:
            raise APIError(422, "PISO_INVALIDO", "El piso supera el total de pisos del edificio.")
        if any(
            d.numero.strip().upper() == request.numero
            for d in await self.repo.departamentos(condominio_id, edificio_id)
        ):
            raise APIError(409, "DEPARTAMENTO_DUPLICADO", "El número ya existe en este edificio.")
        departamento = Departamento(
            id=uuid4(),
            edificio_id=edificio_id,
            **request.model_dump(),
            saldo_a_favor=Decimal("0.00"),
            estado_financiero="AL_DIA",
            activo=True,
        )
        return await self._guardar(condominio_id, actor, departamento, "DEPARTAMENTO_CREADO")

    async def cambiar_estado(self, condominio_id, departamento_id, activo, actor):
        await self.autorizar(condominio_id, actor, True)
        departamento = await self.repo.departamento(condominio_id, departamento_id)
        if departamento is None:
            raise APIError(
                404, "DEPARTAMENTO_NO_ENCONTRADO", "La unidad no existe en este condominio."
            )
        if departamento.activo == activo:
            return departamento
        anterior = DepartamentoResponse.model_validate(departamento).model_dump(mode="json")
        departamento.activo = activo
        return await self._guardar(
            condominio_id, actor, departamento, "DEPARTAMENTO_ESTADO_CAMBIADO", anterior
        )

    async def importar(self, condominio_id, contenido, actor, confirmar=False):
        # Incluso la vista previa es administrativa; no concede escritura al auditor.
        await self.autorizar(condominio_id, actor, True)
        filas = leer_csv(contenido)
        edificios = {
            e.nombre_bloque.strip().lower(): e for e in await self.repo.edificios(condominio_id)
        }
        departamentos = {
            (d.edificio_id, d.numero.strip().upper()): d
            for d in await self.repo.departamentos(condominio_id)
        }
        grupos = defaultdict(list)
        identidades = defaultdict(list)
        for fila in filas:
            grupos[fila.edificio.lower()].append(fila)
            identidades[(fila.edificio.lower(), fila.numero)].append(fila)
        for clave, grupo in grupos.items():
            declarados = {f.total_pisos for f in grupo if f.total_pisos is not None}
            edificio = edificios.get(clave)
            total = edificio.total_pisos if edificio else next(iter(declarados), None)
            for fila in grupo:
                if len(declarados) > 1 or (edificio and declarados and declarados != {total}):
                    fila.errores.append("total_pisos inconsistente para el edificio.")
                elif total is None:
                    fila.errores.append("Declare total_pisos para crear el edificio.")
                elif fila.piso is not None and fila.piso > total:
                    fila.errores.append("El piso supera total_pisos del edificio.")
                fila.total_pisos = total
        for grupo in identidades.values():
            if len({(f.piso, f.coeficiente) for f in grupo}) > 1:
                for fila in grupo:
                    fila.errores.append("El archivo repite la unidad con datos diferentes.")

        vistas = set()
        for fila in filas:
            if fila.errores:
                fila.estado = "ERROR"
                continue
            clave = fila.edificio.lower()
            edificio = edificios.get(clave)
            existente = departamentos.get((edificio.id, fila.numero)) if edificio else None
            if existente and (
                existente.piso != fila.piso
                or existente.coeficiente_participacion != Decimal(fila.coeficiente)
            ):
                fila.errores.append("La unidad existe con piso o coeficiente diferente.")
                fila.estado = "ERROR"
            elif existente or (clave, fila.numero) in vistas:
                fila.estado = "YA_EXISTENTE"
            elif confirmar:
                try:
                    if edificio is None:
                        edificio = await self.crear_edificio(
                            condominio_id,
                            CrearEdificioRequest(
                                nombre_bloque=fila.edificio, total_pisos=fila.total_pisos
                            ),
                            actor,
                        )
                        edificios[clave] = edificio
                    departamento = await self.crear_departamento(
                        condominio_id,
                        edificio.id,
                        CrearDepartamentoRequest(
                            numero=fila.numero,
                            piso=fila.piso,
                            coeficiente_participacion=fila.coeficiente,
                        ),
                        actor,
                    )
                    departamentos[(edificio.id, fila.numero)] = departamento
                    fila.estado = "CREADA"
                except APIError as exc:
                    if exc.status_code not in {409, 422}:
                        raise
                    fila.errores.append(exc.mensaje)
                    fila.estado = "ERROR"
            if fila.estado != "ERROR":
                vistas.add((clave, fila.numero))
        return ImportacionResponse(
            total_filas=len(filas),
            nuevas=sum(f.estado == "NUEVA" for f in filas),
            creadas=sum(f.estado == "CREADA" for f in filas),
            ya_existentes=sum(f.estado == "YA_EXISTENTE" for f in filas),
            rechazadas=sum(f.estado == "ERROR" for f in filas),
            filas=filas,
        )
