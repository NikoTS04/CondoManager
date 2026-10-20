"""Persistencia de identidad, contexto, vínculos y auditoría de CON-04."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.modules.usuarios.schemas import (
    CuentaUsuarioConRolResponse,
    CuentaUsuarioResponse,
    UsuarioDTO,
    VinculoDepartamentoDTO,
)


class SQLAlchemyUsuariosRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def por_email(self, email: str) -> Usuario | None:
        return await self.session.scalar(
            select(Usuario).where(func.lower(func.btrim(Usuario.email)) == email.strip().lower())
        )

    async def por_id(self, usuario_id: UUID, *, bloquear=False) -> Usuario | None:
        query = (
            select(Usuario)
            .where(Usuario.id == usuario_id)
            .execution_options(populate_existing=True)
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def duplicado(self, email: str, documento: str) -> bool:
        return (
            await self.session.scalar(
                select(Usuario.id)
                .where(
                    or_(
                        func.lower(func.btrim(Usuario.email)) == email,
                        func.upper(func.btrim(Usuario.documento_identidad)) == documento,
                    )
                )
                .limit(1)
            )
            is not None
        )

    async def contextos(self, usuario_id: UUID) -> list[dict]:
        rows = await self.session.execute(
            select(Condominio.id, Condominio.nombre, UsuarioRol.rol)
            .join(UsuarioRol, UsuarioRol.condominio_id == Condominio.id)
            .where(
                UsuarioRol.usuario_id == usuario_id,
                UsuarioRol.es_activo.is_(True),
                Condominio.activo.is_(True),
                UsuarioRol.rol.in_(("ADMIN_JUNTA", "AUDITOR", "RESIDENTE")),
            )
            .order_by(Condominio.id)
        )
        return [{"id": str(cid), "nombre": nombre, "rol": rol} for cid, nombre, rol in rows]

    async def perfil(self, usuario: Usuario, condominio_id=None) -> UsuarioDTO | None:
        rol = "SUPERADMIN" if usuario.es_superadmin else None
        cid = None
        vinculos = []
        if not usuario.es_superadmin:
            contexto = next(
                (c for c in await self.contextos(usuario.id) if c["id"] == str(condominio_id)), None
            )
            if contexto is None:
                return None
            rol, cid = contexto["rol"], contexto["id"]
            rows = await self.session.execute(
                select(UsuarioDepartamento, Departamento)
                .join(Departamento, UsuarioDepartamento.departamento_id == Departamento.id)
                .join(Edificio, Departamento.edificio_id == Edificio.id)
                .where(
                    UsuarioDepartamento.usuario_id == usuario.id,
                    Edificio.condominio_id == UUID(cid),
                )
                .order_by(Departamento.id)
            )
            vinculos = [
                VinculoDepartamentoDTO(
                    departamento_id=depto.id,
                    numero=depto.numero,
                    tipo_relacion=vinculo.tipo_relacion,
                    es_activo=vinculo.es_activo and depto.activo,
                )
                for vinculo, depto in rows
            ]
        return UsuarioDTO(
            id=str(usuario.id),
            email=usuario.email,
            nombre=usuario.nombre,
            apellido=usuario.apellido,
            rol=rol,
            condominio_id=cid,
            departamentos=vinculos,
        )

    async def contexto(self, condominio_id: UUID, *, bloquear=False) -> Condominio | None:
        query = select(Condominio).where(
            Condominio.id == condominio_id, Condominio.activo.is_(True)
        )
        if bloquear:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def condominios_usuario(self, usuario_id: UUID) -> list[UUID]:
        return list(
            await self.session.scalars(
                select(UsuarioRol.condominio_id)
                .where(UsuarioRol.usuario_id == usuario_id)
                .order_by(UsuarioRol.condominio_id)
            )
        )

    async def bloquear_contextos(self, ids: list[UUID]):
        await self.session.execute(
            select(Condominio)
            .where(Condominio.id.in_(ids))
            .order_by(Condominio.id)
            .with_for_update()
        )

    async def rol_usuario(self, usuario_id: UUID, condominio_id: UUID) -> UsuarioRol | None:
        return await self.session.scalar(
            select(UsuarioRol)
            .where(UsuarioRol.usuario_id == usuario_id, UsuarioRol.condominio_id == condominio_id)
            .execution_options(populate_existing=True)
        )

    async def listar(
        self, condominio_id: UUID, limit=50, offset=0
    ) -> list[CuentaUsuarioConRolResponse]:
        rows = await self.session.execute(
            select(Usuario, UsuarioRol)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
            .where(UsuarioRol.condominio_id == condominio_id)
            .order_by(Usuario.creado_en.desc(), Usuario.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            CuentaUsuarioConRolResponse(
                **CuentaUsuarioResponse.model_validate(usuario).model_dump(),
                rol=asignacion.rol,
                rol_activo=asignacion.es_activo,
                es_superadmin=usuario.es_superadmin,
            )
            for usuario, asignacion in rows
        ]

    async def ultimo_hash(self, condominio_id: UUID) -> str | None:
        return await self.session.scalar(
            select(AuditoriaLogORM.hash_actual)
            .where(AuditoriaLogORM.condominio_id == condominio_id)
            .order_by(AuditoriaLogORM.timestamp.desc(), AuditoriaLogORM.id.desc())
            .limit(1)
        )

    async def agregar(self, *records):
        self.session.add_all(records)
        await self.session.flush()

    async def confirmar(self):
        await self.session.commit()


def get_usuarios_repository(session: AsyncSession = Depends(get_db_session)):
    return SQLAlchemyUsuariosRepository(session)
