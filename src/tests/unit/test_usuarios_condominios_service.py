"""Pruebas unitarias del Dominio de Usuarios/Condominios (PROC-05)."""

import uuid

import pytest
from passlib.hash import pbkdf2_sha256

from src.modules.condominios.schemas import CrearCondominioRequest, ReglaMoraEnum
from src.modules.condominios.service import (
    CondominiosService,
    ConfiguracionMoraInvalidaException,
)
from src.modules.usuarios.schemas import CrearUsuarioRequest, RolEnum
from src.modules.usuarios.service import (
    CondominioNoExisteException,
    EmailYaRegistradoException,
    RolYaAsignadoException,
    UsuarioNoEncontradoException,
    UsuariosService,
)


def test_hash_password_no_almacena_texto_plano():
    password = "claveSegura123"
    hash_resultante = UsuariosService.hash_password(password)

    assert hash_resultante != password
    assert password not in hash_resultante
    assert pbkdf2_sha256.verify(password, hash_resultante)
    assert not pbkdf2_sha256.verify("otraClave123", hash_resultante)


def test_crear_usuario_rechaza_password_corto():
    with pytest.raises(ValueError):
        CrearUsuarioRequest(
            email="residente@gmail.com",
            password="corta",
            nombre="María",
            apellido="Flores",
            documento_identidad="74125896",
        )


def test_matriz_rbac_solo_admite_roles_del_dominio():
    assert {rol.value for rol in RolEnum} == {
        "SUPERADMIN",
        "ADMIN_JUNTA",
        "AUDITOR",
        "RESIDENTE",
    }


def test_regla_monto_fijo_requiere_monto_positivo():
    request = CrearCondominioRequest(
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
        regla_mora_tipo=ReglaMoraEnum.MONTO_FIJO,
        monto_mora_fijo=None,
    )

    with pytest.raises(ConfiguracionMoraInvalidaException):
        CondominiosService.validar_regla_mora(request)


def test_regla_porcentaje_saldo_es_valida_por_defecto():
    request = CrearCondominioRequest(
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
        regla_mora_tipo=ReglaMoraEnum.PORCENTAJE_SALDO,
        tasa_mora_porcentaje="2.5000",
    )

    CondominiosService.validar_regla_mora(request)


def test_monto_mora_normalizado_a_dos_decimales():
    request = CrearCondominioRequest(
        nombre="Villa Bonita 3",
        direccion="Av. Los Rosales 245",
        monto_mora_fijo="25",
    )

    assert str(request.monto_normalizado()) == "25.00"


def test_excepciones_de_dominio_capturan_identificadores():
    usuario_id = uuid.uuid4()
    condominio_id = uuid.uuid4()

    assert EmailYaRegistradoException("a@b.com").email == "a@b.com"
    assert UsuarioNoEncontradoException(usuario_id).usuario_id == usuario_id
    assert CondominioNoExisteException(condominio_id).condominio_id == condominio_id

    duplicado = RolYaAsignadoException(usuario_id, condominio_id)
    assert duplicado.usuario_id == usuario_id
    assert duplicado.condominio_id == condominio_id
