"""Destinatarios SQL y cola contextual, sin contactos inventados del piloto."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.core.authorization import contexto_consulta, vinculos_activos
from src.modules.condominios.models import Departamento, Edificio
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.templates import PlantillasService
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol


class NotificacionesRepository:
    def __init__(self, session):
        self.session = session

    async def destinatarios(self, cid, did=None, canal="EMAIL"):
        query = (
            select(Usuario, Departamento)
            .join(UsuarioDepartamento, UsuarioDepartamento.usuario_id == Usuario.id)
            .join(Departamento, Departamento.id == UsuarioDepartamento.departamento_id)
            .join(Edificio, Edificio.id == Departamento.edificio_id)
            .join(
                UsuarioRol,
                (UsuarioRol.usuario_id == Usuario.id)
                & (UsuarioRol.condominio_id == Edificio.condominio_id),
            )
            .where(
                Edificio.condominio_id == cid,
                Usuario.esta_activo.is_(True),
                UsuarioDepartamento.es_activo.is_(True),
                Departamento.activo.is_(True),
                UsuarioRol.es_activo.is_(True),
            )
            .order_by(Departamento.id, Usuario.id)
        )
        if did:
            query = query.where(Departamento.id == did)
        return [
            (u, d, u.email if canal == "EMAIL" else u.telefono)
            for u, d in (await self.session.execute(query)).all()
            if (u.email if canal == "EMAIL" else u.telefono)
        ]

    async def encolar(
        self, *, cid, did, usuario, contacto, evento, operacion, tipo, canal, contexto
    ):
        asunto, cuerpo = PlantillasService.renderizar(tipo, contexto)
        id = uuid4()
        await self.session.execute(
            insert(Notificacion)
            .values(
                id=id,
                condominio_id=cid,
                departamento_id=did,
                usuario_destinatario_id=usuario.id,
                evento_id=evento,
                operacion_id=operacion,
                tipo_evento=tipo,
                canal=canal,
                destinatario=contacto,
                asunto=asunto,
                cuerpo=cuerpo,
                estado="EN_COLA",
                transporte="SIMULADO",
                ciclo=1,
                intentos=0,
            )
            .on_conflict_do_nothing(constraint="uq_notificacion_logica")
        )
        return await self.session.scalar(
            select(Notificacion).where(
                Notificacion.evento_id == evento,
                Notificacion.operacion_id == operacion,
                Notificacion.usuario_destinatario_id == usuario.id,
                Notificacion.canal == canal,
            )
        )

    async def listar(self, usuario, cid=None, did=None, estado=None, canal=None):
        cid = contexto_consulta(usuario, cid)
        query = select(Notificacion).where(Notificacion.condominio_id == cid)
        if usuario["rol"] == "RESIDENTE":
            query = query.where(
                Notificacion.usuario_destinatario_id == UUID(usuario["sub"]),
                Notificacion.departamento_id.in_(vinculos_activos(usuario)),
            )
        for columna, valor in (
            (Notificacion.departamento_id, did),
            (Notificacion.estado, estado),
            (Notificacion.canal, canal),
        ):
            if valor is not None:
                query = query.where(columna == valor)
        return list(
            await self.session.scalars(
                query.order_by(Notificacion.fecha_creacion.desc(), Notificacion.id)
            )
        )
