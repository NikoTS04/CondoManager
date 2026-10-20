"""Servicio de Usuarios, Autenticación y Catálogo Piloto (PROC-05)."""

from typing import Dict, List, Optional

from src.core.security import create_access_token, hash_password, verify_password
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, vinculo_piloto
from src.modules.usuarios.schemas import LoginRequest, TokenResponse, UsuarioDTO


class CredencialesInvalidasException(Exception):
    """Excepción al fallar la autenticación de usuario."""
    pass


class UsuariosService:
    """Gestiona el catálogo de usuarios, autenticación y emisión de tokens RBAC."""

    CONDOMINIO_PILOTO_ID = str(CONDOMINIO_PILOTO_ID)

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
        },
        "residente102@villabonita3.pe": {
            "id": "usr-res-102",
            "email": "residente102@villabonita3.pe",
            "password_hash": hash_password("Residente123!"),
            "nombre": "Ana",
            "apellido": "Gómez (Solvente)",
            "rol": "RESIDENTE",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": [vinculo_piloto("102", "PROPIETARIO_TITULAR")],
        },
        "moroso402@villabonita3.pe": {
            "id": "usr-res-402",
            "email": "moroso402@villabonita3.pe",
            "password_hash": hash_password("Moroso123!"),
            "nombre": "Pedro",
            "apellido": "Morales (En Mora)",
            "rol": "RESIDENTE",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": [vinculo_piloto("402", "PROPIETARIO_TITULAR")],
        },
        "inquilino504@villabonita3.pe": {
            "id": "usr-inq-504",
            "email": "inquilino504@villabonita3.pe",
            "password_hash": hash_password("Inquilino123!"),
            "nombre": "Lucía",
            "apellido": "Fernández",
            "rol": "RESIDENTE",
            "condominio_id": CONDOMINIO_PILOTO_ID,
            "departamentos": [vinculo_piloto("504", "INQUILINO")],
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
        },
    }

    @classmethod
    def autenticar(cls, request: LoginRequest) -> TokenResponse:
        """Verifica credenciales, genera el access token JWT y retorna la respuesta."""
        email_clean = request.email.strip().lower()
        usuario_data = cls.USUARIOS_PILOTO.get(email_clean)

        if not usuario_data or not verify_password(request.password, usuario_data["password_hash"]):
            raise CredencialesInvalidasException("Correo electrónico o contraseña incorrectos.")

        dto = UsuarioDTO.model_validate(usuario_data)
        # El perfil público y el JWT comparten exactamente los mismos vínculos.
        token_claims = {
            **dto.model_dump(mode="json", exclude={"id"}),
            "sub": dto.id,
        }

        access_token = create_access_token(data=token_claims)

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
        return UsuarioDTO.model_validate(usuario_data)

    @classmethod
    def listar_usuarios_demo(cls) -> List[UsuarioDTO]:
        """Retorna el catálogo público de perfiles demo para pruebas rápidas."""
        return [
            UsuarioDTO.model_validate(u)
            for u in cls.USUARIOS_PILOTO.values()
        ]
