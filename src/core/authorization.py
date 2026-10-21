"""Autorización contextual común a los recursos piloto de residentes y Junta."""

from uuid import UUID

from fastapi import HTTPException

from src.core.roles import ROLES_ADMINISTRATIVOS, RolUsuario


def denegar(mensaje="No tiene permisos sobre el recurso solicitado."):
    raise HTTPException(403, detail={"error_code": "ACCESO_DENEGADO", "mensaje": mensaje})


def autorizar_condominio(usuario: dict, condominio_id, *, escritura=False):
    rol = usuario.get("rol")
    if rol not in set(RolUsuario) or (escritura and rol not in ROLES_ADMINISTRATIVOS):
        denegar()
    try:
        cid = UUID(str(condominio_id))
        if rol != RolUsuario.SUPERADMIN and UUID(str(usuario.get("condominio_id"))) != cid:
            denegar("El condominio no pertenece a su contexto autorizado.")
    except (ValueError, TypeError, AttributeError):
        denegar("El contexto de condominio es inválido.")
    return cid


def contexto_consulta(usuario: dict, condominio_id=None):
    cid = condominio_id or usuario.get("condominio_id")
    if not cid:
        raise HTTPException(
            422,
            detail={"error_code": "CONTEXTO_REQUERIDO", "mensaje": "Seleccione un condominio."},
        )
    return autorizar_condominio(usuario, cid)


def vinculos_activos(usuario: dict) -> set[str]:
    return {
        str(v["departamento_id"])
        for v in usuario.get("departamentos", [])
        if isinstance(v, dict) and v.get("es_activo") is True
    }


def puede_ver_departamento(usuario: dict, departamento_id) -> bool:
    return usuario.get("rol") != RolUsuario.RESIDENTE or str(departamento_id) in vinculos_activos(
        usuario
    )


def autorizar_departamento(usuario: dict, departamento_id, condominio_id, *, escritura=False):
    autorizar_condominio(usuario, condominio_id)
    if escritura and usuario.get("rol") == RolUsuario.AUDITOR:
        denegar("El auditor tiene permisos de solo lectura.")
    if not puede_ver_departamento(usuario, departamento_id):
        denegar("El departamento no pertenece a sus vínculos activos.")
