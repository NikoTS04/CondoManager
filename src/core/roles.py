"""Catálogos de autorización y tenencia definidos por condomanager_schema.sql."""

from enum import StrEnum


class RolUsuario(StrEnum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN_JUNTA = "ADMIN_JUNTA"
    AUDITOR = "AUDITOR"
    RESIDENTE = "RESIDENTE"


class TipoRelacion(StrEnum):
    PROPIETARIO_TITULAR = "PROPIETARIO_TITULAR"
    COPROPIETARIO = "COPROPIETARIO"
    INQUILINO = "INQUILINO"


ROLES_ADMINISTRATIVOS = {RolUsuario.SUPERADMIN, RolUsuario.ADMIN_JUNTA}
VERSION_SESION = 2
