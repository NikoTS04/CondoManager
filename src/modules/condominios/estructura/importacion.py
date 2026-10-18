"""Lectura CSV sin efectos laterales ni conversiones de coeficientes a float."""

import csv
import io

from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.condominios.estructura.schemas import (
    CrearDepartamentoRequest,
    CrearEdificioRequest,
    FilaImportacion,
)

MAX_BYTES = 2 * 1024 * 1024
MAX_FILAS = 5000


def leer_csv(contenido: bytes) -> list[FilaImportacion]:
    if len(contenido) > MAX_BYTES:
        raise APIError(422, "CSV_INVALIDO", "El CSV supera el máximo de 2 MiB.")
    try:
        texto = contenido.decode("utf-8-sig")
        muestra = texto.splitlines()[0] if texto else ""
        separador = ";" if muestra.count(";") > muestra.count(",") else ","
        lector = csv.reader(io.StringIO(texto, newline=""), delimiter=separador, strict=True)
        cabecera = [c.strip().lower() for c in next(lector)]
        cabecera = ["coeficiente" if c == "coeficiente_participacion" else c for c in cabecera]
        if len(set(cabecera)) != len(cabecera) or not {
            "numero",
            "piso",
            "edificio",
            "coeficiente",
        }.issubset(cabecera):
            raise APIError(422, "CSV_INVALIDO", "Se requieren numero,piso,edificio,coeficiente.")
        if set(cabecera) - {"numero", "piso", "edificio", "coeficiente", "total_pisos"}:
            raise APIError(422, "CSV_INVALIDO", "El CSV contiene columnas desconocidas.")
        filas = []
        while True:
            numero_fila = lector.line_num + 1
            try:
                valores = next(lector)
            except StopIteration:
                break
            if not valores or not any(v.strip() for v in valores):
                continue
            if len(filas) >= MAX_FILAS:
                raise APIError(422, "CSV_INVALIDO", "El máximo es 5000 filas de datos.")
            datos = dict(zip(cabecera, (v.strip() for v in valores)))
            fila = FilaImportacion(
                fila=numero_fila,
                numero=datos.get("numero", "").upper(),
                edificio=datos.get("edificio", ""),
                coeficiente=datos.get("coeficiente", ""),
            )
            if len(valores) != len(cabecera):
                fila.errores.append("Cantidad de columnas incorrecta.")
            try:
                piso_texto = datos.get("piso", "")
                piso = (
                    int(piso_texto)
                    if len(piso_texto) <= 5 and piso_texto.isascii() and piso_texto.isdigit()
                    else 0
                )
                dto = CrearDepartamentoRequest(
                    numero=fila.numero, piso=piso, coeficiente_participacion=fila.coeficiente
                )
                fila.numero, fila.piso = dto.numero, dto.piso
                fila.coeficiente = f"{dto.coeficiente_participacion:.4f}"
            except ValidationError as exc:
                fila.errores.extend(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())
            pisos = datos.get("total_pisos", "")
            if pisos:
                if (
                    len(pisos) <= 5
                    and pisos.isascii()
                    and pisos.isdigit()
                    and 1 <= int(pisos) <= 32767
                ):
                    fila.total_pisos = int(pisos)
                else:
                    fila.errores.append("total_pisos debe ser entero entre 1 y 32767.")
            try:
                CrearEdificioRequest(nombre_bloque=fila.edificio, total_pisos=1)
            except ValidationError:
                fila.errores.append(
                    "edificio debe tener entre 1 y 100 caracteres y no contener nulos."
                )
            filas.append(fila)
        if not filas:
            raise APIError(422, "CSV_INVALIDO", "El archivo no contiene filas de datos.")
        return filas
    except (UnicodeDecodeError, csv.Error, StopIteration, ValueError) as exc:
        raise APIError(422, "CSV_INVALIDO", "El archivo debe ser un CSV UTF-8 válido.") from exc
