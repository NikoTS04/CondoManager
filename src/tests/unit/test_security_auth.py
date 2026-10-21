"""Pruebas unitarias de Autenticación, JWT y RBAC (PROC-05)."""

import asyncio
from datetime import timedelta

import pytest

from src.core.security import (
    HTTPException,
    create_access_token,
    decode_access_token,
    hash_password,
    require_role,
    verify_password,
)
from src.modules.usuarios.schemas import LoginRequest
from src.modules.usuarios.service import (
    CredencialesInvalidasException,
    UsuariosService,
)


def test_password_hashing_and_verification():
    """Verifica que el hashing PBKDF2 genere hashes válidos y seguros."""
    raw = "SuperSecretPassword123!"
    hashed = hash_password(raw)

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Verifica la emisión y decodificación de tokens JWT con claims."""
    payload = {
        "sub": "user-uuid-123",
        "email": "admin@villabonita3.pe",
        "rol": "ADMIN_JUNTA",
        "condominio_id": "vb3-condo",
        "departamentos": [],
    }
    token = create_access_token(payload, expires_delta=timedelta(minutes=10))
    decoded = decode_access_token(token)

    assert decoded["sub"] == "user-uuid-123"
    assert decoded["email"] == "admin@villabonita3.pe"
    assert decoded["rol"] == "ADMIN_JUNTA"
    assert decoded["condominio_id"] == "vb3-condo"


def test_jwt_expired_token():
    """Verifica que un token expirado lance un error HTTP 401."""
    payload = {"sub": "user-expired"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error_code"] == "TOKEN_EXPIRADO"


@pytest.mark.asyncio
async def test_usuarios_service_autenticacion_exitosa(identidad_piloto):
    """Valida la autenticación de usuarios precargados en el piloto."""
    req_admin = LoginRequest(email="admin@villabonita3.pe", password="Admin123!")
    res_admin = await UsuariosService(identidad_piloto).autenticar(req_admin)
    assert res_admin.usuario.rol == "ADMIN_JUNTA"
    assert res_admin.token_type == "bearer"
    assert res_admin.access_token is not None

    req_residente = LoginRequest(email="residente102@villabonita3.pe", password="Residente123!")
    res_residente = await UsuariosService(identidad_piloto).autenticar(req_residente)
    assert res_residente.usuario.rol == "RESIDENTE"
    assert res_residente.usuario.departamentos[0].numero == "102"
    assert res_residente.usuario.departamentos[0].tipo_relacion == "PROPIETARIO_TITULAR"


@pytest.mark.asyncio
async def test_usuarios_service_credenciales_invalidas(identidad_piloto):
    """Verifica el rechazo ante contraseña errónea o usuario inexistente."""
    req_err = LoginRequest(email="admin@villabonita3.pe", password="WrongPassword!")
    with pytest.raises(CredencialesInvalidasException):
        await UsuariosService(identidad_piloto).autenticar(req_err)

    req_inexistente = LoginRequest(email="nadie@villabonita3.pe", password="Password123!")
    with pytest.raises(CredencialesInvalidasException):
        await UsuariosService(identidad_piloto).autenticar(req_inexistente)


def test_require_role_enforcement():
    """Verifica que el guardián RBAC permita o deniegue según el rol."""
    admin_checker = require_role(["ADMIN_JUNTA", "SUPERADMIN"])

    # 1. Usuario con rol permitido -> Pasa
    admin_user = {"sub": "u1", "rol": "ADMIN_JUNTA"}
    result = asyncio.run(admin_checker(admin_user))
    assert result == admin_user

    # 2. Usuario con rol RESIDENTE intentando administrar -> 403 Forbidden
    residente_user = {"sub": "u2", "rol": "RESIDENTE"}
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(admin_checker(residente_user))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "ACCESO_DENEGADO"

    # 3. Usuario con rol AUDITOR intentando mutar -> 403 Forbidden
    auditor_user = {"sub": "u3", "rol": "AUDITOR"}
    with pytest.raises(HTTPException) as exc_info_audit:
        asyncio.run(admin_checker(auditor_user))
    assert exc_info_audit.value.status_code == 403


@pytest.mark.parametrize(
    ("email", "password", "relacion"),
    [
        ("residente102@villabonita3.pe", "Residente123!", "PROPIETARIO_TITULAR"),
        ("inquilino504@villabonita3.pe", "Inquilino123!", "INQUILINO"),
    ],
)
@pytest.mark.asyncio
async def test_residentes_comparten_rol_sql_y_vinculos_en_jwt(
    email, password, relacion, identidad_piloto
):
    response = await UsuariosService(identidad_piloto).autenticar(
        LoginRequest(email=email, password=password)
    )
    perfil = response.usuario.model_dump(mode="json")
    claims = decode_access_token(response.access_token)
    assert claims["rol"] == perfil["rol"] == "RESIDENTE"
    assert claims["session_version"] == 2
    assert claims["departamentos"] == perfil["departamentos"]
    assert claims["departamentos"][0]["tipo_relacion"] == relacion
    assert "tipo_relacion" not in perfil


@pytest.mark.asyncio
async def test_administrativos_sin_tenencia_no_reciben_relaciones_inventadas(identidad_piloto):
    administrativos = [
        await identidad_piloto.perfil(u)
        for u in identidad_piloto.usuarios.values()
        if not identidad_piloto.perfiles[u.email]["departamentos"]
    ]
    assert administrativos
    assert all(u.departamentos == [] for u in administrativos)


@pytest.mark.parametrize("rol", ["PROPIETARIO", "INQUILINO", "SISTEMA_AUTOMATICO", "DESCONOCIDO"])
def test_roles_fuera_del_sql_requieren_renovar_sesion(rol):
    token = create_access_token({"sub": "usuario", "rol": rol})
    with pytest.raises(HTTPException) as error:
        decode_access_token(token)
    assert error.value.status_code == 401
    assert error.value.detail["error_code"] == "SESION_DESACTUALIZADA"


def test_token_de_contrato_anterior_no_se_restaura():
    from src.core.security import ALGORITHM, SECRET_KEY, jwt

    token = jwt.encode({"sub": "usuario", "rol": "ADMIN_JUNTA"}, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as error:
        decode_access_token(token)
    assert error.value.detail["error_code"] == "SESION_DESACTUALIZADA"


def test_guardia_administrativa_no_permite_anonimos(monkeypatch):
    monkeypatch.setenv("AUTH_STRICT_ENFORCEMENT", "false")
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_role(["ADMIN_JUNTA"])(None))
    assert error.value.status_code == 401
