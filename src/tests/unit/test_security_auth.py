"""Pruebas unitarias de Autenticación, JWT y RBAC (PROC-05)."""

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


def test_usuarios_service_autenticacion_exitosa():
    """Valida la autenticación de usuarios precargados en el piloto."""
    req_admin = LoginRequest(email="admin@villabonita3.pe", password="Admin123!")
    res_admin = UsuariosService.autenticar(req_admin)
    assert res_admin.usuario.rol == "ADMIN_JUNTA"
    assert res_admin.token_type == "bearer"
    assert res_admin.access_token is not None

    req_residente = LoginRequest(email="residente102@villabonita3.pe", password="Residente123!")
    res_residente = UsuariosService.autenticar(req_residente)
    assert res_residente.usuario.rol == "PROPIETARIO"
    assert "102" in res_residente.usuario.departamentos


def test_usuarios_service_credenciales_invalidas():
    """Verifica el rechazo ante contraseña errónea o usuario inexistente."""
    req_err = LoginRequest(email="admin@villabonita3.pe", password="WrongPassword!")
    with pytest.raises(CredencialesInvalidasException):
        UsuariosService.autenticar(req_err)

    req_inexistente = LoginRequest(email="nadie@villabonita3.pe", password="Password123!")
    with pytest.raises(CredencialesInvalidasException):
        UsuariosService.autenticar(req_inexistente)


import asyncio


def test_require_role_enforcement():
    """Verifica que el guardián RBAC permita o deniegue según el rol."""
    admin_checker = require_role(["ADMIN_JUNTA", "SUPERADMIN"])

    # 1. Usuario con rol permitido -> Pasa
    admin_user = {"sub": "u1", "rol": "ADMIN_JUNTA"}
    result = asyncio.run(admin_checker(admin_user))
    assert result == admin_user

    # 2. Usuario con rol denegado (PROPIETARIO) -> 403 Forbidden
    residente_user = {"sub": "u2", "rol": "PROPIETARIO"}
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(admin_checker(residente_user))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "ACCESO_DENEGADO"

    # 3. Usuario con rol AUDITOR intentando mutar -> 403 Forbidden
    auditor_user = {"sub": "u3", "rol": "AUDITOR"}
    with pytest.raises(HTTPException) as exc_info_audit:
        asyncio.run(admin_checker(auditor_user))
    assert exc_info_audit.value.status_code == 403

