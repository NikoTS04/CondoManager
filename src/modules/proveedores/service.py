"""Servicio de negocio para Proveedores y Contratos (CON-48, CON-49)."""

import hashlib
import os
import re
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import UploadFile

from src.core.errors import APIError
from src.modules.proveedores.models import (
    ContratoProveedor,
    DocumentoContratoVersion,
    Proveedor,
)
from src.modules.proveedores.repository import SQLAlchemyProveedoresRepository
from src.modules.proveedores.schemas import (
    ActualizarContratoRequest,
    ActualizarProveedorRequest,
    ContratoDTO,
    ContratoDetalleDTO,
    CrearContratoRequest,
    CrearProveedorRequest,
    DocumentoVersionDTO,
    ProveedorDTO,
    ProveedorDetalleDTO,
)

# Límite de archivo para entorno Vercel Hobby / Demo: 3 MiB
MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024  # 3,145,728 bytes
MAGIC_PDF_SIGNATURE = b"%PDF"


class ProveedoresService:
    def __init__(self, repo: SQLAlchemyProveedoresRepository):
        self.repo = repo

    # PROVEEDORES (CON-48)

    async def registrar_proveedor(
        self, condominio_id: UUID, request: CrearProveedorRequest, usuario_id: UUID
    ) -> ProveedorDTO:
        # Verificar RUC duplicado en el mismo condominio
        existente = await self.repo.obtener_por_ruc(condominio_id, request.ruc)
        if existente is not None:
            raise APIError(
                409,
                "PROVEEDOR_RUC_DUPLICADO",
                f"Ya existe un proveedor registrado con el RUC {request.ruc} en este condominio.",
            )

        proveedor = await self.repo.crear_proveedor(condominio_id, request, usuario_id)
        return ProveedorDTO.model_validate(proveedor)

    async def obtener_proveedor(
        self, condominio_id: UUID, proveedor_id: UUID
    ) -> ProveedorDetalleDTO:
        proveedor = await self.repo.obtener_por_id(condominio_id, proveedor_id)
        if proveedor is None:
            raise APIError(
                404,
                "PROVEEDOR_NO_ENCONTRADO",
                "El proveedor solicitado no existe en este condominio.",
            )

        contratos = proveedor.contratos or []
        hoy = date.today()
        contratos_vigentes = sum(
            1 for c in contratos if c.estado in ("VIGENTE", "POR_VENCER") and c.fecha_fin >= hoy
        )

        detalle = ProveedorDetalleDTO(
            id=proveedor.id,
            condominio_id=proveedor.condominio_id,
            ruc=proveedor.ruc,
            razon_social=proveedor.razon_social,
            nombre_comercial=proveedor.nombre_comercial,
            rubro=proveedor.rubro,
            contacto_nombre=proveedor.contacto_nombre,
            contacto_telefono=proveedor.contacto_telefono,
            contacto_email=proveedor.contacto_email,
            direccion=proveedor.direccion,
            activo=proveedor.activo,
            notas=proveedor.notas,
            version=proveedor.version,
            creado_en=proveedor.creado_en,
            actualizado_en=proveedor.actualizado_en,
            total_contratos=len(contratos),
            contratos_vigentes=contratos_vigentes,
            egresos_vinculados=0,
            incidencias_vinculadas=0,
        )
        return detalle

    async def listar_proveedores(
        self,
        condominio_id: UUID,
        activo: bool | None = None,
        rubro: str | None = None,
        buscar: str | None = None,
    ) -> list[ProveedorDTO]:
        proveedores = await self.repo.listar_proveedores(
            condominio_id, activo=activo, rubro=rubro, buscar=buscar
        )
        return [ProveedorDTO.model_validate(p) for p in proveedores]

    async def actualizar_proveedor(
        self,
        condominio_id: UUID,
        proveedor_id: UUID,
        request: ActualizarProveedorRequest,
    ) -> ProveedorDTO:
        proveedor = await self.repo.obtener_por_id(condominio_id, proveedor_id)
        if proveedor is None:
            raise APIError(
                404,
                "PROVEEDOR_NO_ENCONTRADO",
                "El proveedor solicitado no existe en este condominio.",
            )

        actualizado = await self.repo.actualizar_proveedor(proveedor, request)
        return ProveedorDTO.model_validate(actualizado)

    # CONTRATOS Y PÓLIZAS (CON-49)

    @staticmethod
    def _calcular_estado_y_dias(contrato: ContratoProveedor) -> tuple[str, int]:
        hoy = date.today()
        dias = (contrato.fecha_fin - hoy).days
        estado = contrato.estado

        if estado not in ("CANCELADO", "RENOVADO"):
            if dias < 0:
                estado = "VENCIDO"
            elif dias <= 60:
                estado = "POR_VENCER"
            else:
                estado = "VIGENTE"

        return estado, dias

    async def registrar_contrato(
        self,
        condominio_id: UUID,
        proveedor_id: UUID,
        request: CrearContratoRequest,
        usuario_id: UUID,
    ) -> ContratoDTO:
        proveedor = await self.repo.obtener_por_id(condominio_id, proveedor_id)
        if proveedor is None:
            raise APIError(
                404,
                "PROVEEDOR_NO_ENCONTRADO",
                "No se puede asociar un contrato a un proveedor inexistente.",
            )

        contrato = await self.repo.crear_contrato(
            condominio_id, proveedor_id, request, usuario_id
        )
        estado, dias = self._calcular_estado_y_dias(contrato)
        contrato.estado = estado

        dto = ContratoDTO.model_validate(contrato)
        dto.dias_restantes = dias
        dto.tiene_documento = False
        return dto

    async def obtener_contrato(
        self, condominio_id: UUID, contrato_id: UUID
    ) -> ContratoDetalleDTO:
        contrato = await self.repo.obtener_contrato_por_id(condominio_id, contrato_id)
        if contrato is None:
            raise APIError(
                404,
                "CONTRATO_NO_ENCONTRADO",
                "El contrato solicitado no existe en este condominio.",
            )

        estado, dias = self._calcular_estado_y_dias(contrato)
        contrato.estado = estado

        versiones_dto = [
            DocumentoVersionDTO.model_validate(v) for v in contrato.versiones
        ]

        return ContratoDetalleDTO(
            id=contrato.id,
            condominio_id=contrato.condominio_id,
            proveedor_id=contrato.proveedor_id,
            numero_contrato=contrato.numero_contrato,
            tipo_documento=contrato.tipo_documento,
            descripcion=contrato.descripcion,
            monto_mensual=contrato.monto_mensual,
            moneda=contrato.moneda,
            fecha_inicio=contrato.fecha_inicio,
            fecha_fin=contrato.fecha_fin,
            contacto_emergencia=contrato.contacto_emergencia,
            contacto_emergencia_telefono=contrato.contacto_emergencia_telefono,
            estado=contrato.estado,
            version_actual=contrato.version_actual,
            dias_restantes=dias,
            tiene_documento=len(versiones_dto) > 0,
            creado_en=contrato.creado_en,
            actualizado_en=contrato.actualizado_en,
            proveedor_ruc=contrato.proveedor.ruc,
            proveedor_razon_social=contrato.proveedor.razon_social,
            versiones=versiones_dto,
        )

    async def listar_contratos(
        self,
        condominio_id: UUID,
        proveedor_id: UUID | None = None,
        estado: str | None = None,
    ) -> list[ContratoDTO]:
        contratos = await self.repo.listar_contratos(
            condominio_id, proveedor_id=proveedor_id, estado=estado
        )
        resultado: list[ContratoDTO] = []
        for c in contratos:
            est, dias = self._calcular_estado_y_dias(c)
            dto = ContratoDTO.model_validate(c)
            dto.estado = est
            dto.dias_restantes = dias
            dto.tiene_documento = len(c.versiones) > 0
            resultado.append(dto)
        return resultado

    async def actualizar_contrato(
        self,
        condominio_id: UUID,
        contrato_id: UUID,
        request: ActualizarContratoRequest,
    ) -> ContratoDTO:
        contrato = await self.repo.obtener_contrato_por_id(condominio_id, contrato_id)
        if contrato is None:
            raise APIError(
                404,
                "CONTRATO_NO_ENCONTRADO",
                "El contrato solicitado no existe en este condominio.",
            )

        actualizado = await self.repo.actualizar_contrato(contrato, request)
        est, dias = self._calcular_estado_y_dias(actualizado)
        dto = ContratoDTO.model_validate(actualizado)
        dto.estado = est
        dto.dias_restantes = dias
        dto.tiene_documento = len(actualizado.versiones) > 0
        return dto

    # GESTIÓN Y VERSIONADO DE ARCHIVOS PRIVADOS (CON-49)

    async def subir_documento_version(
        self,
        condominio_id: UUID,
        contrato_id: UUID,
        archivo: UploadFile,
        usuario_id: UUID,
        motivo_reemplazo: str | None = None,
    ) -> DocumentoVersionDTO:
        contrato = await self.repo.obtener_contrato_por_id(condominio_id, contrato_id)
        if contrato is None:
            raise APIError(
                404,
                "CONTRATO_NO_ENCONTRADO",
                "El contrato solicitado no existe en este condominio.",
            )

        # 1. Mitigación de Path Traversal en el nombre del archivo
        nombre_original = os.path.basename(archivo.filename or "documento.pdf")
        nombre_sanitizado = re.sub(r"[^A-Za-z0-9._-]", "_", nombre_original)

        # 2. Leer contenido binario
        contenido = await archivo.read()
        tamano = len(contenido)

        if tamano == 0:
            raise APIError(
                422,
                "ARCHIVO_VACIO",
                "El archivo proporcionado está vacío.",
            )

        if tamano > MAX_FILE_SIZE_BYTES:
            raise APIError(
                413,
                "ARCHIVO_DEMASIADO_GRANDE",
                f"El archivo excede el tamaño máximo permitido de 3 MiB (tamaño: {tamano} bytes).",
            )

        # 3. Validación binaria estricta de Magic Bytes (PDF)
        if not contenido.startswith(MAGIC_PDF_SIGNATURE):
            raise APIError(
                422,
                "FORMATO_NO_PERMITIDO",
                "Solo se admiten documentos en formato PDF válido (%PDF).",
            )

        # 4. Hash criptográfico SHA-256
        hash_sha256 = hashlib.sha256(contenido).hexdigest()

        # 5. Persistencia versionada (conserva siempre versiones anteriores)
        doc_version = await self.repo.agregar_version_documento(
            contrato=contrato,
            archivo_nombre=nombre_sanitizado,
            archivo_mime="application/pdf",
            archivo_tamano_bytes=tamano,
            hash_sha256=hash_sha256,
            archivo_binario=contenido,
            subido_por=usuario_id,
            motivo_reemplazo=motivo_reemplazo,
        )

        return DocumentoVersionDTO.model_validate(doc_version)

    async def descargar_documento_version(
        self,
        condominio_id: UUID,
        contrato_id: UUID,
        version: int,
    ) -> tuple[bytes, str, str]:
        contrato = await self.repo.obtener_contrato_por_id(condominio_id, contrato_id)
        if contrato is None:
            raise APIError(
                404,
                "CONTRATO_NO_ENCONTRADO",
                "El contrato solicitado no existe.",
            )

        doc_version = await self.repo.obtener_version_documento(contrato_id, version)
        if doc_version is None:
            raise APIError(
                404,
                "VERSION_NO_ENCONTRADA",
                f"No existe la versión {version} del documento para este contrato.",
            )

        return (
            doc_version.archivo_binario,
            doc_version.archivo_mime,
            doc_version.archivo_nombre,
        )
