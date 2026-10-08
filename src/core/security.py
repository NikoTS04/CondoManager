"""Módulo de Seguridad, Criptografía y Control de Acceso RBAC (PROC-05)."""

from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Any, Callable, Dict, List, Optional
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

SECRET_KEY = os.getenv("SECRET_KEY", "condomanager_secret_key_sdd_pilot_2026_super_secure")
ALGORITHM = "HS256"
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
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except getattr(jwt, "ExpiredSignatureError", Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_EXPIRADO", "mensaje": "La sesión ha expirado. Vuelva a iniciar sesión."},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALIDO", "mensaje": "Token de autenticación inválido o corrupto."},
        )


# ============================================================================
# Dependencias de Inyección FastAPI para RBAC
# ============================================================================

async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[Dict[str, Any]]:
    """Obtiene el contexto del usuario si se proporciona un Bearer token válido, o None."""
    if not auth or not auth.credentials:
        return None
    return decode_access_token(auth.credentials)


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """Exige un Bearer token válido y retorna el payload del usuario autenticado."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "NO_AUTENTICADO", "mensaje": "Se requiere cabecera 'Authorization: Bearer <token>'."},
        )
    return decode_access_token(auth.credentials)


def require_role(allowed_roles: List[str]) -> Callable:
    """Fábrica de dependencias para verificar que el rol del usuario coincida con los roles autorizados."""
    async def role_checker(
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    ) -> Optional[Dict[str, Any]]:
        # Si se proporciona token, validar rol de forma estricta
        if current_user:
            user_role = current_user.get("rol")
            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "ACCESO_DENEGADO",
                        "mensaje": f"Acceso restringido. Su rol actual ('{user_role}') no tiene privilegios suficientes.",
                        "roles_requeridos": allowed_roles,
                    },
                )
            return current_user

        # Si no hay token y el modo estricto está habilitado
        if os.getenv("AUTH_STRICT_ENFORCEMENT", "false").lower() == "true":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "NO_AUTENTICADO", "mensaje": "Se requiere cabecera 'Authorization: Bearer <token>'."},
            )

        return None

    return role_checker

