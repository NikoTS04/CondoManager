"""Pruebas unitarias para Directorio de Proveedores y Contratos (CON-48, CON-49)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

from src.core.errors import APIError
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
from src.modules.proveedores.service import ProveedoresService


class MockProveedoresRepository:
    def __init__(self):
        self.proveedores: dict[UUID, Proveedor] = {}
        self.contratos: dict[UUID, ContratoProveedor] = {}
        self.documentos: dict[tuple[UUID, int], DocumentoContratoVersion] = {}

    async def crear_proveedor(
        self, condominio_id: UUID, request: CrearProveedorRequest, creado_por: UUID
    ) -> Proveedor:
        p = Proveedor(
            id=uuid4(),
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
            creado_en=datetime.now(),
            actualizado_en=datetime.now(),
        )
        p.contratos = []
        self.proveedores[p.id] = p
        return p

    async def obtener_por_id(
        self, condominio_id: UUID, proveedor_id: UUID
    ) -> Proveedor | None:
        p = self.proveedores.get(proveedor_id)
        if p and p.condominio_id == condominio_id:
            p.contratos = [
                c for c in self.contratos.values() if c.proveedor_id == p.id
            ]
            return p
        return None

    async def obtener_por_ruc(
        self, condominio_id: UUID, ruc: str
    ) -> Proveedor | None:
        if not ruc or "\x00" in ruc:
            return None
        for p in self.proveedores.values():
            if p.condominio_id == condominio_id and p.ruc == ruc.strip():
                return p
        return None

    async def listar_proveedores(
        self,
        condominio_id: UUID,
        activo: bool | None = None,
        rubro: str | None = None,
        buscar: str | None = None,
    ) -> list[Proveedor]:
        resultado = []
        for p in self.proveedores.values():
            if p.condominio_id != condominio_id:
                continue
            if activo is not None and p.activo != activo:
                continue
            if rubro and p.rubro.upper() != rubro.strip().upper():
                continue
            if buscar and buscar.strip():
                t = buscar.strip().lower()
                en_razon = t in p.razon_social.lower()
                en_comercial = p.nombre_comercial and t in p.nombre_comercial.lower()
                en_ruc = t in p.ruc
                if not (en_razon or en_comercial or en_ruc):
                    continue
            resultado.append(p)
        return sorted(resultado, key=lambda x: x.razon_social)

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
        proveedor.actualizado_en = datetime.now()
        return proveedor

    async def crear_contrato(
        self,
        condominio_id: UUID,
        proveedor_id: UUID,
        request: CrearContratoRequest,
        creado_por: UUID,
    ) -> ContratoProveedor:
        c = ContratoProveedor(
            id=uuid4(),
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
            creado_en=datetime.now(),
            actualizado_en=datetime.now(),
        )
        c.versiones = []
        c.proveedor = self.proveedores[proveedor_id]
        self.contratos[c.id] = c
        return c

    async def obtener_contrato_por_id(
        self, condominio_id: UUID, contrato_id: UUID
    ) -> ContratoProveedor | None:
        c = self.contratos.get(contrato_id)
        if c and c.condominio_id == condominio_id:
            c.versiones = [
                doc for (cid, _), doc in self.documentos.items() if cid == c.id
            ]
            c.proveedor = self.proveedores.get(c.proveedor_id)
            return c
        return None

    async def listar_contratos(
        self,
        condominio_id: UUID,
        proveedor_id: UUID | None = None,
        estado: str | None = None,
    ) -> list[ContratoProveedor]:
        resultado = []
        for c in self.contratos.values():
            if c.condominio_id != condominio_id:
                continue
            if proveedor_id and c.proveedor_id != proveedor_id:
                continue
            if estado and c.estado != estado.strip().upper():
                continue
            c.versiones = [
                doc for (cid, _), doc in self.documentos.items() if cid == c.id
            ]
            c.proveedor = self.proveedores.get(c.proveedor_id)
            resultado.append(c)
        return sorted(resultado, key=lambda x: x.fecha_fin)

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

        contrato.actualizado_en = datetime.now()
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
        existentes = [doc for (cid, _), doc in self.documentos.items() if cid == contrato.id]
        nueva_version = max((v.version for v in existentes), default=0) + 1

        doc = DocumentoContratoVersion(
            id=uuid4(),
            contrato_id=contrato.id,
            version=nueva_version,
            archivo_nombre=archivo_nombre,
            archivo_mime=archivo_mime,
            archivo_tamano_bytes=archivo_tamano_bytes,
            hash_sha256=hash_sha256,
            archivo_binario=archivo_binario,
            motivo_reemplazo=motivo_reemplazo,
            subido_por=subido_por,
            subido_en=datetime.now(),
        )
        self.documentos[(contrato.id, nueva_version)] = doc
        contrato.version_actual = nueva_version
        contrato.versiones.append(doc)
        return doc

    async def obtener_version_documento(
        self, contrato_id: UUID, version: int
    ) -> DocumentoContratoVersion | None:
        return self.documentos.get((contrato_id, version))


@pytest.fixture
def service():
    repo = MockProveedoresRepository()
    return ProveedoresService(repo)


@pytest.mark.asyncio
async def test_crear_proveedor_exitoso(service):
    cid = uuid4()
    uid = uuid4()
    req = CrearProveedorRequest(
        ruc="20551122334",
        razon_social="Ascensores Rápidos SAC",
        nombre_comercial="Otis Express",
        rubro="MANTENIMIENTO_PREVENTIVO",
        contacto_nombre="Ing. Marco Polo",
        contacto_telefono="999888777",
        contacto_email="contacto@ascensores.pe",
        direccion="Av. Industrial 123",
        notas="Mantenimiento 24/7",
    )

    prov = await service.registrar_proveedor(cid, req, uid)
    assert prov.ruc == "20551122334"
    assert prov.razon_social == "Ascensores Rápidos SAC"
    assert prov.rubro == "MANTENIMIENTO_PREVENTIVO"
    assert prov.activo is True
    assert prov.version == 1


@pytest.mark.asyncio
async def test_ruc_duplicado_mismo_condominio_rechazado(service):
    cid = uuid4()
    uid = uuid4()
    req1 = CrearProveedorRequest(
        ruc="20123456789",
        razon_social="Seguridad Total SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Juan Perez",
        contacto_telefono="987654321",
        contacto_email="jperez@seguridad.pe",
    )
    await service.registrar_proveedor(cid, req1, uid)

    req2 = CrearProveedorRequest(
        ruc="20123456789",  # Mismo RUC
        razon_social="Otra Empresa de Seguridad SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Maria Gomez",
        contacto_telefono="911222333",
        contacto_email="mgomez@seguridad.pe",
    )
    with pytest.raises(APIError) as exc_info:
        await service.registrar_proveedor(cid, req2, uid)
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "PROVEEDOR_RUC_DUPLICADO"


@pytest.mark.asyncio
async def test_listar_y_filtrar_proveedores(service):
    cid = uuid4()
    uid = uuid4()
    p1 = CrearProveedorRequest(
        ruc="20111111111",
        razon_social="Limpieza Pro SAC",
        rubro="LIMPIEZA",
        contacto_nombre="Lucia Diaz",
        contacto_telefono="912345678",
        contacto_email="lucia@limpiezapro.pe",
    )
    p2 = CrearProveedorRequest(
        ruc="20222222222",
        razon_social="Vigilancia Águila SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Pedro Silva",
        contacto_telefono="987111222",
        contacto_email="pedro@aguila.pe",
    )
    await service.registrar_proveedor(cid, p1, uid)
    await service.registrar_proveedor(cid, p2, uid)

    todos = await service.listar_proveedores(cid)
    assert len(todos) == 2

    solo_seguridad = await service.listar_proveedores(cid, rubro="SEGURIDAD")
    assert len(solo_seguridad) == 1
    assert solo_seguridad[0].ruc == "20222222222"

    busqueda = await service.listar_proveedores(cid, buscar="Limpieza")
    assert len(busqueda) == 1
    assert busqueda[0].ruc == "20111111111"


@pytest.mark.asyncio
async def test_contrato_registro_y_calculo_vigencia(service):
    cid = uuid4()
    uid = uuid4()
    prov = await service.registrar_proveedor(
        cid,
        CrearProveedorRequest(
            ruc="20333333333",
            razon_social="Bombas & Motores SAC",
            rubro="MANTENIMIENTO_PREVENTIVO",
            contacto_nombre="Raul Torres",
            contacto_telefono="944555666",
            contacto_email="bombas@motores.pe",
        ),
        uid,
    )

    hoy = date.today()
    req_contrato = CrearContratoRequest(
        numero_contrato="CTR-2026-001",
        tipo_documento="CONTRATO_SERVICIO",
        descripcion="Mantenimiento bimensual de bombas hidroneumáticas",
        monto_mensual=Decimal("850.50"),
        moneda="PEN",
        fecha_inicio=hoy - timedelta(days=30),
        fecha_fin=hoy + timedelta(days=20),  # Menos de 60 días -> POR_VENCER
        contacto_emergencia="Ing. Guardia 24h",
        contacto_emergencia_telefono="999111000",
    )

    contrato = await service.registrar_contrato(cid, prov.id, req_contrato, uid)
    assert contrato.estado == "POR_VENCER"
    assert contrato.dias_restantes == 20
    assert contrato.monto_mensual == Decimal("850.50")


@pytest.mark.asyncio
async def test_subida_version_documento_pdf_segura(service):
    cid = uuid4()
    uid = uuid4()
    prov = await service.registrar_proveedor(
        cid,
        CrearProveedorRequest(
            ruc="20444444444",
            razon_social="Extintores del Perú SAC",
            rubro="SEGURIDAD",
            contacto_nombre="Sonia Mendoza",
            contacto_telefono="955666777",
            contacto_email="sonia@extintores.pe",
        ),
        uid,
    )

    hoy = date.today()
    contrato = await service.registrar_contrato(
        cid,
        prov.id,
        CrearContratoRequest(
            numero_contrato="EXT-2026-05",
            tipo_documento="POLIZA_SEGURO",
            descripcion="Recarga y certificación anual de extintores",
            monto_mensual=Decimal("300.00"),
            fecha_inicio=hoy,
            fecha_fin=hoy + timedelta(days=365),
        ),
        uid,
    )

    # 1. Archivo PDF válido con magic bytes %PDF
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    upload_file = UploadFile(
        file=BytesIO(pdf_bytes),
        filename="contrato_original.pdf",
        headers={"content-type": "application/pdf"},
    )

    v1 = await service.subir_documento_version(cid, contrato.id, upload_file, uid)
    assert v1.version == 1
    assert v1.archivo_nombre == "contrato_original.pdf"
    assert v1.archivo_tamano_bytes == len(pdf_bytes)

    # 2. Reemplazo por Addenda (versión 2)
    pdf_bytes_v2 = b"%PDF-1.5\nAddenda 2026\n%%EOF"
    upload_v2 = UploadFile(
        file=BytesIO(pdf_bytes_v2),
        filename="addenda_firmada.pdf",
        headers={"content-type": "application/pdf"},
    )

    v2 = await service.subir_documento_version(
        cid, contrato.id, upload_v2, uid, motivo_reemplazo="Ampliación de cobertura"
    )
    assert v2.version == 2
    assert v2.archivo_nombre == "addenda_firmada.pdf"
    assert v2.motivo_reemplazo == "Ampliación de cobertura"

    # 3. Descargar v1 y v2 para asegurar que ambas siguen en el repositorio
    binario1, mime1, nom1 = await service.descargar_documento_version(cid, contrato.id, 1)
    assert binario1 == pdf_bytes
    assert nom1 == "contrato_original.pdf"

    binario2, mime2, nom2 = await service.descargar_documento_version(cid, contrato.id, 2)
    assert binario2 == pdf_bytes_v2
    assert nom2 == "addenda_firmada.pdf"


@pytest.mark.asyncio
async def test_rechazo_archivo_no_pdf(service):
    cid = uuid4()
    uid = uuid4()
    prov = await service.registrar_proveedor(
        cid,
        CrearProveedorRequest(
            ruc="20666666666",
            razon_social="Servicios Generales SRL",
            rubro="LIMPIEZA",
            contacto_nombre="Elena Paz",
            contacto_telefono="977888999",
            contacto_email="elena@servicios.pe",
        ),
        uid,
    )
    hoy = date.today()
    contrato = await service.registrar_contrato(
        cid,
        prov.id,
        CrearContratoRequest(
            numero_contrato="CTR-002",
            tipo_documento="CONTRATO_SERVICIO",
            descripcion="Limpieza diaria",
            fecha_inicio=hoy,
            fecha_fin=hoy + timedelta(days=90),
        ),
        uid,
    )

    # Archivo de texto plano simulando ejecutable o no-PDF
    bad_file = UploadFile(
        file=BytesIO(b"MZ\x90\x00\x03\x00\x00\x00malicious binary content"),
        filename="fake.pdf",
    )
    with pytest.raises(APIError) as exc_info:
        await service.subir_documento_version(cid, contrato.id, bad_file, uid)
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "FORMATO_NO_PERMITIDO"
