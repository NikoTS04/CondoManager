"""Rutas FastAPI para Proveedores y Contratos (CON-48, CON-49)."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from src.core.authorization import autorizar_condominio
from src.core.security import get_current_user
from src.modules.proveedores.repository import (
    SQLAlchemyProveedoresRepository,
    get_proveedores_repository,
)
from src.modules.proveedores.schemas import (
    ActualizarContratoRequest,
    ActualizarProveedorRequest,
    ContratoDetalleDTO,
    ContratoDTO,
    CrearContratoRequest,
    CrearProveedorRequest,
    DocumentoVersionDTO,
    ProveedorDetalleDTO,
    ProveedorDTO,
)
from src.modules.proveedores.service import ProveedoresService

router = APIRouter(tags=["Proveedores y Contratos"])


def _servicio(
    repo: SQLAlchemyProveedoresRepository = Depends(get_proveedores_repository),
) -> ProveedoresService:
    return ProveedoresService(repo)


# ==============================================================================
# PROVEEDORES (CON-48)
# ==============================================================================


@router.post(
    "/condominios/{cid}/proveedores",
    response_model=ProveedorDTO,
    status_code=201,
    summary="Registrar un nuevo proveedor en el directorio (CON-48)",
)
async def registrar_proveedor(
    cid: UUID,
    payload: CrearProveedorRequest,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=True)
    return await service.registrar_proveedor(cid, payload, UUID(actor["sub"]))


@router.get(
    "/condominios/{cid}/proveedores",
    response_model=list[ProveedorDTO],
    summary="Listar proveedores del condominio con filtros (CON-48)",
)
async def listar_proveedores(
    cid: UUID,
    activo: bool | None = None,
    rubro: str | None = None,
    buscar: str | None = None,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    return await service.listar_proveedores(cid, activo=activo, rubro=rubro, buscar=buscar)


@router.get(
    "/condominios/{cid}/proveedores/{proveedor_id}",
    response_model=ProveedorDetalleDTO,
    summary="Consultar detalle de un proveedor e historial vinculado (CON-48)",
)
async def obtener_proveedor(
    cid: UUID,
    proveedor_id: UUID,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    return await service.obtener_proveedor(cid, proveedor_id)


@router.patch(
    "/condominios/{cid}/proveedores/{proveedor_id}",
    response_model=ProveedorDTO,
    summary="Actualizar información de un proveedor (CON-48)",
)
async def actualizar_proveedor(
    cid: UUID,
    proveedor_id: UUID,
    payload: ActualizarProveedorRequest,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=True)
    return await service.actualizar_proveedor(cid, proveedor_id, payload)


# ==============================================================================
# CONTRATOS Y PÓLIZAS (CON-49)
# ==============================================================================


@router.post(
    "/condominios/{cid}/proveedores/{proveedor_id}/contratos",
    response_model=ContratoDTO,
    status_code=201,
    summary="Registrar un contrato o póliza para un proveedor (CON-49)",
)
async def registrar_contrato(
    cid: UUID,
    proveedor_id: UUID,
    payload: CrearContratoRequest,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=True)
    return await service.registrar_contrato(cid, proveedor_id, payload, UUID(actor["sub"]))


@router.get(
    "/condominios/{cid}/proveedores/{proveedor_id}/contratos",
    response_model=list[ContratoDTO],
    summary="Listar contratos de un proveedor específico (CON-49)",
)
async def listar_contratos_proveedor(
    cid: UUID,
    proveedor_id: UUID,
    estado: str | None = None,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    return await service.listar_contratos(cid, proveedor_id=proveedor_id, estado=estado)


@router.get(
    "/condominios/{cid}/contratos",
    response_model=list[ContratoDTO],
    summary="Listar todos los contratos del condominio con días restantes de vigencia (CON-49)",
)
async def listar_contratos_condominio(
    cid: UUID,
    estado: str | None = None,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    return await service.listar_contratos(cid, proveedor_id=None, estado=estado)


@router.get(
    "/condominios/{cid}/contratos/{contrato_id}",
    response_model=ContratoDetalleDTO,
    summary="Consultar detalle de un contrato con historial de versiones de documentos (CON-49)",
)
async def obtener_contrato(
    cid: UUID,
    contrato_id: UUID,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    return await service.obtener_contrato(cid, contrato_id)


@router.patch(
    "/condominios/{cid}/contratos/{contrato_id}",
    response_model=ContratoDTO,
    summary="Actualizar datos o vigencia de un contrato (CON-49)",
)
async def actualizar_contrato(
    cid: UUID,
    contrato_id: UUID,
    payload: ActualizarContratoRequest,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=True)
    return await service.actualizar_contrato(cid, contrato_id, payload)


@router.post(
    "/condominios/{cid}/contratos/{contrato_id}/versiones",
    response_model=DocumentoVersionDTO,
    status_code=201,
    summary="Subir o reemplazar versión de PDF de contrato o póliza (CON-49)",
)
async def subir_documento_version(
    cid: UUID,
    contrato_id: UUID,
    archivo: UploadFile = File(...),
    motivo_reemplazo: str | None = Form(default=None),
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=True)
    return await service.subir_documento_version(
        condominio_id=cid,
        contrato_id=contrato_id,
        archivo=archivo,
        usuario_id=UUID(actor["sub"]),
        motivo_reemplazo=motivo_reemplazo,
    )


@router.get(
    "/condominios/{cid}/contratos/{contrato_id}/versiones/{version}/descargar",
    summary="Descargar versión de documento PDF de forma segura (CON-49)",
)
async def descargar_documento_version(
    cid: UUID,
    contrato_id: UUID,
    version: int,
    actor: dict = Depends(get_current_user),
    service: ProveedoresService = Depends(_servicio),
):
    autorizar_condominio(actor, cid, escritura=False)
    contenido, mime, nombre = await service.descargar_documento_version(cid, contrato_id, version)
    return Response(
        content=contenido,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{nombre}"',
            "Cache-Control": "private, no-cache",
        },
    )
