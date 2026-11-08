"""Ejecuta regresión financiera en PostgreSQL LOCAL exclusivo de pruebas.

No arranca servicios ni carga .env. La base debe ser desechable: las fixtures
crean/eliminan esquemas. --full ejecuta toda la suite. Nunca crea commits.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRUEBAS = [
    "src/tests/unit/test_pagos_contabilidad_storage.py",
    "src/tests/unit/test_calculo_mora_diaria.py",
    "src/tests/integration/test_pagos_sprint3_db.py",
    "src/tests/bdd/test_pagos_sprint3_bdd.py",
    "src/tests/integration/test_pagos_db.py",
    "src/tests/integration/test_mora_diaria_db.py",
    "src/tests/integration/test_fondos_moras_db.py",
    "src/tests/integration/test_convergencia_con72.py",
    "src/tests/integration/test_notificaciones_pagos_db.py",
    "src/tests/integration/test_estado_cuenta_db.py",
    "src/tests/integration/test_aislamiento_con77_db.py",
    "src/tests/integration/test_emision_db.py",
    "src/tests/integration/test_saldos_favor_db.py",
]


def entorno_pruebas(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "postgresql+asyncpg"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not parsed.path.endswith("_test")
        or parsed.port in (None, 5432)
        or parsed.query
    ):
        raise ValueError("Use PostgreSQL local, puerto exclusivo distinto de 5432 y base *_test.")
    env = os.environ.copy()
    for key in set(env) | {
        "CON3_TEST_DATABASE_URL",
        "CON04_TEST_DATABASE_URL",
        "CON05_TEST_DATABASE_URL",
        "CON06_TEST_DATABASE_URL",
        "CON11_TEST_DATABASE_URL",
        "CON13_TEST_DATABASE_URL",
        "CON39_TEST_DATABASE_URL",
        "CON46_TEST_DATABASE_URL",
    }:
        if key.endswith("TEST_DATABASE_URL"):
            env[key] = url
    env.update(
        DATABASE_URL=url,
        DATABASE_URL_SYNC=url.replace("postgresql+asyncpg:", "postgresql:"),
        JWT_SECRET="sprint3-clave-publica-exclusiva-de-pruebas-no-produccion",
        CONDOMINIO_PILOTO_ID="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        REDIS_URL="redis://127.0.0.1:55426/0",
        DEBUG="false",
        DEMO_MODE="false",
        VOUCHERS_DIR=str(ROOT / "tmp/sprint3/vouchers"),
        PYTHONIOENCODING="utf-8",
    )
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default="postgresql+asyncpg://sprint3:sprint3_local_test@127.0.0.1:55425/sprint3_test",
    )
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    try:
        env = entorno_pruebas(args.database_url)
    except ValueError as exc:
        parser.error(str(exc))
    salida = ROOT / "tmp/sprint3"
    salida.mkdir(parents=True, exist_ok=True)
    nombre = "backend-completo" if args.full else "backend-financiero"
    comando = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pytest",
        "-q",
        f"--junitxml={salida / (nombre + '.xml')}",
        *(
            ["--cov", f"--cov-report=xml:{salida / 'coverage.xml'}", "--cov-report=term"]
            if args.full
            else PRUEBAS
        ),
    ]
    proceso = subprocess.run(
        comando,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    (salida / (nombre + ".log")).write_text(proceso.stdout, encoding="utf-8")
    print(proceso.stdout)
    return proceso.returncode


if __name__ == "__main__":
    raise SystemExit(main())
