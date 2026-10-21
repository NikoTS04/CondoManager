"""Resolución de destinatarios autorizados por departamento y condominio (CON-32/34/36).

Solo selecciona vínculos activos (`usuario_departamentos.es_activo IS TRUE`)
pertenecientes a cuentas activas (`usuarios.esta_activo IS TRUE`) del
departamento y condominio indicados, garantizando aislamiento estricto entre
unidades.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.condominios.models import Departamento, Edificio
from src.modules.usuarios.models import Usuario, UsuarioDepartamento

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnidadDepartamento:
    departamento_id: uuid.UUID
    numero: str
    edificio_id: uuid.UUID
    edificio_nombre: str
    condominio_id: uuid.UUID
    activo: bool

    @property
    def etiqueta_dpto(self) -> str:
        return f"{self.numero} ({self.edificio_nombre})"


@dataclass(frozen=True)
class DestinatarioDepartamento:
    usuario_id: uuid.UUID
    email: str
    nombre_completo: str
    tipo_relacion: str
    departamento_id: uuid.UUID
    departamento_numero: str
    edificio_nombre: str
    condominio_id: uuid.UUID

    @property
    def etiqueta_dpto(self) -> str:
        return f"{self.departamento_numero} ({self.edificio_nombre})"


async def obtener_unidad_departamento(
    session: AsyncSession,
    departamento_id: uuid.UUID,
    condominio_id: uuid.UUID | None = None,
) -> UnidadDepartamento | None:
    """Obtiene los datos del departamento y su edificio validando pertenencia al condominio."""
    stmt = (
        select(
            Departamento.id,
            Departamento.numero,
            Departamento.edificio_id,
            Edificio.nombre_bloque,
            Edificio.condominio_id,
            Departamento.activo,
        )
        .join(Edificio, Edificio.id == Departamento.edificio_id)
        .where(Departamento.id == departamento_id)
    )
    if condominio_id is not None:
        stmt = stmt.where(Edificio.condominio_id == condominio_id)

    fila = (await session.execute(stmt)).first()
    if fila is None:
        return None
    return UnidadDepartamento(
        departamento_id=fila[0],
        numero=fila[1],
        edificio_id=fila[2],
        edificio_nombre=fila[3],
        condominio_id=fila[4],
        activo=bool(fila[5]),
    )


async def resolver_destinatarios_departamento(
    session: AsyncSession,
    departamento_id: uuid.UUID,
    condominio_id: uuid.UUID | None = None,
) -> list[DestinatarioDepartamento]:
    """Devuelve los destinatarios con vínculo activo y cuenta activa del departamento."""
    stmt = (
        select(
            Usuario.id,
            Usuario.email,
            Usuario.nombre,
            Usuario.apellido,
            UsuarioDepartamento.tipo_relacion,
            Departamento.id,
            Departamento.numero,
            Edificio.nombre_bloque,
            Edificio.condominio_id,
        )
        .join(UsuarioDepartamento, UsuarioDepartamento.usuario_id == Usuario.id)
        .join(Departamento, Departamento.id == UsuarioDepartamento.departamento_id)
        .join(Edificio, Edificio.id == Departamento.edificio_id)
        .where(
            Departamento.id == departamento_id,
            UsuarioDepartamento.es_activo.is_(True),
            Usuario.esta_activo.is_(True),
        )
        .order_by(Usuario.id)
    )
    if condominio_id is not None:
        stmt = stmt.where(Edificio.condominio_id == condominio_id)

    filas = (await session.execute(stmt)).all()
    destinatarios: list[DestinatarioDepartamento] = []
    for (
        usuario_id,
        email,
        nombre,
        apellido,
        tipo_relacion,
        dpto_id,
        dpto_numero,
        edificio_nombre,
        condo_id,
    ) in filas:
        correo = (email or "").strip()
        if not correo:
            continue
        nombre_completo = f"{(nombre or '').strip()} {(apellido or '').strip()}".strip()
        destinatarios.append(
            DestinatarioDepartamento(
                usuario_id=usuario_id,
                email=correo,
                nombre_completo=nombre_completo or "Residente",
                tipo_relacion=tipo_relacion,
                departamento_id=dpto_id,
                departamento_numero=dpto_numero,
                edificio_nombre=edificio_nombre,
                condominio_id=condo_id,
            )
        )

    if not destinatarios:
        logger.info(
            "Sin destinatarios activos para departamento_id=%s condominio_id=%s",
            departamento_id,
            condominio_id,
        )
    return destinatarios


async def resolver_destinatarios_condominio(
    session: AsyncSession,
    condominio_id: uuid.UUID,
) -> list[DestinatarioDepartamento]:
    """Devuelve los destinatarios con vínculo activo de todos los departamentos activos del condominio."""
    stmt = (
        select(
            Usuario.id,
            Usuario.email,
            Usuario.nombre,
            Usuario.apellido,
            UsuarioDepartamento.tipo_relacion,
            Departamento.id,
            Departamento.numero,
            Edificio.nombre_bloque,
            Edificio.condominio_id,
        )
        .join(UsuarioDepartamento, UsuarioDepartamento.usuario_id == Usuario.id)
        .join(Departamento, Departamento.id == UsuarioDepartamento.departamento_id)
        .join(Edificio, Edificio.id == Departamento.edificio_id)
        .where(
            Edificio.condominio_id == condominio_id,
            Departamento.activo.is_(True),
            UsuarioDepartamento.es_activo.is_(True),
            Usuario.esta_activo.is_(True),
        )
        .order_by(Departamento.numero, Usuario.id)
    )
    filas = (await session.execute(stmt)).all()
    destinatarios: list[DestinatarioDepartamento] = []
    for (
        usuario_id,
        email,
        nombre,
        apellido,
        tipo_relacion,
        dpto_id,
        dpto_numero,
        edificio_nombre,
        condo_id,
    ) in filas:
        correo = (email or "").strip()
        if not correo:
            continue
        nombre_completo = f"{(nombre or '').strip()} {(apellido or '').strip()}".strip()
        destinatarios.append(
            DestinatarioDepartamento(
                usuario_id=usuario_id,
                email=correo,
                nombre_completo=nombre_completo or "Residente",
                tipo_relacion=tipo_relacion,
                departamento_id=dpto_id,
                departamento_numero=dpto_numero,
                edificio_nombre=edificio_nombre,
                condominio_id=condo_id,
            )
        )
    if not destinatarios:
        logger.info("Sin destinatarios activos para condominio_id=%s", condominio_id)
    return destinatarios
