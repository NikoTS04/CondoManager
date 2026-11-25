"""Repositorio SQLAlchemy para Proveedores y Contratos (CON-48, CON-49)."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db_session
from src.modules.proveedores.models import (
    ContratoProveedor,
    DocumentoContratoVersion,
    Proveedor,
)
from src.modules.proveedores.schemas import (
    ActualizarContratoRequest,
    ActualizarProveedorRequest,
    CrearContratoRequest,
    CrearProveedorRequest,
)


class SQLAlchemyProveedoresRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # PROVEEDORES (CON-48)

    async def crear_proveedor(
        self, condominio_id: UUID, request: CrearProveedorRequest, creado_por: UUID
    ) -> Proveedor:
        proveedor = Proveedor(
            condominio_id=condominio_id,
            ruc=request.ruc.strip(),
            razon_social=request.razon_social.strip(),
            nombre_comercial=request.nombre_comercial.strip() if request.nombre_comercial else None,
            rubro=request.rubro.strip().upper(),
            contacto_nombre=request.contacto_nombre.strip(),
            contacto_telefono=request.contacto_telefono.strip(),
            contacto_email=str(request.contacto_email).strip().lower(),
            direccion=request.direccion.strip() if request.direccion else None,
            notas=request.notas.strip() if request.notas else None,
            creado_por=creado_por,
            activo=True,
            version=1,
        )
        self.session.add(proveedor)
        await self.session.flush()
        return proveedor

    async def obtener_por_id(
        self, condominio_id: UUID, proveedor_id: UUID
    ) -> Proveedor | None:
        query = (
            select(Proveedor)
            .where(
                Proveedor.id == proveedor_id,
                Proveedor.condominio_id == condominio_id,
            )
            .options(selectinload(Proveedor.contratos))
        )
        return await self.session.scalar(query)

    async def obtener_por_ruc(
        self, condominio_id: UUID, ruc: str
    ) -> Proveedor | None:
        if not ruc or "\x00" in ruc:
            return None
        query = select(Proveedor).where(
            Proveedor.condominio_id == condominio_id,
            Proveedor.ruc == ruc.strip(),
        )
        return await self.session.scalar(query)

    async def listar_proveedores(
        self,
        condominio_id: UUID,
        activo: bool | None = None,
        rubro: str | None = None,
        buscar: str | None = None,
    ) -> list[Proveedor]:
        query = (
            select(Proveedor)
            .where(Proveedor.condominio_id == condominio_id)
            .order_by(Proveedor.razon_social.asc())
        )
        if activo is not None:
            query = query.where(Proveedor.activo == activo)
        if rubro:
            query = query.where(func.upper(Proveedor.rubro) == rubro.strip().upper())
        if buscar and buscar.strip():
            patron = f"%{buscar.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(Proveedor.razon_social).like(patron),
                    func.lower(Proveedor.nombre_comercial).like(patron),
                    Proveedor.ruc.like(f"%{buscar.strip()}%"),
                )
            )
        result = await self.session.scalars(query)
        return list(result.all())

    async def actualizar_proveedor(
        self, proveedor: Proveedor, request: ActualizarProveedorRequest
    ) -> Proveedor:
        if request.razon_social is not None:
            proveedor.razon_social = request.razon_social.strip()
        if request.nombre_comercial is not None:
            proveedor.nombre_comercial = request.nombre_comercial.strip() if request.nombre_comercial else None
        if request.rubro is not None:
            proveedor.rubro = request.rubro.strip().upper()
        if request.contacto_nombre is not None:
            proveedor.contacto_nombre = request.contacto_nombre.strip()
        if request.contacto_telefono is not None:
            proveedor.contacto_telefono = request.contacto_telefono.strip()
        if request.contacto_email is not None:
            proveedor.contacto_email = str(request.contacto_email).strip().lower()
        if request.direccion is not None:
            proveedor.direccion = request.direccion.strip() if request.direccion else None
        if request.activo is not None:
            proveedor.activo = request.activo
        if request.notas is not None:
            proveedor.notas = request.notas.strip() if request.notas else None

        proveedor.version += 1
        await self.session.flush()
        return proveedor

    # CONTRATOS (CON-49)

    async def crear_contrato(
        self,
        condominio_id: UUID,
        proveedor_id: UUID,
        request: CrearContratoRequest,
        creado_por: UUID,
    ) -> ContratoProveedor:
        contrato = ContratoProveedor(
            condominio_id=condominio_id,
            proveedor_id=proveedor_id,
            numero_contrato=request.numero_contrato.strip(),
            tipo_documento=request.tipo_documento,
            descripcion=request.descripcion.strip(),
            monto_mensual=request.monto_mensual,
            moneda=request.moneda,
            fecha_inicio=request.fecha_inicio,
            fecha_fin=request.fecha_fin,
            contacto_emergencia=request.contacto_emergencia.strip() if request.contacto_emergencia else None,
            contacto_emergencia_telefono=request.contacto_emergencia_telefono.strip() if request.contacto_emergencia_telefono else None,
            estado="VIGENTE",
            version_actual=1,
            creado_por=creado_por,
        )
        self.session.add(contrato)
        await self.session.flush()
        return contrato

    async def obtener_contrato_por_id(
        self, condominio_id: UUID, contrato_id: UUID
    ) -> ContratoProveedor | None:
        query = (
            select(ContratoProveedor)
            .where(
                ContratoProveedor.id == contrato_id,
                ContratoProveedor.condominio_id == condominio_id,
            )
            .options(
                selectinload(ContratoProveedor.proveedor),
                selectinload(ContratoProveedor.versiones),
            )
        )
        return await self.session.scalar(query)

    async def listar_contratos(
        self,
        condominio_id: UUID,
        proveedor_id: UUID | None = None,
        estado: str | None = None,
    ) -> list[ContratoProveedor]:
        query = (
            select(ContratoProveedor)
            .where(ContratoProveedor.condominio_id == condominio_id)
            .options(
                selectinload(ContratoProveedor.proveedor),
                selectinload(ContratoProveedor.versiones),
            )
            .order_by(ContratoProveedor.fecha_fin.asc())
        )
        if proveedor_id:
            query = query.where(ContratoProveedor.proveedor_id == proveedor_id)
        if estado:
            query = query.where(ContratoProveedor.estado == estado.strip().upper())
        result = await self.session.scalars(query)
        return list(result.all())

    async def actualizar_contrato(
        self, contrato: ContratoProveedor, request: ActualizarContratoRequest
    ) -> ContratoProveedor:
        if request.descripcion is not None:
            contrato.descripcion = request.descripcion.strip()
        if request.monto_mensual is not None:
            contrato.monto_mensual = request.monto_mensual
        if request.fecha_fin is not None:
            contrato.fecha_fin = request.fecha_fin
        if request.contacto_emergencia is not None:
            contrato.contacto_emergencia = request.contacto_emergencia.strip() if request.contacto_emergencia else None
        if request.contacto_emergencia_telefono is not None:
            contrato.contacto_emergencia_telefono = request.contacto_emergencia_telefono.strip() if request.contacto_emergencia_telefono else None
        if request.estado is not None:
            contrato.estado = request.estado

        await self.session.flush()
        return contrato

    async def agregar_version_documento(
        self,
        contrato: ContratoProveedor,
        archivo_nombre: str,
        archivo_mime: str,
        archivo_tamano_bytes: int,
        hash_sha256: str,
        archivo_binario: bytes,
        subido_por: UUID,
        motivo_reemplazo: str | None = None,
    ) -> DocumentoContratoVersion:
        # Calcular siguiente número de versión
        nueva_version = contrato.version_actual + (1 if contrato.versiones else 0)
        # Si es la primera versión subida y no había documentos, se queda en 1
        if not contrato.versiones:
            nueva_version = 1
        else:
            nueva_version = max((v.version for v in contrato.versiones), default=0) + 1

        doc_version = DocumentoContratoVersion(
            contrato_id=contrato.id,
            version=nueva_version,
            archivo_nombre=archivo_nombre,
            archivo_mime=archivo_mime,
            archivo_tamano_bytes=archivo_tamano_bytes,
            hash_sha256=hash_sha256,
            archivo_binario=archivo_binario,
            motivo_reemplazo=motivo_reemplazo,
            subido_por=subido_por,
        )
        contrato.version_actual = nueva_version
        self.session.add(doc_version)
        await self.session.flush()
        return doc_version

    async def obtener_version_documento(
        self, contrato_id: UUID, version: int
    ) -> DocumentoContratoVersion | None:
        query = select(DocumentoContratoVersion).where(
            DocumentoContratoVersion.contrato_id == contrato_id,
            DocumentoContratoVersion.version == version,
        )
        return await self.session.scalar(query)

    async def obtener_version_por_id(
        self, version_id: UUID
    ) -> DocumentoContratoVersion | None:
        query = select(DocumentoContratoVersion).where(
            DocumentoContratoVersion.id == version_id
        )
        return await self.session.scalar(query)


async def get_proveedores_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SQLAlchemyProveedoresRepository:
    return SQLAlchemyProveedoresRepository(session)
