"""Datos de demostración explícitos; no se utilizan para autenticar en memoria."""

from uuid import uuid5

from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID

DEMO_CUENTAS = [
    {
        "email": "admin@villabonita3.pe",
        "password": "Admin123!",
        "nombre": "Carlos",
        "apellido": "Mendoza",
        "rol": "ADMIN_JUNTA",
    },
    {
        "email": "auditor@villabonita3.pe",
        "password": "Auditor123!",
        "nombre": "Jorge",
        "apellido": "Revisor Fiscal",
        "rol": "AUDITOR",
    },
    {
        "email": "residente102@villabonita3.pe",
        "password": "Residente123!",
        "nombre": "Ana",
        "apellido": "Gómez (Solvente)",
        "rol": "RESIDENTE",
        "unidad": "102",
        "relacion": "PROPIETARIO_TITULAR",
    },
    {
        "email": "moroso402@villabonita3.pe",
        "password": "Moroso123!",
        "nombre": "Pedro",
        "apellido": "Morales (En Mora)",
        "rol": "RESIDENTE",
        "unidad": "402",
        "relacion": "PROPIETARIO_TITULAR",
    },
    {
        "email": "inquilino504@villabonita3.pe",
        "password": "Inquilino123!",
        "nombre": "Lucía",
        "apellido": "Fernández",
        "rol": "RESIDENTE",
        "unidad": "504",
        "relacion": "INQUILINO",
    },
    {
        "email": "superadmin@condomanager.pe",
        "password": "SuperAdmin123!",
        "nombre": "Gestor",
        "apellido": "Plataforma",
        "rol": "SUPERADMIN",
    },
]


def id_demo(email: str):
    return uuid5(CONDOMINIO_PILOTO_ID, "usuario:" + email)
