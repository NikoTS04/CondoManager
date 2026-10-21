"""Bootstrap explícito: python -m scripts.crear_superadmin (contraseña por getpass)."""

import asyncio
from getpass import getpass

from src.core.database import AsyncSessionLocal
from src.core.security import hash_password
from src.modules.usuarios.models import Usuario
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository
from src.modules.usuarios.schemas import CrearUsuarioRequest


async def provisionar(request):
    async with AsyncSessionLocal() as session, session.begin():
        repo = SQLAlchemyUsuariosRepository(session)
        if await repo.duplicado(request.email, request.documento_identidad):
            raise ValueError(
                "La identidad ya existe; no se modifica su estado ni su concesión global."
            )
        usuario = Usuario(
            **request.model_dump(exclude={"password"}),
            password_hash=hash_password(request.password.get_secret_value()),
            esta_activo=True,
            es_superadmin=True,
            auth_revision=1,
        )
        await repo.agregar(usuario)
        return usuario.id


def main():
    request = CrearUsuarioRequest(
        email=input("Correo: "),
        nombre=input("Nombre: "),
        apellido=input("Apellido: "),
        documento_identidad=input("Documento: "),
        password=getpass("Contraseña inicial: "),
    )
    uid = asyncio.run(provisionar(request))
    print(f"SuperAdmin global provisionado: {uid}")


if __name__ == "__main__":
    main()
