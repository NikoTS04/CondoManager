"""Validación de datos reales de CSV y contratos de precisión de CON-3."""

import pytest
from pydantic import ValidationError

from src.core.errors import APIError
from src.modules.condominios.estructura.importacion import leer_csv
from src.modules.condominios.estructura.schemas import (
    CrearDepartamentoRequest,
    EstadoDepartamentoRequest,
)


@pytest.mark.parametrize(
    "valor", [0.72, 1, "NaN", "Infinity", "-1", "0", "100.0001", "1.00001", "1e-2"]
)
def test_rechaza_coeficientes_fuera_de_contrato(valor):
    with pytest.raises(ValidationError):
        CrearDepartamentoRequest(numero="101", piso=1, coeficiente_participacion=valor)


def test_preserva_ceros_del_numero_y_coeficiente_decimal():
    dto = CrearDepartamentoRequest(numero=" 001b ", piso=1, coeficiente_participacion="0.7200")
    assert dto.numero == "001B"
    assert str(dto.coeficiente_participacion) == "0.7200"
    with pytest.raises(ValidationError):
        EstadoDepartamentoRequest(activo="false")


def test_csv_bom_comillas_multilinea_y_lineas_originales():
    filas = leer_csv(
        '\ufeffnumero,piso,edificio,coeficiente,total_pisos\r\n\r\n001,1,"Torre,\n Norte",0.7200,14\r\n102,0,Sur,NaN,2\r\n'.encode()
    )
    assert len(filas) == 2
    assert filas[0].fila == 3 and filas[1].fila == 5
    assert filas[0].edificio == "Torre,\n Norte"
    assert filas[0].coeficiente == "0.7200"
    assert len(filas[1].errores) == 2


def test_csv_semicolon_alias_y_columnas_desordenadas():
    fila = leer_csv(b"edificio;coeficiente_participacion;numero;piso\nNorte;1.25;101;1\n")[0]
    assert fila.numero == "101" and fila.coeficiente == "1.2500"


def test_piso_excesivamente_largo_y_nombre_nulo_son_errores_por_fila():
    filas = leer_csv(
        (
            "numero,piso,edificio,coeficiente,total_pisos\n101,"
            + "9" * 5000
            + ",Norte,1,2\n102,1,Nor\x00te,1,2\n103,1,Norte,1,2\n"
        ).encode()
    )
    assert filas[0].errores and filas[1].errores
    assert not filas[2].errores


@pytest.mark.parametrize(
    "contenido",
    [
        b"",
        b"numero,piso\n1,1",
        b"\xff",
        b"numero,piso,edificio,coeficiente\n",
        b'numero,piso,edificio,coeficiente\n1,1,"ab,0.7\n',
    ],
)
def test_archivos_invalidos(contenido):
    with pytest.raises(APIError) as error:
        leer_csv(contenido)
    assert error.value.error_code == "CSV_INVALIDO"
