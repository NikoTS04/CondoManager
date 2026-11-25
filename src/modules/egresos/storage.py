"""Adaptador de documentos privados para CON-51.

El módulo consume operaciones genéricas de guardar/leer/eliminar y no importa ni
utiliza la conciliación de vouchers. El driver existente aporta almacenamiento
privado local/Supabase y el catálogo de contenido PNG/JPEG/PDF configurado por el
proyecto.
"""

from pathlib import Path

from src.core.errors import APIError
from src.modules.pagos.storage import TipoDocumento, get_voucher_storage


class EgresosStorage:
    def __init__(self, backend=None):
        self._backend = backend or get_voucher_storage()

    @staticmethod
    def _traducir_error(exc: APIError) -> APIError:
        codigo = {
            "VOUCHER_INVALIDO": "DOCUMENTO_INVALIDO",
            "FORMATO_VOUCHER_NO_SOPORTADO": "FORMATO_NO_SOPORTADO",
            "VOUCHER_ALMACENAMIENTO_NO_DISPONIBLE": "ALMACENAMIENTO_NO_DISPONIBLE",
            "VOUCHER_NO_DISPONIBLE": "DOCUMENTO_NO_DISPONIBLE",
        }.get(exc.error_code, exc.error_code)
        return APIError(exc.status_code, codigo, exc.mensaje)

    def validar(self, contenido: bytes) -> tuple[str, str]:
        try:
            return self._backend.validar_documento(contenido, TipoDocumento.VOUCHER)
        except APIError as exc:
            raise self._traducir_error(exc) from exc

    def guardar(self, contenido: bytes) -> tuple[str, str]:
        try:
            return self._backend.guardar(contenido, TipoDocumento.VOUCHER)
        except APIError as exc:
            raise self._traducir_error(exc) from exc

    def leer(self, clave: str) -> bytes:
        try:
            contenido = self._backend.ruta(clave)
            return contenido.read_bytes() if isinstance(contenido, Path) else contenido
        except APIError as exc:
            raise self._traducir_error(exc) from exc

    def eliminar(self, clave: str) -> None:
        try:
            self._backend.eliminar(clave)
        except APIError as exc:
            raise self._traducir_error(exc) from exc


def get_egresos_storage() -> EgresosStorage:
    return EgresosStorage()
