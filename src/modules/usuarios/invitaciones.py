"""Invitación, activación de un uso y relevo transaccional (CON-76/7)."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.config import settings
from src.core.errors import APIError
from src.core.security import hash_password
from src.modules.notificaciones.models import Notificacion
from src.modules.usuarios.comunicaciones import aviso_invitacion
from src.modules.usuarios.invitaciones_models import InvitacionUsuario, OperacionIdentidad
from src.modules.usuarios.models import Usuario, UsuarioRol
from src.modules.usuarios.schemas import InvitacionResponse, RelevoResponse
from src.modules.usuarios.service import UsuariosService


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class IdentidadService(UsuariosService):
    def __init__(self, repository):
        super().__init__(repository)
        self.db = repository.session

    async def _repetida(self, cid, clave, actor, accion, datos):
        huella = hash_token(json.dumps([actor["sub"], accion, datos], sort_keys=True))
        operacion = await self.db.get(OperacionIdentidad, (cid, clave))
        if operacion:
            if operacion.huella != huella:
                raise APIError(
                    409, "IDEMPOTENCIA_CONFLICTO", "La clave ya identifica otra solicitud."
                )
            return huella, operacion.respuesta
        return huella, None

    async def _guardar(self, cid, clave, huella, respuesta):
        await self.repo.agregar(
            OperacionIdentidad(
                condominio_id=cid,
                clave=clave,
                huella=huella,
                respuesta=respuesta,
            )
        )
        await self.repo.confirmar()
        return respuesta

    async def _dto(self, invitacion):
        usuario = await self.repo.por_id(invitacion.usuario_id)
        log = await self.db.scalar(
            select(Notificacion).where(
                Notificacion.operacion_id == invitacion.id,
                Notificacion.finalidad == "INVITACION",
            )
        )
        estado = "PENDIENTE"
        if invitacion.utilizada_en:
            estado = "UTILIZADA"
        elif invitacion.revocada_en:
            estado = "REVOCADA"
        elif invitacion.expira_en <= datetime.now(UTC):
            estado = "EXPIRADA"
        return InvitacionResponse(
            id=invitacion.id,
            usuario_id=usuario.id,
            email=usuario.email,
            estado=estado,
            expira_en=invitacion.expira_en,
            creado_en=invitacion.creado_en,
            notificacion_id=log.id,
            estado_correo=log.estado,
        ).model_dump(mode="json")

    async def _emitir(self, cid, usuario, actor):
        ahora = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        invitacion = InvitacionUsuario(
            id=uuid4(),
            usuario_id=usuario.id,
            condominio_id=cid,
            creador_id=UUID(actor["sub"]),
            token_hash=hash_token(token),
            revision_cuenta=usuario.auth_revision,
            creado_en=ahora,
            expira_en=ahora + timedelta(hours=settings.INVITACION_EXPIRE_HOURS),
        )
        aviso = aviso_invitacion(invitacion, usuario, token)
        await self.repo.agregar(invitacion, aviso)
        await self._auditar(
            cid,
            actor,
            usuario,
            "USUARIO_INVITADO",
            {},
            posterior={
                "invitacion_id": str(invitacion.id),
                "usuario_id": str(usuario.id),
                "expira_en": invitacion.expira_en.isoformat(),
            },
        )
        return invitacion

    async def invitar(self, cid, request, actor, clave):
        await self._autorizar(cid, actor, bloquear=True)
        huella, previa = await self._repetida(
            cid, clave, actor, "INVITAR", request.model_dump(mode="json")
        )
        if previa:
            return previa
        if await self.repo.duplicado(request.email, request.documento_identidad):
            raise APIError(409, "USUARIO_DUPLICADO", "El correo o documento ya está registrado.")
        usuario = Usuario(
            id=uuid4(),
            **request.model_dump(),
            password_hash=hash_password(secrets.token_urlsafe(48)),
            esta_activo=False,
            activacion_pendiente=True,
            auth_revision=1,
            es_superadmin=False,
            creado_en=datetime.now(UTC),
        )
        try:
            await self.repo.agregar(usuario)
            await self.repo.agregar(
                UsuarioRol(usuario_id=usuario.id, condominio_id=cid, rol="RESIDENTE")
            )
            invitacion = await self._emitir(cid, usuario, actor)
            return await self._guardar(cid, clave, huella, await self._dto(invitacion))
        except IntegrityError as exc:
            nombre = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", "")
            if nombre in {
                "uq_usuario_email_normalizado",
                "uq_usuario_documento_normalizado",
                "usuarios_email_key",
            }:
                raise APIError(
                    409, "USUARIO_DUPLICADO", "El correo o documento ya está registrado."
                ) from exc
            raise

    async def listar_invitaciones(self, cid, actor, limit=50, offset=0):
        await self._autorizar(cid, actor)
        invitaciones = await self.db.scalars(
            select(InvitacionUsuario)
            .where(
                InvitacionUsuario.condominio_id == cid,
            )
            .order_by(InvitacionUsuario.creado_en.desc(), InvitacionUsuario.id)
            .limit(limit)
            .offset(offset)
        )
        return [await self._dto(i) for i in invitaciones]

    async def _bloquear_invitacion(self, cid, iid, actor=None):
        # Orden compartido con cambios de cuenta/rol: usuario, contextos, invitación.
        invitacion = await self.db.get(InvitacionUsuario, iid)
        if not invitacion or invitacion.condominio_id != cid:
            raise APIError(
                404, "INVITACION_NO_ENCONTRADA", "No existe la invitación en este contexto."
            )
        usuario = await self.repo.por_id(invitacion.usuario_id, bloquear=True)
        contextos = set(await self.repo.condominios_usuario(usuario.id)) | {cid}
        await self.repo.bloquear_contextos(list(contextos))
        if actor:
            await self._autorizar(cid, actor)
        invitacion = await self.db.scalar(
            select(InvitacionUsuario)
            .where(
                InvitacionUsuario.id == iid,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return invitacion, usuario

    async def modificar_invitacion(self, cid, iid, actor, clave, reenviar=False):
        await self._autorizar(cid, actor)
        invitacion, usuario = await self._bloquear_invitacion(cid, iid, actor)
        huella, previa = await self._repetida(
            cid, clave, actor, "REENVIAR" if reenviar else "REVOCAR", {"id": str(iid)}
        )
        if previa:
            return previa
        if invitacion.utilizada_en or not usuario.activacion_pendiente:
            raise APIError(409, "INVITACION_UTILIZADA", "La cuenta ya completó su activación.")
        ultima = await self.db.scalar(
            select(InvitacionUsuario.id)
            .where(
                InvitacionUsuario.usuario_id == usuario.id,
            )
            .order_by(InvitacionUsuario.creado_en.desc(), InvitacionUsuario.id)
            .limit(1)
        )
        if reenviar and ultima != invitacion.id:
            raise APIError(
                409, "INVITACION_REVOCADA", "Seleccione la invitación más reciente para reenviar."
            )
        if not invitacion.revocada_en:
            invitacion.revocada_en = datetime.now(UTC)
            await self.repo.agregar(invitacion)
            await self._auditar(
                cid,
                actor,
                usuario,
                "INVITACION_REVOCADA",
                {},
                posterior={"invitacion_id": str(iid)},
            )
        if reenviar:
            rol = await self.repo.rol_usuario(usuario.id, cid)
            if not rol or not rol.es_activo or usuario.esta_activo:
                raise APIError(
                    409, "ACTIVACION_NO_AUTORIZADA", "La cuenta no admite una invitación."
                )
            invitacion = await self._emitir(cid, usuario, actor)
        return await self._guardar(cid, clave, huella, await self._dto(invitacion))

    async def activar(self, request):
        invitacion = await self.db.scalar(
            select(InvitacionUsuario).where(
                InvitacionUsuario.token_hash == hash_token(request.token.get_secret_value()),
            )
        )
        if not invitacion:
            raise APIError(400, "ACTIVACION_INVALIDA", "El enlace de activación no es válido.")
        invitacion, usuario = await self._bloquear_invitacion(
            invitacion.condominio_id, invitacion.id
        )
        if invitacion.utilizada_en:
            raise APIError(409, "ACTIVACION_USADA", "El enlace ya se utilizó. Inicia sesión.")
        if invitacion.revocada_en:
            raise APIError(
                400, "ACTIVACION_REVOCADA", "El enlace fue revocado. Solicita una invitación nueva."
            )
        if invitacion.expira_en <= datetime.now(UTC):
            raise APIError(
                400,
                "ACTIVACION_EXPIRADA",
                "El enlace venció. Solicita el reenvío a la administración.",
            )
        contexto = await self.repo.contexto(invitacion.condominio_id)
        rol = await self.repo.rol_usuario(usuario.id, invitacion.condominio_id)
        if (
            not usuario.activacion_pendiente
            or usuario.esta_activo
            or usuario.auth_revision != invitacion.revision_cuenta
            or not contexto
            or not rol
            or not rol.es_activo
        ):
            raise APIError(
                400, "ACTIVACION_NO_AUTORIZADA", "La invitación ya no autoriza activar la cuenta."
            )
        usuario.password_hash = hash_password(request.password.get_secret_value())
        usuario.esta_activo = True
        usuario.activacion_pendiente = False
        usuario.auth_revision += 1
        invitacion.utilizada_en = datetime.now(UTC)
        await self.repo.agregar(usuario, invitacion)
        await self._auditar(
            invitacion.condominio_id,
            {"rol": "INVITACION", "sub": str(usuario.id)},
            usuario,
            "USUARIO_ACTIVADO",
            {},
        )
        await self.repo.confirmar()
        return {"estado": "ACTIVADO", "mensaje": "Cuenta activada. Ya puedes iniciar sesión."}

    async def relevar(self, cid, request, actor, clave):
        await self._autorizar(cid, actor)
        if request.saliente_id == request.entrante_id:
            raise APIError(422, "RELEVO_INVALIDO", "Selecciona usuarios distintos.")
        if request.tipo == "JUNTA" and actor["rol"] != "SUPERADMIN":
            raise APIError(403, "ACCESO_DENEGADO", "Solo SuperAdmin releva la Junta.")
        contextos = {cid}
        for uid in sorted((request.saliente_id, request.entrante_id)):
            await self._asignacion_para_vinculo(cid, uid)
            if await self.repo.por_id(uid, bloquear=True) is None:
                raise APIError(404, "USUARIO_NO_ENCONTRADO", "No existe un usuario del relevo.")
            contextos.update(await self.repo.condominios_usuario(uid))
        await self.repo.bloquear_contextos(list(contextos))
        await self._autorizar(cid, actor)
        huella, previa = await self._repetida(
            cid, clave, actor, "RELEVO", request.model_dump(mode="json")
        )
        if previa:
            return previa
        await self._asignacion_para_vinculo(cid, request.entrante_id, vigente=True)
        if request.tipo == "JUNTA":
            if "rol_saliente" not in request.model_fields_set:
                raise APIError(
                    422,
                    "RELEVO_INVALIDO",
                    "Indica el acceso final del saliente, incluido null para revocar.",
                )
            if request.departamento_id is not None:
                raise APIError(
                    422, "RELEVO_INVALIDO", "El relevo de Junta no cambia departamentos."
                )
            anterior = await self.repo.rol_usuario(request.saliente_id, cid)
            if not anterior.es_activo or anterior.rol != "ADMIN_JUNTA":
                raise APIError(409, "RELEVO_INVALIDO", "El saliente no es Junta vigente.")
            await self.gestionar_rol(
                cid, request.entrante_id, "ADMIN_JUNTA", actor, confirmar=False
            )
            await self.gestionar_rol(
                cid, request.saliente_id, request.rol_saliente, actor, confirmar=False
            )
        else:
            if request.departamento_id is None or request.rol_saliente is not None:
                raise APIError(
                    422,
                    "RELEVO_INVALIDO",
                    "Indica el departamento del inquilino, sin cambiar roles.",
                )
            row = await self.repo.departamento(cid, request.departamento_id, bloquear=True)
            anterior = await self.repo.vinculo(request.saliente_id, request.departamento_id)
            entrante = await self.repo.vinculo(request.entrante_id, request.departamento_id)
            if (
                not row
                or not anterior
                or not anterior.es_activo
                or anterior.tipo_relacion != "INQUILINO"
            ):
                raise APIError(
                    409, "RELEVO_INVALIDO", "El saliente no es inquilino activo de la unidad."
                )
            if entrante and entrante.es_activo and entrante.tipo_relacion != "INQUILINO":
                raise APIError(
                    409,
                    "RELEVO_INVALIDO",
                    "El entrante ya tiene otra relación activa con la unidad.",
                )
            await self.gestionar_vinculo(
                cid,
                request.entrante_id,
                request.departamento_id,
                "INQUILINO",
                actor,
                confirmar=False,
            )
            await self.gestionar_vinculo(
                cid, request.saliente_id, request.departamento_id, None, actor, confirmar=False
            )
        respuesta = RelevoResponse(
            operacion_id=clave,
            tipo=request.tipo,
            saliente_id=request.saliente_id,
            entrante_id=request.entrante_id,
        ).model_dump(mode="json")
        return await self._guardar(cid, clave, huella, respuesta)
