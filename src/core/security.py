"""Módulo de Seguridad, Criptografía y Control de Acceso RBAC (PROC-05)."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from pydantic import TypeAdapter, ValidationError

from src.core.config import settings
from src.core.errors import APIError
from src.core.roles import VERSION_SESION, RolUsuario
from src.modules.usuarios.repository import get_usuarios_repository
from src.modules.usuarios.schemas import VinculoDepartamentoDTO

try:
    from fastapi import Depends, HTTPException, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    def Depends(dep=None):  # type: ignore
        return dep

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: Any = None):
            super().__init__(str(detail))
            self.status_code = status_code
            self.detail = detail

    class status:  # type: ignore
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403

    HTTPAuthorizationCredentials = Any  # type: ignore

    def HTTPBearer(**kwargs):  # type: ignore
        return None


try:
    import jwt
except ImportError:
    try:
        from jose import jwt
    except ImportError:
        jwt = None

# ============================================================================
# Configuración Criptográfica
# ============================================================================

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas para facilitar el uso del piloto

security_scheme = HTTPBearer(auto_error=False) if HAS_FASTAPI else None


# ============================================================================
# Hashing de Contraseñas (PBKDF2-HMAC-SHA256 con Salt Criptográfico)
# ============================================================================


def hash_password(password: str) -> str:
    """Genera un hash seguro con salting aleatorio usando PBKDF2-SHA256."""
    salt = secrets.token_hex(16)
    iterations = 100_000
    derived_key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt}${derived_key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contraseña en texto plano contra su hash con protección contra timing attacks."""
    try:
        if hashed_password.startswith("$pbkdf2-sha256$"):
            from passlib.hash import pbkdf2_sha256

            return pbkdf2_sha256.verify(plain_password, hashed_password)
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            import bcrypt

            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        test_key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=plain_password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=iterations,
        )
        return secrets.compare_digest(test_key.hex(), expected_hex)
    except Exception:
        return False


# ============================================================================
# Generación y Validación de Tokens JWT
# ============================================================================


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Emite un token JWT con tiempo de expiración y claims del usuario."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.setdefault("auth_revision", 1)
    to_encode.update({"exp": expire, "iat": now, "session_version": VERSION_SESION})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except getattr(jwt, "ExpiredSignatureError", ()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "TOKEN_EXPIRADO",
                "mensaje": "La sesión ha expirado. Vuelva a iniciar sesión.",
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "TOKEN_INVALIDO",
                "mensaje": "Token de autenticación inválido o corrupto.",
            },
        )

    try:
        RolUsuario(payload.get("rol"))
        if payload.get("session_version") != VERSION_SESION or not payload.get("sub"):
            raise ValueError("Contrato de sesión anterior")
        revision = payload.get("auth_revision")
        if type(revision) is not int or revision < 1:
            raise ValueError("Revisión de autorización ausente o inválida")
        vinculos = TypeAdapter(List[VinculoDepartamentoDTO]).validate_python(
            payload.get("departamentos", [])
        )
    except (ValueError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "SESION_DESACTUALIZADA",
                "mensaje": "La sesión utiliza un contrato antiguo o inválido. Inicie sesión de nuevo.",
            },
        )
    payload["departamentos"] = [v.model_dump(mode="json") for v in vinculos]
    return payload


# ============================================================================
# Dependencias de Inyección FastAPI para RBAC
# ============================================================================


async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    repository=Depends(get_usuarios_repository),
) -> Optional[Dict[str, Any]]:
    """Obtiene el contexto del usuario si se proporciona un Bearer token válido, o None."""
    if not auth or not auth.credentials:
        return None
    return await _autenticar_token(auth.credentials, repository)


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    repository=Depends(get_usuarios_repository),
) -> Dict[str, Any]:
    """Exige un Bearer token válido y retorna el payload del usuario autenticado."""
    if not auth or not auth.credentials:
        raise APIError(
            401, "NO_AUTENTICADO", "Se requiere cabecera 'Authorization: Bearer <token>'."
        )
    return await _autenticar_token(auth.credentials, repository)


async def _autenticar_token(token, repository):
    try:
        payload = decode_access_token(token)
    except HTTPException as exc:
        raise APIError(exc.status_code, exc.detail["error_code"], exc.detail["mensaje"]) from exc
    return await validar_sesion(payload, repository)


async def validar_sesion(payload: dict, repository) -> dict:
    """La firma no basta: cada solicitud comprueba cuenta y permisos persistidos."""
    from uuid import UUID

    try:
        uid = UUID(payload["sub"])
    except (ValueError, TypeError, KeyError):
        raise APIError(401, "SESION_REVOCADA", "Inicie sesión de nuevo.") from None
    usuario = await repository.por_id(uid)
    if (
        usuario is None
        or not usuario.esta_activo
        or usuario.auth_revision != payload.get("auth_revision")
    ):
        raise APIError(
            401,
            "SESION_REVOCADA",
            "La cuenta o sesión ya no está habilitada. Inicie sesión de nuevo.",
        )
    perfil = await repository.perfil(usuario, payload.get("condominio_id"))
    if perfil is None or perfil.rol != payload.get("rol"):
        raise APIError(401, "SESION_REVOCADA", "Los permisos cambiaron. Inicie sesión de nuevo.")
    return {**payload, **perfil.model_dump(mode="json", exclude={"id"}), "sub": str(usuario.id)}


def require_role(allowed_roles: List[str]) -> Callable:
    """Fábrica de dependencias para verificar que el rol del usuario coincida con los roles autorizados."""

    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "NO_AUTENTICADO",
                    "mensaje": "Se requiere cabecera 'Authorization: Bearer <token>'.",
                },
            )

        user_role = current_user.get("rol")
        if user_role not in allowed_roles or user_role not in set(RolUsuario):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "ACCESO_DENEGADO",
                    "mensaje": f"El rol '{user_role}' no tiene permisos para esta operación.",
                    "roles_requeridos": allowed_roles,
                },
            )
        return current_user

    return role_checker
