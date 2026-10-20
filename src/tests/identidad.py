"""Repositorio de identidad aislado para pruebas unitarias; nunca usado por la app."""

from copy import deepcopy
from datetime import UTC, datetime

from src.core.security import hash_password
from src.modules.usuarios.demo import DEMO_CUENTAS, id_demo
from src.modules.usuarios.models import Usuario
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, vinculo_piloto
from src.modules.usuarios.schemas import UsuarioDTO

HASHES = {c["email"]: hash_password(c["password"]) for c in DEMO_CUENTAS}


class RepositorioIdentidadDemo:
    def __init__(self):
        self.usuarios = {}
        self.perfiles = {}
        for index, cuenta in enumerate(DEMO_CUENTAS):
            usuario = Usuario(
                id=id_demo(cuenta["email"]),
                email=cuenta["email"],
                nombre=cuenta["nombre"],
                apellido=cuenta["apellido"],
                documento_identidad=f"DEMO{index:06d}",
                password_hash=HASHES[cuenta["email"]],
                esta_activo=True,
                es_superadmin=cuenta["rol"] == "SUPERADMIN",
                auth_revision=1,
                creado_en=datetime.now(UTC),
            )
            self.usuarios[usuario.id] = usuario
            self.perfiles[usuario.email] = {
                "id": str(usuario.id),
                "email": usuario.email,
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "rol": cuenta["rol"],
                "condominio_id": None if usuario.es_superadmin else str(CONDOMINIO_PILOTO_ID),
                "departamentos": [vinculo_piloto(cuenta["unidad"], cuenta["relacion"])]
                if cuenta.get("unidad")
                else [],
            }

    async def por_email(self, email):
        return next((u for u in self.usuarios.values() if u.email == email.strip().lower()), None)

    async def por_id(self, uid, **_kwargs):
        return self.usuarios.get(uid)

    async def contextos(self, uid):
        perfil = self.perfiles[self.usuarios[uid].email]
        return (
            [{"id": perfil["condominio_id"], "nombre": "Villa Bonita 3", "rol": perfil["rol"]}]
            if perfil["condominio_id"]
            else []
        )

    async def perfil(self, usuario, _cid=None):
        return UsuarioDTO.model_validate(deepcopy(self.perfiles[usuario.email]))
