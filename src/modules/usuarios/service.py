"""Alta administrativa, estado global y autenticación persistente (CON-04)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from src.core.audit import AuditoriaPayload
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.security import create_access_token, hash_password, validar_sesion, verify_password
from src.modules.usuarios.models import Usuario, UsuarioRol
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository
from src.modules.usuarios.schemas import (
    AsignacionRolResponse,
    CrearUsuarioRequest,
    CuentaUsuarioResponse,
    LoginRequest,
    TokenResponse,
)


class CredencialesInvalidasException(APIError):
    def __init__(self):
        super().__init__(
            401, "CREDENCIALES_INVALIDAS", "Correo, contraseña o acceso no habilitado."
        )


class UsuariosService:
    def __init__(self, repository: SQLAlchemyUsuariosRepository):
        self.repo = repository

    async def autenticar(self, request: LoginRequest) -> TokenResponse:
        usuario = await self.repo.por_email(request.email)
        if usuario is None or not verify_password(
            request.password.get_secret_value(), usuario.password_hash
        ):
            raise CredencialesInvalidasException()
        if not usuario.esta_activo:
            raise CredencialesInvalidasException()
        cid = request.condominio_id
        if not usuario.es_superadmin:
            contextos = await self.repo.contextos(usuario.id)
            if not contextos:
                raise CredencialesInvalidasException()
            if cid is None and len(contextos) > 1:
                raise APIError(
                    409,
                    "CONTEXTO_REQUERIDO",
                    "Seleccione un condominio.",
                    {"condominios": [{"id": c["id"], "nombre": c["nombre"]} for c in contextos]},
                )
            cid = cid or UUID(contextos[0]["id"])
        perfil = await self.repo.perfil(usuario, cid)
        if perfil is None:
            raise APIError(403, "ACCESO_DENEGADO", "El condominio no está autorizado.")
        token = create_access_token(
            {
                **perfil.model_dump(mode="json", exclude={"id"}),
                "sub": str(usuario.id),
                "auth_revision": usuario.auth_revision,
            }
        )
        return TokenResponse(access_token=token, usuario=perfil)

    async def _autorizar(self, condominio_id, actor, *, bloquear=False):
        if actor["rol"] not in {"SUPERADMIN", "ADMIN_JUNTA"} or (
            actor["rol"] != "SUPERADMIN" and str(condominio_id) != actor.get("condominio_id")
        ):
            raise APIError(
                403, "ACCESO_DENEGADO", "No puede administrar usuarios de este condominio."
            )
        if await self.repo.contexto(condominio_id, bloquear=bloquear) is None:
            raise APIError(
                404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo con ese UUID."
            )
        await validar_sesion(actor, self.repo)

    async def listar(self, condominio_id, actor, limit=50, offset=0):
        await self._autorizar(condominio_id, actor)
        return await self.repo.listar(condominio_id, limit, offset)

    async def _auditar(
        self,
        cid,
        actor,
        usuario,
        accion,
        anterior,
        *,
        posterior=None,
        motivo="GESTION_ADMINISTRATIVA_USUARIOS",
    ):
        payload = AuditoriaPayload(
            condominio_id=str(cid),
            departamento_id=None,
            accion_ejecutada=accion,
            motivo=motivo,
            resultado="EXITOSO",
            actor_tipo=actor["rol"],
            actor_id=actor["sub"],
            estado_anterior=anterior,
            estado_posterior=(
                CuentaUsuarioResponse.model_validate(usuario).model_dump(mode="json")
                if posterior is None
                else posterior
            ),
            hash_previo=await self.repo.ultimo_hash(cid),
        )
        await self.repo.agregar(
            AuditoriaLogORM(
                condominio_id=cid,
                departamento_id=None,
                timestamp=payload.timestamp,
                accion_ejecutada=payload.accion_ejecutada,
                motivo=payload.motivo,
                resultado=payload.resultado,
                actor_tipo=payload.actor_tipo,
                actor_id=payload.actor_id,
                estado_anterior=payload.estado_anterior,
                estado_posterior=payload.estado_posterior,
                hash_previo=payload.hash_previo,
                hash_actual=payload.calcular_hash(),
            )
        )

    async def crear(self, cid: UUID, request: CrearUsuarioRequest, actor: dict) -> Usuario:
        await self._autorizar(cid, actor, bloquear=True)
        if await self.repo.duplicado(request.email, request.documento_identidad):
            raise APIError(409, "USUARIO_DUPLICADO", "El correo o documento ya está registrado.")
        usuario = Usuario(
            id=uuid4(),
            email=request.email,
            nombre=request.nombre,
            apellido=request.apellido,
            telefono=request.telefono,
            documento_identidad=request.documento_identidad,
            password_hash=hash_password(request.password.get_secret_value()),
            esta_activo=False,
            auth_revision=1,
            es_superadmin=False,
            creado_en=datetime.now(UTC),
        )
        try:
            await self.repo.agregar(usuario)
            await self.repo.agregar(
                UsuarioRol(usuario_id=usuario.id, condominio_id=cid, rol="RESIDENTE")
            )
            await self._auditar(cid, actor, usuario, "ALTA_USUARIO", {})
            await self.repo.confirmar()
        except IntegrityError as exc:
            nombre = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", "") or ""
            if nombre in {
                "uq_usuario_email_normalizado",
                "uq_usuario_documento_normalizado",
                "usuarios_email_key",
            }:
                raise APIError(
                    409, "USUARIO_DUPLICADO", "El correo o documento ya está registrado."
                ) from exc
            raise
        return usuario

    async def cambiar_estado(self, cid: UUID, usuario_id: UUID, esta_activo: bool, actor: dict):
        if actor["rol"] != "SUPERADMIN":
            raise APIError(
                403, "ACCESO_DENEGADO", "Solo SuperAdmin cambia el estado de las cuentas."
            )
        usuario = await self.repo.por_id(usuario_id, bloquear=True)
        if usuario is None:
            raise APIError(
                404, "USUARIO_NO_ENCONTRADO", "No existe el usuario en el contexto seleccionado."
            )
        contextos = await self.repo.condominios_usuario(usuario_id)
        if cid not in contextos:
            raise APIError(
                404, "USUARIO_NO_ENCONTRADO", "No existe el usuario en el contexto seleccionado."
            )
        await self.repo.bloquear_contextos(contextos)
        await self._autorizar(cid, actor)
        if usuario.esta_activo != esta_activo:
            anterior = CuentaUsuarioResponse.model_validate(usuario).model_dump(mode="json")
            usuario.esta_activo = esta_activo
            usuario.auth_revision += 1
            await self.repo.agregar(usuario)
            for contexto in contextos:
                await self._auditar(contexto, actor, usuario, "USUARIO_ESTADO_CAMBIADO", anterior)
        await self.repo.confirmar()
        return usuario

    async def consultar_rol(self, cid: UUID, usuario_id: UUID, actor: dict):
        await self._autorizar(cid, actor)
        asignacion = await self.repo.rol_usuario(usuario_id, cid)
        if asignacion is None:
            raise APIError(404, "ROL_NO_ENCONTRADO", "No existe una asignación en este condominio.")
        return asignacion

    async def gestionar_rol(self, cid: UUID, usuario_id: UUID, rol: str | None, actor: dict):
        """PUT asigna/reactiva; DELETE (rol=None) revoca sin borrar la asignación."""
        await self._autorizar(cid, actor)
        if str(usuario_id) == actor["sub"]:
            raise APIError(403, "ACCESO_DENEGADO", "No puede modificar su propia asignación.")
        if actor["rol"] != "SUPERADMIN" and await self.repo.rol_usuario(usuario_id, cid) is None:
            raise APIError(404, "ROL_NO_ENCONTRADO", "No existe una asignación en este condominio.")
        usuario = await self.repo.por_id(usuario_id, bloquear=True)
        if usuario is None:
            raise APIError(404, "USUARIO_NO_ENCONTRADO", "No existe la identidad solicitada.")
        if usuario.es_superadmin:
            raise APIError(
                403, "ACCESO_DENEGADO", "La concesión global se gestiona fuera de esta API."
            )
        contextos = set(await self.repo.condominios_usuario(usuario_id)) | {cid}
        await self.repo.bloquear_contextos(list(contextos))
        await self._autorizar(cid, actor)
        asignacion = await self.repo.rol_usuario(usuario_id, cid)
        if asignacion is None and (rol is None or actor["rol"] != "SUPERADMIN"):
            raise APIError(404, "ROL_NO_ENCONTRADO", "No existe una asignación en este condominio.")
        if actor["rol"] != "SUPERADMIN" and (
            rol == "ADMIN_JUNTA" or asignacion.rol not in {"AUDITOR", "RESIDENTE"}
        ):
            raise APIError(
                403, "ACCESO_DENEGADO", "Solo SuperAdmin puede gestionar roles de Junta."
            )

        anterior = (
            AsignacionRolResponse.model_validate(asignacion).model_dump(mode="json")
            if asignacion
            else {}
        )
        if asignacion is None:
            asignacion = UsuarioRol(
                usuario_id=usuario_id, condominio_id=cid, rol=rol, es_activo=True
            )
            accion = "ROL_ASIGNADO"
        elif rol is None:
            if not asignacion.es_activo:
                return asignacion
            asignacion.es_activo = False
            accion = "ROL_REVOCADO"
        else:
            if asignacion.es_activo and asignacion.rol == rol:
                return asignacion
            asignacion.rol = rol
            asignacion.es_activo = True
            accion = "ROL_CAMBIADO"
        usuario.auth_revision += 1
        await self.repo.agregar(usuario, asignacion)
        await self._auditar(
            cid,
            actor,
            usuario,
            accion,
            anterior,
            posterior=AsignacionRolResponse.model_validate(asignacion).model_dump(mode="json"),
            motivo="GESTION_ROLES_PERMISOS",
        )
        await self.repo.confirmar()
        return asignacion
