"""Docker instala requirements.txt, no pyproject.toml."""

import re
import tomllib
from pathlib import Path


def test_docker_incluye_dependencias_de_ejecucion():
    def nombre(requisito):
        return re.split(r"[\[<>=!~; ]", requisito, maxsplit=1)[0].lower().replace("_", "-")

    declaradas = tomllib.loads(Path("pyproject.toml").read_text())["project"]["dependencies"]
    instaladas = {nombre(r) for r in Path("requirements.txt").read_text().splitlines()}
    assert {nombre(r) for r in declaradas} <= instaladas
