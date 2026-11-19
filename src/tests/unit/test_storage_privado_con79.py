"""Pruebas unitarias de CON-79: Almacén privado de evidencias y documentos."""

import io
import zipfile

import pytest
from pypdf import PdfWriter

from src.core.errors import APIError
from src.modules.pagos.storage import TipoDocumento, VoucherStorage


def crear_pdf_valido() -> bytes:
    buffer = io.BytesIO()
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    pdf.write(buffer)
    return buffer.getvalue()


def crear_docx_valido() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types></Types>")
        zf.writestr("word/document.xml", b"<w:document></w:document>")
    return buffer.getvalue()


def test_guardar_y_recuperar_prorrateo_pdf(tmp_path):
    storage = VoucherStorage(tmp_path)
    contenido = crear_pdf_valido()
    nombre, content_type = storage.guardar(contenido, tipo=TipoDocumento.PRORRATEO)

    assert nombre.endswith(".pdf")
    assert content_type == "application/pdf"
    assert storage.ruta(nombre).read_bytes() == contenido


def test_guardar_y_recuperar_prorrateo_docx(tmp_path):
    storage = VoucherStorage(tmp_path)
    contenido = crear_docx_valido()
    nombre, content_type = storage.guardar(contenido, tipo=TipoDocumento.PRORRATEO)

    assert nombre.endswith(".docx")
    assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert storage.ruta(nombre).read_bytes() == contenido


def test_rechazo_prorrateo_invalido(tmp_path):
    storage = VoucherStorage(tmp_path)
    with pytest.raises(APIError) as exc:
        storage.guardar(b"<html>no es docx ni pdf</html>", tipo=TipoDocumento.PRORRATEO)
    assert exc.value.status_code == 415


def test_rechazo_docx_corrupto(tmp_path):
    storage = VoucherStorage(tmp_path)
    # Empieza como zip pero no contiene xml obligatorio
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("test.txt", b"hola")
    with pytest.raises(APIError) as exc:
        storage.guardar(buffer.getvalue(), tipo=TipoDocumento.PRORRATEO)
    assert exc.value.status_code == 422


def test_limite_tamanio_prorrateo_10_mib(tmp_path):
    storage = VoucherStorage(tmp_path)
    with pytest.raises(APIError) as exc:
        storage.guardar(b"x" * (10 * 1024 * 1024 + 1), tipo=TipoDocumento.PRORRATEO)
    assert exc.value.status_code == 413


def test_eliminar_seguro_protege_evidencias_vigentes(tmp_path):
    storage = VoucherStorage(tmp_path)
    contenido = crear_pdf_valido()
    nombre, _ = storage.guardar(contenido)

    # Intentar eliminar evidencia vigente debe ser rechazado con 409
    with pytest.raises(APIError) as exc:
        storage.eliminar_seguro(nombre, es_vigente=True)
    assert exc.value.status_code == 409
    assert exc.value.error_code == "EVIDENCIA_VIGENTE_NO_ELIMINABLE"
    assert storage.ruta(nombre).is_file()

    # Si es huérfana (no vigente), se permite la eliminación física
    storage.eliminar_seguro(nombre, es_vigente=False)
    with pytest.raises(APIError) as exc_ruta:
        storage.ruta(nombre)
    assert exc_ruta.value.status_code == 404


@pytest.mark.parametrize(
    "ataque",
    [
        "../../etc/passwd",
        "..\\..\\Windows\\System32\\cmd.exe",
        "sub/archivo.pdf",
        "https://malicioso.com/voucher.pdf",
        "archivo.exe",
    ],
)
def test_mitigacion_path_traversal(tmp_path, ataque):
    storage = VoucherStorage(tmp_path)
    with pytest.raises(APIError) as exc:
        storage.ruta(ataque)
    assert exc.value.status_code == 404
