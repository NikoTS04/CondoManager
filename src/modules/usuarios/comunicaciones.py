"""Productores de identidad sobre la cola SQL; secretos solo para el worker."""

from urllib.parse import urlsplit
from uuid import UUID, uuid4, uuid5

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import settings
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.notificaciones.models import Notificacion
from src.modules.usuarios.invitaciones_models import InvitacionUsuario
from src.modules.usuarios.models import Usuario


def cifrador():
    try:
        return Fernet(settings.IDENTITY_DELIVERY_KEY.encode("ascii"))
    except (ValueError, UnicodeError):
        raise APIError(
            503, "IDENTIDAD_NO_CONFIGURADA", "Configure la clave de entrega de identidad."
        ) from None


def aviso_invitacion(invitacion, usuario, token):
    url = urlsplit(settings.ACTIVACION_WEB_URL)
    if url.scheme not in {"http", "https"} or not url.netloc or url.query or url.fragment:
        raise APIError(503, "IDENTIDAD_NO_CONFIGURADA", "Configure la URL de activación.")
    enlace = f"{settings.ACTIVACION_WEB_URL}#token={token}"
    cuerpo = (
        f"Hola {usuario.nombre},\n\nActiva tu cuenta de CondoManager y elige tu contraseña:\n"
        f"{enlace}\n\nEl enlace vence el {invitacion.expira_en.isoformat()} y solo puede usarse una vez."
    )
    return Notificacion(
        id=uuid4(),
        condominio_id=invitacion.condominio_id,
        departamento_id=None,
        usuario_destinatario_id=usuario.id,
        evento_id=invitacion.id,
        operacion_id=invitacion.id,
        tipo_evento="UsuarioInvitadoEvent",
        finalidad="INVITACION",
        canal="EMAIL",
        destinatario=usuario.email,
        asunto="Activa tu cuenta de CondoManager",
        cuerpo="Invitación de acceso. Enlace privado omitido del historial.",
        contenido_cifrado=cifrador().encrypt(cuerpo.encode()).decode(),
        estado="EN_COLA",
        transporte="PROVEEDOR",
        ciclo=1,
        intentos=0,
    )


def aviso_cambio(cid, usuario, auditoria, departamento_id=None):
    return Notificacion(
        id=uuid4(),
        condominio_id=cid,
        departamento_id=departamento_id,
        usuario_destinatario_id=usuario.id,
        evento_id=auditoria.id,
        operacion_id=auditoria.id,
        tipo_evento="AccesoUsuarioCambiadoEvent",
        finalidad="SEGURIDAD",
        canal="EMAIL",
        destinatario=usuario.email,
        asunto="Cambio de acceso en CondoManager",
        cuerpo=(
            f"Hola {usuario.nombre},\n\nLa administración registró un cambio de acceso "
            f"({auditoria.accion_ejecutada}) en el condominio {cid}. "
            "Tus sesiones anteriores ya no son válidas. Si conservas acceso, inicia sesión de nuevo. "
            "Consulta a la administración si no reconoces este cambio."
        ),
        estado="EN_COLA",
        transporte="PROVEEDOR",
        ciclo=1,
        intentos=0,
    )


TIPO_CUENTA_ACTIVADA = "CuentaActivadaEvent"
_NAMESPACE_ACTIVACION = UUID("5b0f6a52-3f0e-4d52-9a67-8f1f4c6d0c78")


def _enlace_login():
    """Deriva `/login` de la URL de activación; sin URL válida no se incluye enlace."""
    url = urlsplit(settings.ACTIVACION_WEB_URL)
    if url.scheme not in {"http", "https"} or not url.netloc or url.query or url.fragment:
        return None
    base = url.path.rstrip("/").rsplit("/", 1)[0]
    return f"{url.scheme}://{url.netloc}{base}/login"


def aviso_activacion(invitacion, usuario, condominio):
    """Aviso de «cuenta activada»; nunca contiene token ni contraseña.

    Los identificadores se derivan de la invitación (un solo uso), de modo que
    `uq_notificacion_logica` impide un segundo aviso aunque se reintente la activación.
    El evento difiere del id de la invitación para no chocar con el aviso de invitación.
    """
    enlace = _enlace_login()
    partes = [
        f"Hola {usuario.nombre},",
        f"Tu cuenta de CondoManager en {condominio.nombre} ya está activa.",
    ]
    if enlace:
        partes.append(f"Puedes iniciar sesión aquí: {enlace}")
    partes.append(
        "Si no fuiste tú quien activó esta cuenta, contacta a la administración del condominio."
    )
    return Notificacion(
        id=uuid4(),
        condominio_id=invitacion.condominio_id,
        departamento_id=None,
        usuario_destinatario_id=usuario.id,
        evento_id=uuid5(_NAMESPACE_ACTIVACION, f"{TIPO_CUENTA_ACTIVADA}:{invitacion.id}"),
        operacion_id=invitacion.id,
        tipo_evento=TIPO_CUENTA_ACTIVADA,
        finalidad="SEGURIDAD",
        canal="EMAIL",
        destinatario=usuario.email,
        asunto="Tu cuenta de CondoManager está activa",
        cuerpo="\n\n".join(partes),
        estado="EN_COLA",
        transporte="PROVEEDOR",
        ciclo=1,
        intentos=0,
    )


async def destinatario_identidad_valido(db, log, ahora):
    """No confundir el aviso de seguridad con nuevas comunicaciones de la unidad."""
    usuario = await db.get(Usuario, log.usuario_destinatario_id)
    if usuario is None or usuario.email != log.destinatario or log.canal != "EMAIL":
        return False
    if log.finalidad == "INVITACION":
        from src.modules.condominios.models import Condominio
        from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

        invitacion = await db.get(InvitacionUsuario, log.operacion_id)
        contexto = await db.get(Condominio, log.condominio_id)
        rol = await SQLAlchemyUsuariosRepository(db).rol_usuario(usuario.id, log.condominio_id)
        return bool(
            invitacion
            and invitacion.usuario_id == usuario.id
            and invitacion.condominio_id == log.condominio_id
            and not invitacion.utilizada_en
            and not invitacion.revocada_en
            and invitacion.expira_en > ahora
            and usuario.activacion_pendiente
            and not usuario.esta_activo
            and usuario.auth_revision == invitacion.revision_cuenta
            and contexto
            and contexto.activo
            and rol
            and rol.es_activo
        )
    if log.finalidad == "SEGURIDAD" and log.tipo_evento == TIPO_CUENTA_ACTIVADA:
        # La operación es la invitación consumida: el aviso solo sale mientras la cuenta
        # siga activa y con acceso vigente en el contexto.
        from src.modules.condominios.models import Condominio
        from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository

        invitacion = await db.get(InvitacionUsuario, log.operacion_id)
        contexto = await db.get(Condominio, log.condominio_id)
        rol = await SQLAlchemyUsuariosRepository(db).rol_usuario(usuario.id, log.condominio_id)
        return bool(
            invitacion
            and invitacion.usuario_id == usuario.id
            and invitacion.condominio_id == log.condominio_id
            and invitacion.utilizada_en
            and not invitacion.revocada_en
            and usuario.esta_activo
            and not usuario.activacion_pendiente
            and contexto
            and contexto.activo
            and rol
            and rol.es_activo
        )
    if log.finalidad == "SEGURIDAD":
        auditoria = await db.get(AuditoriaLogORM, log.operacion_id)
        return bool(
            auditoria
            and auditoria.condominio_id == log.condominio_id
            and str(usuario.id)
            == str(
                auditoria.estado_posterior.get("usuario_id") or auditoria.estado_posterior.get("id")
            )
        )
    return False


def contenido_entrega(log):
    if log.finalidad != "INVITACION":
        return log.cuerpo
    try:
        return cifrador().decrypt(log.contenido_cifrado.encode()).decode()
    except (InvalidToken, AttributeError, UnicodeError):
        raise APIError(
            503, "IDENTIDAD_NO_CONFIGURADA", "No se pudo abrir el material de entrega."
        ) from None
