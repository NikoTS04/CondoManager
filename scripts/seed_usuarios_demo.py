"""Provisionar datos demo persistentes: python -m scripts.seed_usuarios_demo."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid5

from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.security import hash_password
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.usuarios.demo import DEMO_CUENTAS, id_demo
from src.modules.usuarios.models import Usuario, UsuarioDepartamento, UsuarioRol
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID, DEPARTAMENTOS_PILOTO


async def cargar_demo(session):
    """Reejecución conservadora: no altera cuentas, contraseñas ni estados existentes."""
    cid = CONDOMINIO_PILOTO_ID
    if await session.get(Condominio, cid) is None:
        session.add(
            Condominio(
                id=cid,
                nombre="Villa Bonita 3",
                direccion="Condominio de demostración",
                moneda="PEN",
                regla_mora_tipo="MONTO_FIJO",
                monto_mora_fijo=0,
                dia_vencimiento=20,
                dias_gracia=2,
                activo=True,
            )
        )
        await session.flush()
    await session.execute(select(Condominio).where(Condominio.id == cid).with_for_update())
    edificio_id = uuid5(cid, "edificio:piloto")
    if await session.get(Edificio, edificio_id) is None:
        session.add(
            Edificio(
                id=edificio_id, condominio_id=cid, nombre_bloque="Torre piloto", total_pisos=14
            )
        )
        await session.flush()
    for datos in DEPARTAMENTOS_PILOTO.values():
        if await session.get(Departamento, datos["id"]) is None:
            session.add(
                Departamento(
                    id=datos["id"],
                    edificio_id=edificio_id,
                    numero=datos["numero"],
                    piso=datos["piso"],
                    coeficiente_participacion=datos["coeficiente"],
                    saldo_a_favor=datos["saldo_a_favor"],
                    estado_financiero=datos["estado_financiero"],
                    activo=True,
                )
            )
    await session.flush()
    creadas = 0
    for index, datos in enumerate(DEMO_CUENTAS, 1):
        existente = await session.scalar(select(Usuario).where(Usuario.email == datos["email"]))
        if existente is not None:
            if existente.id != id_demo(datos["email"]):
                raise RuntimeError(
                    "Un correo demo ya pertenece a otra identidad; no se modificó esa cuenta."
                )
            continue
        usuario = Usuario(
            id=id_demo(datos["email"]),
            email=datos["email"],
            nombre=datos["nombre"],
            apellido=datos["apellido"],
            documento_identidad=f"DEMO{index:06d}",
            password_hash=hash_password(datos["password"]),
            esta_activo=True,
            es_superadmin=datos["rol"] == "SUPERADMIN",
            auth_revision=1,
            creado_en=datetime.now(UTC),
        )
        session.add(usuario)
        await session.flush()
        if datos["rol"] != "SUPERADMIN":
            session.add(UsuarioRol(usuario_id=usuario.id, condominio_id=cid, rol=datos["rol"]))
        if datos.get("unidad"):
            session.add(
                UsuarioDepartamento(
                    usuario_id=usuario.id,
                    departamento_id=uuid5(cid, datos["unidad"]),
                    tipo_relacion=datos["relacion"],
                    es_activo=True,
                )
            )
        creadas += 1
    await session.flush()
    return creadas


async def main():
    async with AsyncSessionLocal() as session, session.begin():
        creadas = await cargar_demo(session)
    print(f"Datos demo persistidos. Cuentas nuevas: {creadas}; cuentas existentes conservadas.")


if __name__ == "__main__":
    asyncio.run(main())
