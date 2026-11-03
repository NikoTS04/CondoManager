"""Almacén local privado de evidencia. Nunca acepta rutas aportadas por clientes."""

import io
import os
import re
import warnings
import zipfile
from enum import Enum
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from src.core.config import settings
from src.core.errors import APIError

MAX_BYTES = 5 * 1024 * 1024
NOMBRE = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.(?:png|jpg|pdf)")
NOMBRE_DOCUMENTO = re.compile(
    r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.(?:png|jpg|pdf|docx)"
)
MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class TipoDocumento(str, Enum):
    VOUCHER = "VOUCHER"
    PRORRATEO = "PRORRATEO"


CATALOGO_DOCUMENTOS = {
    TipoDocumento.VOUCHER: {
        "max_bytes": 5 * 1024 * 1024,
        "formatos_permitidos": {"png", "jpg", "pdf"},
        "mimes": {"png": "image/png", "jpg": "image/jpeg", "pdf": "application/pdf"},
    },
    TipoDocumento.PRORRATEO: {
        "max_bytes": 10 * 1024 * 1024,
        "formatos_permitidos": {"pdf", "docx"},
        "mimes": {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    },
}


class VoucherStorage:
    def __init__(self, directorio: str | Path | None = None):
        ruta = Path(directorio or settings.VOUCHERS_DIR)
        if not ruta.is_absolute():
            ruta = Path(__file__).resolve().parents[3] / ruta
        self.directorio = ruta.resolve()

    @staticmethod
    def validar(datos: bytes) -> tuple[str, str]:
        return VoucherStorage.validar_documento(datos, TipoDocumento.VOUCHER)

    @staticmethod
    def validar_documento(
        datos: bytes, tipo: TipoDocumento = TipoDocumento.VOUCHER
    ) -> tuple[str, str]:
        config = CATALOGO_DOCUMENTOS.get(tipo, CATALOGO_DOCUMENTOS[TipoDocumento.VOUCHER])
        limite_bytes = config["max_bytes"]

        if len(datos) > limite_bytes:
            raise APIError(
                413,
                "ARCHIVO_DEMASIADO_GRANDE",
                f"El máximo permitido para {tipo.value.lower()} es {limite_bytes // (1024 * 1024)} MiB.",
            )
        if not datos:
            raise APIError(
                422,
                "VOUCHER_INVALIDO",
                f"Adjunte un archivo válido para {tipo.value.lower()}.",
            )

        if tipo == TipoDocumento.PRORRATEO:
            # Soporta PDF y DOCX
            if datos.startswith(b"%PDF-"):
                if not datos.rstrip().endswith(b"%%EOF"):
                    raise APIError(422, "DOCUMENTO_INVALIDO", "PDF incompleto o corrupto.")
                try:
                    pdf = PdfReader(io.BytesIO(datos), strict=True)
                    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 500:
                        raise APIError(422, "DOCUMENTO_INVALIDO", "PDF protegido o fuera de límites.")
                    return "pdf", MIME["pdf"]
                except Exception as exc:
                    raise APIError(422, "DOCUMENTO_INVALIDO", "No se pudo validar el archivo PDF.") from exc

            if datos.startswith(b"PK\x03\x04"):
                try:
                    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
                        nombres = set(zf.namelist())
                        if "[Content_Types].xml" not in nombres or "word/document.xml" not in nombres:
                            raise APIError(422, "DOCUMENTO_INVALIDO", "El archivo DOCX no es válido.")
                    return "docx", MIME["docx"]
                except zipfile.BadZipFile as exc:
                    raise APIError(422, "DOCUMENTO_INVALIDO", "El archivo DOCX está dañado.") from exc

            raise APIError(415, "FORMATO_NO_SOPORTADO", "Formato no soportado para prorrateo. Use PDF o DOCX.")

        # Por defecto validación de VOUCHER
        try:
            if datos.startswith(b"%PDF-"):
                if not datos.rstrip().endswith(b"%%EOF"):
                    raise ValueError("PDF incompleto")
                pdf = PdfReader(io.BytesIO(datos), strict=True)
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 100:
                    raise ValueError("PDF protegido o fuera de límites")
                return "pdf", MIME["pdf"]
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(datos)) as imagen:
                    formato = imagen.format
                    if formato not in {"PNG", "JPEG"}:
                        raise APIError(415, "FORMATO_VOUCHER_NO_SOPORTADO", "Use PNG, JPEG o PDF.")
                    if imagen.width * imagen.height > 20_000_000:
                        raise ValueError("Imagen fuera de límites")
                    imagen.verify()
                # verify no decodifica el raster JPEG: comprobar también su contenido.
                with Image.open(io.BytesIO(datos)) as imagen:
                    imagen.load()
            extension = "png" if formato == "PNG" else "jpg"
            return extension, MIME[extension]
        except APIError:
            raise
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            if not datos.startswith((b"%PDF-", b"\x89PNG", b"\xff\xd8")):
                raise APIError(415, "FORMATO_VOUCHER_NO_SOPORTADO", "Use PNG, JPEG o PDF.") from exc
            raise APIError(
                422, "VOUCHER_INVALIDO", "El contenido no es un PNG, JPG o PDF válido."
            ) from exc
        except Exception as exc:
            # Los errores de parser no deben divulgar contenido de evidencia ni producir 500.
            raise APIError(
                422, "VOUCHER_INVALIDO", "No se pudo validar el archivo adjunto."
            ) from exc

    def guardar(self, datos: bytes, tipo: TipoDocumento = TipoDocumento.VOUCHER) -> tuple[str, str]:
        extension, content_type = self.validar_documento(datos, tipo)
        nombre = f"{uuid4()}.{extension}"
        destino = self.directorio / nombre
        try:
            self.directorio.mkdir(parents=True, exist_ok=True)
            with destino.open("xb") as archivo:
                archivo.write(datos)
                archivo.flush()
                os.fsync(archivo.fileno())
        except OSError as exc:
            try:
                destino.unlink(missing_ok=True)
            except OSError:
                pass  # La limpieza recuperable reintentará; no ocultar el error controlado.
            raise APIError(
                503, "VOUCHER_ALMACENAMIENTO_NO_DISPONIBLE", "No se pudo guardar el archivo."
            ) from exc
        return nombre, content_type

    def ruta(self, nombre: str) -> Path:
        if not NOMBRE_DOCUMENTO.fullmatch(nombre):
            raise APIError(
                404, "VOUCHER_NO_DISPONIBLE", "La evidencia no está en el almacén local."
            )
        # Prevención estricta de Path Traversal
        if ".." in nombre or "/" in nombre or "\\" in nombre:
            raise APIError(
                404, "VOUCHER_NO_DISPONIBLE", "Ruta de archivo no autorizada."
            )
        ruta = self.directorio / nombre
        if ruta.is_symlink() or ruta.resolve().parent != self.directorio.resolve() or not ruta.is_file():
            raise APIError(404, "VOUCHER_NO_DISPONIBLE", "La evidencia local no está disponible.")
        return ruta

    def eliminar(self, nombre: str):
        if NOMBRE_DOCUMENTO.fullmatch(nombre) and ".." not in nombre and "/" not in nombre and "\\" not in nombre:
            ruta = self.directorio / nombre
            if not ruta.is_symlink():
                ruta.unlink(missing_ok=True)

    def eliminar_seguro(self, nombre: str, es_vigente: bool = False):
        if es_vigente:
            raise APIError(
                409,
                "EVIDENCIA_VIGENTE_NO_ELIMINABLE",
                "No se puede eliminar una evidencia vigente o asociada a un comprobante activo.",
            )
        self.eliminar(nombre)
