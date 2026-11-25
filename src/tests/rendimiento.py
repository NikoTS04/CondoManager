"""Aceleraciones de infraestructura de pruebas que no cambian ningún resultado.

1. `verify_password` es una función pura (mismo texto + mismo hash ⇒ mismo resultado) y cuesta
   100 000 iteraciones PBKDF2 por llamada. Cientos de inicios de sesión verifican las mismas
   credenciales demo contra los mismos hashes: se memoriza el resultado por par exacto. Un hash
   nuevo (cambio de contraseña, activación) o un texto distinto siempre se calcula de verdad.
   `hash_password` NO se memoriza: su sal aleatoria es parte del contrato.
2. Recolector de basura: los módulos importados (SQLAlchemy, FastAPI, modelos) se congelan tras
   la colección para que el GC no los recorra en cada ciclo, y se espacian las recolecciones de
   generación joven. No altera la semántica de los objetos.

Desactivable con `CONDOMANAGER_PRUEBAS_SIN_ACELERAR=1` para descartarlo ante cualquier duda.
"""

import functools
import gc
import os
import sys

import src.core.security as seguridad

ACTIVO = os.getenv("CONDOMANAGER_PRUEBAS_SIN_ACELERAR") != "1"
_verificar_original = seguridad.verify_password


@functools.lru_cache(maxsize=4096)
def _verificar_memo(texto: str, hash_guardado: str) -> bool:
    return _verificar_original(texto, hash_guardado)


@functools.wraps(_verificar_original)
def verify_password(plain_password, hashed_password):
    if isinstance(plain_password, str) and isinstance(hashed_password, str):
        return _verificar_memo(plain_password, hashed_password)
    return _verificar_original(plain_password, hashed_password)


def pytest_configure(config):
    if ACTIVO:
        seguridad.verify_password = verify_password


def pytest_collection_finish(session):
    if not ACTIVO:
        return
    # Reexporta en los módulos que hicieron `from src.core.security import verify_password`.
    for modulo in list(sys.modules.values()):
        if modulo is not seguridad and getattr(modulo, "verify_password", None) is (
            _verificar_original
        ):
            modulo.verify_password = verify_password
    gc.collect()
    gc.freeze()
    gc.set_threshold(50_000, 50, 100)
