"""Servicio de Usuarios, Autenticación y Catálogo Piloto (PROC-05)."""

from typing import Dict, List, Optional
import uuid
from src.core.config import settings
from src.core.security import create_access_token, hash_password, verify_password
from src.modules.usuarios.schemas import LoginRequest, TokenResponse, UsuarioDTO


class CredencialesInvalidasException(Exception):
    """Excepción al fallar la autenticación de usuario."""
    pass


class UsuariosService:
    """Gestiona el catálogo de usuarios, autenticación y emisión de tokens RBAC."""

    try:
        CONDOMINIO_PILOTO_ID: str | None = str(uuid.UUID(settings.CONDOMINIO_PILOTO_ID))
    except (TypeError, ValueError, AttributeError):
        CONDOMINIO_PILOTO_ID = None

    # Directorio de Usuarios Semilla para el Piloto Villa Bonita 3
    USUARIOS_PILOTO: Dict[str, Dict] = {
        "admin@villabonita3.pe": {
            "id": "usr-admin-01",
            "email": "admin@villabonita3.pe",
            "password_hash": hash_password("Admin123!"),
            "nombre": "Carlos",
            "apellido": "Mendoza",
            "rol": "ADMIN_JUNTA",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": [],
            "tipo_relacion": "ADMINISTRADOR",
        },
        "auditor@villabonita3.pe": {
            "id": "usr-audit-01",
            "email": "auditor@villabonita3.pe",
            "password_hash": hash_password("Auditor123!"),
            "nombre": "Jorge",
            "apellido": "Revisor Fiscal",
            "rol": "AUDITOR",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": [],
            "tipo_relacion": "AUDITOR",
        },
        "residente102@villabonita3.pe": {
            "id": "usr-res-102",
            "email": "residente102@villabonita3.pe",
            "password_hash": hash_password("Residente123!"),
            "nombre": "Ana",
            "apellido": "Gómez (Solvente)",
            "rol": "PROPIETARIO",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": ["102"],
            "tipo_relacion": "PROPIETARIO_TITULAR",
        },
        "moroso402@villabonita3.pe": {
            "id": "usr-res-402",
            "email": "moroso402@villabonita3.pe",
            "password_hash": hash_password("Moroso123!"),
            "nombre": "Pedro",
            "apellido": "Morales (En Mora)",
            "rol": "PROPIETARIO",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": ["402"],
            "tipo_relacion": "PROPIETARIO_TITULAR",
        },
        "inquilino504@villabonita3.pe": {
            "id": "usr-inq-504",
            "email": "inquilino504@villabonita3.pe",
            "password_hash": hash_password("Inquilino123!"),
            "nombre": "Lucía",
            "apellido": "Fernández",
            "rol": "INQUILINO",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": ["504"],
            "tipo_relacion": "INQUILINO",
        },
        "superadmin@condomanager.pe": {
            "id": "usr-super-01",
            "email": "superadmin@condomanager.pe",
            "password_hash": hash_password("SuperAdmin123!"),
            "nombre": "Gestor",
            "apellido": "Plataforma",
            "rol": "SUPERADMIN",
            "condominio_id": None,
            "departamentos": [],
            "tipo_relacion": "SUPERADMIN",
        },
    }

    @classmethod
    def autenticar(cls, request: LoginRequest) -> TokenResponse:
        """Verifica credenciales, genera el access token JWT y retorna la respuesta."""
        email_clean = request.email.strip().lower()
        usuario_data = cls.USUARIOS_PILOTO.get(email_clean)

        if not usuario_data or not verify_password(request.password, usuario_data["password_hash"]):
            raise CredencialesInvalidasException("Correo electrónico o contraseña incorrectos.")

        # Claims para el JWT
        token_claims = {
            "sub": usuario_data["id"],
            "email": usuario_data["email"],
            "rol": usuario_data["rol"],
            "condominio_id": usuario_data["condominio_id"],
            "departamentos": usuario_data["departamentos"],
            "tipo_relacion": usuario_data["tipo_relacion"],
            "nombre": f"{usuario_data['nombre']} {usuario_data['apellido']}",
        }

        access_token = create_access_token(data=token_claims)

        dto = UsuarioDTO(
            id=usuario_data["id"],
            email=usuario_data["email"],
            nombre=usuario_data["nombre"],
            apellido=usuario_data["apellido"],
            rol=usuario_data["rol"],
            condominio_id=usuario_data["condominio_id"],
            departamentos=usuario_data["departamentos"],
            tipo_relacion=usuario_data["tipo_relacion"],
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,
            usuario=dto,
        )

    @classmethod
    def obtener_por_email(cls, email: str) -> Optional[UsuarioDTO]:
        """Busca un usuario por correo electrónico."""
        usuario_data = cls.USUARIOS_PILOTO.get(email.strip().lower())
        if not usuario_data:
            return None
        return UsuarioDTO(
            id=usuario_data["id"],
            email=usuario_data["email"],
            nombre=usuario_data["nombre"],
            apellido=usuario_data["apellido"],
            rol=usuario_data["rol"],
            condominio_id=usuario_data["condominio_id"],
            departamentos=usuario_data["departamentos"],
            tipo_relacion=usuario_data["tipo_relacion"],
        )

    @classmethod
    def listar_usuarios_demo(cls) -> List[UsuarioDTO]:
        """Retorna el catálogo público de perfiles demo para pruebas rápidas."""
        return [
            UsuarioDTO(
                id=u["id"],
                email=u["email"],
                nombre=u["nombre"],
                apellido=u["apellido"],
                rol=u["rol"],
                condominio_id=u["condominio_id"],
                departamentos=u["departamentos"],
                tipo_relacion=u["tipo_relacion"],
            )
            for u in cls.USUARIOS_PILOTO.values()
        ]
