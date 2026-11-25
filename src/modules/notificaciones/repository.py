"""Destinatarios SQL y cola contextual, sin contactos inventados del piloto."""

import os
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.core.authorization import contexto_consulta, vinculos_activos
from src.core.config import settings
from src.core.roles import RolUsuario
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.templates import PlantillasService
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol

AVISO_INCIDENCIA = "NOTIF_INCIDENCIA_REGISTRADA"


class NotificacionesRepository:
    def __init__(self, session):
        self.session = session

    async def destinatarios(self, cid, did=None, canal="EMAIL"):
        query = (
            select(Usuario, Departamento)
            .join(UsuarioDepartamento, UsuarioDepartamento.usuario_id == Usuario.id)
            .join(Departamento, Departamento.id == UsuarioDepartamento.departamento_id)
            .join(Edificio, Edificio.id == Departamento.edificio_id)
            .join(Condominio, Condominio.id == Edificio.condominio_id)
            .join(
                UsuarioRol,
                (UsuarioRol.usuario_id == Usuario.id)
                & (UsuarioRol.condominio_id == Edificio.condominio_id),
            )
            .where(
                Edificio.condominio_id == cid,
                Condominio.activo.is_(True),
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

    async def destinatarios_junta(self, cid):
        return list(await self.session.scalars(
            select(Usuario)
            .join(UsuarioRol)
            .join(Condominio, Condominio.id == UsuarioRol.condominio_id)
            .where(
                UsuarioRol.condominio_id == cid,
                UsuarioRol.rol == RolUsuario.ADMIN_JUNTA,
                UsuarioRol.es_activo.is_(True),
                Usuario.esta_activo.is_(True),
                Condominio.activo.is_(True),
            )
        ))

    async def destinatarios_operativos(self, aviso):
        if aviso.tipo_evento == AVISO_INCIDENCIA:
            return [(u, None, u.email) for u in await self.destinatarios_junta(aviso.condominio_id)]
        return await self.destinatarios(aviso.condominio_id, aviso.departamento_id, aviso.canal)

    async def encolar(
        self, *, cid, did, usuario, contacto, evento, operacion, tipo, canal, contexto,
        recordatorio_vencimiento=None, recordatorio_dias=None,
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
                recordatorio_vencimiento=recordatorio_vencimiento,
                recordatorio_dias=recordatorio_dias,
                estado="EN_COLA",
                transporte="PROVEEDOR" if canal == "EMAIL" and (
                    settings.MAILJET_ENABLED or settings.APP_ENV == "production"
                    or os.getenv("VERCEL_ENV") == "production"
                ) else "SIMULADO",
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
