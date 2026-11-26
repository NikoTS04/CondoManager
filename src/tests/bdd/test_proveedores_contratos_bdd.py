"""Ejecución de la especificación BDD para CON-48 y CON-49."""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

try:
    from pytest_bdd import given, parsers, scenarios, then, when

    HAS_BDD_RUNTIME = True
except ImportError:
    HAS_BDD_RUNTIME = False

from src.core.errors import APIError
from src.modules.proveedores.schemas import (
    CrearContratoRequest,
    CrearProveedorRequest,
)
from src.modules.proveedores.service import ProveedoresService
from src.tests.unit.test_proveedores_contratos_con48_con49 import MockProveedoresRepository

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "06-egresos-proveedores"
    / "features"
    / "proveedores_contratos.feature"
)

if HAS_BDD_RUNTIME and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))


@pytest.fixture
def context():
    repo = MockProveedoresRepository()
    service = ProveedoresService(repo)
    cid = uuid4()
    uid_junta = uuid4()
    uid_auditor = uuid4()
    return {
        "repo": repo,
        "service": service,
        "cid": cid,
        "uid_junta": uid_junta,
        "uid_auditor": uid_auditor,
        "proveedor": None,
        "contrato": None,
        "error": None,
        "doc_v1": None,
        "doc_v2": None,
    }


# Escenario: Registro exitoso
@given("un condominio y un integrante de Junta autenticado")
def step_condominio_junta(context):
    assert context["cid"] is not None
    assert context["uid_junta"] is not None


@when("registra un proveedor con RUC de 11 dígitos, razón social y datos de contacto")
def step_registrar_proveedor(context):
    req = CrearProveedorRequest(
        ruc="20551122334",
        razon_social="Servicios de Mantenimiento SAC",
        rubro="MANTENIMIENTO_PREVENTIVO",
        contacto_nombre="Carlos Ramos",
        contacto_telefono="999888777",
        contacto_email="cramos@servicios.pe",
    )
    context["proveedor"] = asyncio.run(
        context["service"].registrar_proveedor(context["cid"], req, context["uid_junta"])
    )


@then("el proveedor queda guardado como activo y con versión inicial 1")
def step_verificar_proveedor_guardado(context):
    p = context["proveedor"]
    assert p is not None
    assert p.activo is True
    assert p.version == 1


@then("aparece disponible en el directorio oficial del condominio")
def step_verificar_en_directorio(context):
    lista = asyncio.run(context["service"].listar_proveedores(context["cid"]))
    assert any(p.id == context["proveedor"].id for p in lista)


# Escenario: Rechazo de RUC duplicado
@given(parsers.parse('un proveedor existente con RUC "{ruc}" en el condominio'))
def step_proveedor_existente(context, ruc):
    req = CrearProveedorRequest(
        ruc=ruc,
        razon_social="Empresa Base SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Juan Silva",
        contacto_telefono="911222333",
        contacto_email="jsilva@base.pe",
    )
    asyncio.run(context["service"].registrar_proveedor(context["cid"], req, context["uid_junta"]))


@when(parsers.parse('otro integrante intenta registrar un proveedor con el mismo RUC "{ruc}"'))
def step_intenta_duplicar_ruc(context, ruc):
    req = CrearProveedorRequest(
        ruc=ruc,
        razon_social="Empresa Duplicada SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Pedro Gomez",
        contacto_telefono="944555666",
        contacto_email="pgomez@duplicada.pe",
    )
    try:
        asyncio.run(
            context["service"].registrar_proveedor(context["cid"], req, context["uid_junta"])
        )
    except APIError as e:
        context["error"] = e


@then(parsers.parse("la solicitud es rechazada con código {status:d} {codigo}"))
def step_verificar_error(context, status, codigo):
    from fastapi import HTTPException

    err = context["error"]
    assert err is not None
    if isinstance(err, HTTPException):
        assert err.status_code == status
        assert err.detail["error_code"] == codigo
    else:
        assert err.status_code == status
        assert err.error_code == codigo


@then("no se duplica la entidad en el directorio")
def step_no_duplicado(context):
    lista = asyncio.run(context["service"].listar_proveedores(context["cid"]))
    assert len(lista) == 1


# Escenario: Registro de contrato y alertas
@given("un proveedor registrado en el directorio")
def step_dado_proveedor(context):
    req = CrearProveedorRequest(
        ruc="20999888777",
        razon_social="Ascensores del Pacífico SAC",
        rubro="ASCENSORES",
        contacto_nombre="Lucia Torres",
        contacto_telefono="988777666",
        contacto_email="lucia@ascensores.pe",
    )
    context["proveedor"] = asyncio.run(
        context["service"].registrar_proveedor(context["cid"], req, context["uid_junta"])
    )


@when(
    parsers.parse(
        "la Junta registra un contrato de servicio con fecha de inicio y fecha de fin a {dias:d} días"
    )
)
def step_registrar_contrato_dias(context, dias):
    hoy = date.today()
    req = CrearContratoRequest(
        numero_contrato="CTR-PACIFICO-01",
        tipo_documento="CONTRATO_SERVICIO",
        descripcion="Mantenimiento preventivo mensual de 2 ascensores",
        monto_mensual=Decimal("1200.00"),
        moneda="PEN",
        fecha_inicio=hoy - timedelta(days=10),
        fecha_fin=hoy + timedelta(days=dias),
    )
    context["contrato"] = asyncio.run(
        context["service"].registrar_contrato(
            context["cid"], context["proveedor"].id, req, context["uid_junta"]
        )
    )


@then("el contrato queda en estado POR_VENCER con alerta preventiva de 60 días")
def step_verificar_estado_por_vencer(context):
    assert context["contrato"].estado == "POR_VENCER"


@then(parsers.parse("muestra {dias:d} días restantes para el vencimiento"))
def step_verificar_dias(context, dias):
    assert context["contrato"].dias_restantes == dias


# Escenario: Custodia digital y versionamiento
@given("un contrato vigente registrado en el sistema")
def step_dado_contrato_vigente(context):
    req_p = CrearProveedorRequest(
        ruc="20777666555",
        razon_social="Seguridad 360 SAC",
        rubro="SEGURIDAD",
        contacto_nombre="Marcos Diaz",
        contacto_telefono="933444555",
        contacto_email="mdiaz@seguridad360.pe",
    )
    p = asyncio.run(
        context["service"].registrar_proveedor(context["cid"], req_p, context["uid_junta"])
    )
    hoy = date.today()
    req_c = CrearContratoRequest(
        numero_contrato="CTR-SEG-2026",
        tipo_documento="CONTRATO_SERVICIO",
        descripcion="Vigilancia privada 24/7",
        monto_mensual=Decimal("4500.00"),
        moneda="PEN",
        fecha_inicio=hoy,
        fecha_fin=hoy + timedelta(days=180),
    )
    context["contrato"] = asyncio.run(
        context["service"].registrar_contrato(context["cid"], p.id, req_c, context["uid_junta"])
    )


@when("la Junta sube el documento PDF original firmado")
def step_sube_pdf_original(context):
    from fastapi import UploadFile

    pdf = BytesIO(b"%PDF-1.4\nContrato Original Firmado\n%%EOF")
    upload = UploadFile(file=pdf, filename="contrato_vigilancia.pdf")
    context["doc_v1"] = asyncio.run(
        context["service"].subir_documento_version(
            context["cid"], context["contrato"].id, upload, context["uid_junta"]
        )
    )


@then("queda almacenado en el repositorio privado con versión 1")
def step_verificar_v1(context):
    assert context["doc_v1"].version == 1
    assert context["doc_v1"].archivo_nombre == "contrato_vigilancia.pdf"


@when("posteriormente se sube una addenda en PDF indicando el motivo de reemplazo")
def step_sube_addenda(context):
    from fastapi import UploadFile

    pdf_v2 = BytesIO(b"%PDF-1.5\nAddenda Incremento Personal\n%%EOF")
    upload_v2 = UploadFile(file=pdf_v2, filename="addenda_01.pdf")
    context["doc_v2"] = asyncio.run(
        context["service"].subir_documento_version(
            context["cid"],
            context["contrato"].id,
            upload_v2,
            context["uid_junta"],
            motivo_reemplazo="Ampliación a 2 guardias nocturnos",
        )
    )


@then("se genera la versión 2 del documento")
def step_verificar_v2(context):
    assert context["doc_v2"].version == 2
    assert context["doc_v2"].motivo_reemplazo == "Ampliación a 2 guardias nocturnos"


@then("la versión 1 anterior se conserva intacta en el historial para auditoría")
def step_conserva_v1(context):
    b1, m1, n1 = asyncio.run(
        context["service"].descargar_documento_version(context["cid"], context["contrato"].id, 1)
    )
    assert b1 == b"%PDF-1.4\nContrato Original Firmado\n%%EOF"

    b2, m2, n2 = asyncio.run(
        context["service"].descargar_documento_version(context["cid"], context["contrato"].id, 2)
    )
    assert b2 == b"%PDF-1.5\nAddenda Incremento Personal\n%%EOF"


# Escenario: Restricción de permisos y aislamiento por rol
@given("un usuario con rol AUDITOR en el condominio")
def step_dado_auditor(context):
    assert context["uid_auditor"] is not None


@when("consulta el directorio de proveedores y contratos")
def step_auditor_consulta(context):
    context["lista_auditor"] = asyncio.run(context["service"].listar_proveedores(context["cid"]))


@then("puede visualizar la información y descargar los documentos")
def step_auditor_ve(context):
    assert isinstance(context["lista_auditor"], list)


@when("el auditor intenta registrar o modificar un proveedor")
def step_auditor_intenta_crear(context):
    from src.core.authorization import autorizar_condominio

    usuario_auditor = {
        "sub": str(context["uid_auditor"]),
        "rol": "AUDITOR",
        "condominio_id": str(context["cid"]),
    }
    try:
        autorizar_condominio(usuario_auditor, context["cid"], escritura=True)
    except Exception as e:
        context["error"] = e
