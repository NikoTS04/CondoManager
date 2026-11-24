"""Previsualización persistida y confirmación atómica de comunicaciones EMAIL."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from src.core.authorization import autorizar_condominio, contexto_consulta
from src.core.errors import APIError
from src.core.security import validar_sesion
from src.modules.condominios.models import Departamento, Edificio
from src.modules.notificaciones.models import Comunicado, ContactoBloqueado, Notificacion
from src.modules.notificaciones.repository import NotificacionesRepository
from src.modules.notificaciones.schemas import PrevisualizarComunicado
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository


class ComunicadosService:
    def __init__(self, session):
        self.db = session

    async def autorizar(self, usuario, cid):
        autorizar_condominio(usuario, cid, escritura=True)
        repo = SQLAlchemyUsuariosRepository(self.db)
        if await repo.contexto(cid, bloquear=True) is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el contexto.")
        await validar_sesion(usuario, repo)

    async def opciones(self, usuario, cid):
        cid = contexto_consulta(usuario, cid)
        async with self.db.begin():
            edificios = dict((await self.db.execute(
                select(Edificio.id, Edificio.nombre_bloque).where(Edificio.condominio_id == cid)
            )).all())
            return [{
                "usuario_id": str(u.id), "nombre": u.nombre, "email": email,
                "departamento_id": str(d.id), "departamento": d.numero,
                "edificio_id": str(d.edificio_id), "edificio": edificios[d.edificio_id],
            } for u, d, email in await NotificacionesRepository(self.db).destinatarios(cid)]

    async def audiencia(self, cid, datos):
        candidatos = await NotificacionesRepository(self.db).destinatarios(cid)
        edificios = set(await self.db.scalars(select(Edificio.id).where(Edificio.condominio_id == cid)))
        departamentos = set(await self.db.scalars(
            select(Departamento.id).join(Edificio).where(Edificio.condominio_id == cid)
        ))
        usuarios = {u.id for u, _, _ in candidatos}
        for pedidos, permitidos in (
            (datos.edificio_ids, edificios), (datos.departamento_ids, departamentos),
            (datos.usuario_ids, usuarios),
        ):
            if not set(pedidos) <= permitidos:
                raise APIError(422, "AUDIENCIA_INVALIDA", "La selección no pertenece al contexto activo.")
        bloqueados = set(await self.db.scalars(
            select(ContactoBloqueado.email).where(ContactoBloqueado.condominio_id == cid)
        ))
        seleccionados = {}
        for u, d, email in candidatos:
            if (
                (datos.edificio_ids and d.edificio_id not in datos.edificio_ids)
                or (datos.departamento_ids and d.id not in datos.departamento_ids)
                or (datos.usuario_ids and u.id not in datos.usuario_ids)
                or email.strip().lower() in bloqueados
            ):
                continue
            # Un comunicado general es por usuario, aunque tenga varias unidades.
            seleccionados.setdefault(str(u.id), {
                "usuario_id": str(u.id), "departamento_id": str(d.id),
                "edificio_id": str(d.edificio_id),
                "email": email, "nombre": u.nombre, "departamento": d.numero,
            })
        return sorted(seleccionados.values(), key=lambda d: d["usuario_id"])

    @staticmethod
    def dto(lote):
        return {
            "id": str(lote.id), "condominio_id": str(lote.condominio_id),
            "contenido": lote.contenido, "destinatarios": lote.audiencia,
            "cantidad": len(lote.audiencia), "creado_en": lote.creado_en,
            "confirmado_en": lote.confirmado_en,
        }

    async def previsualizar(self, usuario, datos):
        cid = UUID(str(datos.condominio_id))
        async with self.db.begin():
            await self.autorizar(usuario, cid)
            lote = Comunicado(
                condominio_id=cid, contenido=datos.model_dump(mode="json"),
                audiencia=await self.audiencia(cid, datos), creado_en=datetime.now(UTC),
            )
            self.db.add(lote)
            await self.db.flush()
            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario, cid, None, "COMUNICADO_PREVISUALIZADO", "SELECCION_ADMINISTRATIVA",
                {}, {"comunicado_id": str(lote.id), "cantidad": len(lote.audiencia)},
            )
            return self.dto(lote)

    async def confirmar(self, usuario, id):
        async with self.db.begin():
            lote = await self.db.get(Comunicado, id)
            if lote is None:
                raise APIError(404, "COMUNICADO_NO_ENCONTRADO", "No existe el comunicado.")
            await self.autorizar(usuario, lote.condominio_id)
            lote = await self.db.scalar(
                select(Comunicado).where(Comunicado.id == id).with_for_update()
                .execution_options(populate_existing=True)
            )
            if lote.confirmado_en:
                return self.dto(lote)
            if datetime.now(UTC) > lote.creado_en + timedelta(minutes=15):
                raise APIError(409, "PREVISUALIZACION_CADUCADA", "Previsualice nuevamente.")
            datos = PrevisualizarComunicado.model_validate(lote.contenido)
            if await self.audiencia(lote.condominio_id, datos) != lote.audiencia:
                raise APIError(409, "AUDIENCIA_CAMBIADA", "Los contactos cambiaron; previsualice nuevamente.")
            if not lote.audiencia:
                raise APIError(422, "AUDIENCIA_VACIA", "No hay destinatarios elegibles.")
            repo = NotificacionesRepository(self.db)
            from src.modules.usuarios.models import Usuario
            for destino in lote.audiencia:
                await repo.encolar(
                    cid=lote.condominio_id, did=UUID(destino["departamento_id"]),
                    usuario=await self.db.get(Usuario, UUID(destino["usuario_id"])),
                    contacto=destino["email"], evento=lote.id,
                    operacion=lote.id, tipo="NOTIF_COMUNICADO_GENERAL", canal="EMAIL",
                    contexto={"titulo": datos.titulo, "mensaje": datos.mensaje, "remitente": datos.remitente},
                )
            lote.confirmado_en = datetime.now(UTC)
            await SQLAlchemyPagosRepository(self.db).auditar(
                usuario, lote.condominio_id, None, "COMUNICADO_CONFIRMADO",
                "AUDIENCIA_PREVISUALIZADA", {"estado": "BORRADOR"},
                {"estado": "EN_COLA", "comunicado_id": str(id), "cantidad": len(lote.audiencia)},
            )
            return self.dto(lote)

    async def listar(self, usuario, cid):
        cid = contexto_consulta(usuario, cid)
        async with self.db.begin():
            lotes = list(await self.db.scalars(
                select(Comunicado).where(Comunicado.condominio_id == cid)
                .order_by(Comunicado.creado_en.desc(), Comunicado.id).limit(50)
            ))
            conteos = (await self.db.execute(
                select(Notificacion.evento_id, Notificacion.estado, func.count())
                .where(Notificacion.condominio_id == cid, Notificacion.evento_id.in_([lote.id for lote in lotes]))
                .group_by(Notificacion.evento_id, Notificacion.estado)
            )).all()
            return [{
                **self.dto(lote), "conteos": {e: n for id, e, n in conteos if id == lote.id}
            } for lote in lotes]
