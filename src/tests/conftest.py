"""Configuración común de la suite de pruebas.

Debe cargarse antes de que los módulos de prueba importen `src.*`: activa el modo TESTING
para que el engine de SQLAlchemy trabaje con `NullPool` (ver `src/core/database.py`).
"""

import os

os.environ["TESTING"] = "1"
