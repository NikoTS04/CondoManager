"""Reglas de registro y consulta de gastos (CON-51).

Esta etapa no implementa aprobación, presentación ni pagos. Las referencias a
CON-48/49 se rechazan mientras sus tablas no estén integradas en esta rama.
"""

import asyncio
import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import autorizar_condominio, denegar
from src.core.config import settings
from src.core.errors import APIError
from src.core.roles import RolUsuario
from src.modules.egresos.models import DocumentoFinanciero, Egreso
from src.modules.egresos.repository import SQLAlchemyEgresosRepository
from src.modules.egresos.schemas import (
    ActualizarEgresoRequest,
    CrearEgresoRequest,
    DocumentoFinancieroResponse,
    EgresoResponse,
)
from src.modules.egresos.storage import get_egresos_storage
from src.modules.pagos.repository import SQLAlchemyPagosRepository

ROLES_LECTURA = {
    RolUsuario.SUPERADMIN.value,
    RolUsuario.ADMIN_JUNTA.value,
    RolUsuario.AUDITOR.value,
}
ROLES_ESCRITURA = {RolUsuario.SUPERADMIN.value, RolUsuario.ADMIN_JUNTA.value}
MAX_NOMBRE_VISIBLE = 255
logger = logging.getLogger("condomanager.egresos")


def _decimal(valor: Decimal | None) -> str | None:
    return None if valor is None else f"{valor:.2f}"


def _snapshot(egreso: Egreso) -> dict:
    return {
        "egreso_id": str(egreso.id),
        "condominio_id": str(egreso.condominio_id),
        "concepto_id": str(egreso.concepto_id),
        "proveedor_id": str(egreso.proveedor_id) if egreso.proveedor_id else None,
        "contrato_id": str(egreso.contrato_id) if egreso.contrato_id else None,
        "presupuesto_id": str(egreso.presupuesto_id) if egreso.presupuesto_id else None,
        "item_presupuesto_id": (
            str(egreso.item_presupuesto_id) if egreso.item_presupuesto_id else None
        ),
        "descripcion": egreso.descripcion,
        "justificacion": egreso.justificacion,
        "moneda": egreso.moneda,
        "fecha_gasto": egreso.fecha_gasto.isoformat(),
        "monto_pactado": _decimal(egreso.monto_pactado),
        "monto_solicitado": _decimal(egreso.monto_solicitado),
        "monto_aprobado": _decimal(egreso.monto_aprobado),
        "monto_pagado": _decimal(egreso.monto_pagado),
        "estado": egreso.estado,
        "version": egreso.version,
    }


def _clean_filename(filename: str | None, stored_key: str) -> str:
    """Construye solo un nombre de presentación, nunca una ruta ni storage key."""
    raw = (filename or "documento").replace("\\", "/").rsplit("/", 1)[-1]
    raw = re.sub(r"[\x00-\x1f\x7f]", "", raw).strip(" .")
    stem = raw.rsplit(".", 1)[0] if "." in raw else raw
    stem = re.sub(r"[^\w .-]", "_", stem, flags=re.UNICODE).strip(" .") or "documento"
    extension = stored_key.rsplit(".", 1)[-1].lower()
    return f"{stem[: MAX_NOMBRE_VISIBLE - len(extension) - 1]}.{extension}"


class EgresosService:
    """Servicio transaccional de registro, consulta, edición y sustento CON-51."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = SQLAlchemyEgresosRepository(session)

    @staticmethod
    def _autorizar(actor: dict, condominio_id: UUID, *, escritura: bool) -> UUID:
        rol = actor.get("rol")
        permitidos = ROLES_ESCRITURA if escritura else ROLES_LECTURA
        if rol not in permitidos:
            denegar("El rol no tiene permiso para esta operación de egresos.")
        try:
            UUID(str(actor["sub"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(401, "TOKEN_INVALIDO", "La sesión no contiene un actor válido.") from exc
        return autorizar_condominio(actor, condominio_id, escritura=escritura)

    async def _bloquear_contexto(self, condominio_id: UUID, *, escritura: bool):
        condominio = await self.repository.bloquear_condominio(condominio_id)
        if condominio is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        if escritura and not condominio.activo:
            raise APIError(
                409, "CONDOMINIO_INACTIVO", "No se puede modificar un condominio inactivo."
            )
        return condominio

    async def _auditar(
        self,
        actor: dict,
        condominio_id: UUID,
        accion: str,
        motivo: str,
        anterior: dict,
        posterior: dict,
    ) -> None:
        # El lock del condominio ya se mantiene para encadenar el hash sin bifurcarlo.
        await SQLAlchemyPagosRepository(self.session).auditar(
            actor,
            condominio_id,
            None,
            accion,
            motivo,
            anterior,
            posterior,
        )

    async def _commit_or_conflict(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise APIError(
                409,
                "EGRESO_CONFLICTO_CONCURRENCIA",
                "El egreso cambió concurrentemente; recargue y vuelva a intentar.",
            ) from exc

    async def _rollback(self) -> None:
        if self.session.in_transaction():
            await self.session.rollback()

    @staticmethod
    def _validate_text(request: CrearEgresoRequest | ActualizarEgresoRequest) -> None:
        for name in ("descripcion", "justificacion"):
            value = getattr(request, name, None)
            if value is not None and "\x00" in value:
                raise APIError(
                    422, "DATOS_EGRESO_INVALIDOS", "El texto contiene caracteres inválidos."
                )

    async def _validate_links(
        self,
        condominio_id: UUID,
        *,
        concepto_id: UUID,
        presupuesto_id: UUID | None,
        item_presupuesto_id: UUID | None,
    ) -> None:
        concepto = await self.repository.obtener_concepto(condominio_id, concepto_id)
        if concepto is None:
            raise APIError(
                422,
                "CONCEPTO_PRESUPUESTAL_NO_DISPONIBLE",
                "El concepto no existe, está inactivo o pertenece a otro condominio.",
            )
        if (presupuesto_id is None) != (item_presupuesto_id is None):
            raise APIError(
                422,
                "REFERENCIA_PRESUPUESTO_INVALIDA",
                "presupuesto_id e item_presupuesto_id deben enviarse juntos.",
            )
        if presupuesto_id is None:
            return

        presupuesto = await self.repository.obtener_presupuesto(condominio_id, presupuesto_id)
        if presupuesto is None:
            raise APIError(
                404,
                "PRESUPUESTO_NO_ENCONTRADO",
                "No existe el presupuesto indicado en este condominio.",
            )
        item = next(
            (
                item
                for item in (presupuesto.items or [])
                if str(item.get("id")) == str(item_presupuesto_id)
            ),
            None,
        )
        if item is None or str(item.get("concepto_id")) != str(concepto_id):
            raise APIError(
                422,
                "ITEM_PRESUPUESTAL_NO_COINCIDE",
                "El ítem no pertenece al presupuesto y concepto seleccionados.",
            )

    @staticmethod
    def _serializar(egreso: Egreso) -> EgresoResponse:
        concepto = egreso.concepto
        proveedor = None
        # No cargar ni simular proveedor: referencias no nulas se rechazan mientras
        # CON-48/49 no esté disponible. El DTO conserva el slot para el adapter futuro.
        documentos = [DocumentoFinancieroResponse.model_validate(d) for d in egreso.documentos]
        aprobaciones = [
            {
                "id": a.id,
                "egreso_id": a.egreso_id,
                "version_egreso": a.version_egreso,
                "monto_revisado": a.monto_revisado,
                "decision": a.decision,
                "motivo": a.motivo,
                "vigente": a.version_egreso == egreso.version,
                "actor_id": a.actor_id,
                "creado_en": a.creado_en,
            }
            for a in egreso.aprobaciones
        ]
        pagos = []
        for pago in egreso.pagos:
            movimiento = next((m.id for m in pago.movimientos if m.tipo == "PAGO_EGRESO"), None)
            pagos.append(
                {
                    "id": pago.id,
                    "egreso_id": pago.egreso_id,
                    "cuenta_id": pago.cuenta_id,
                    "monto": pago.monto,
                    "fecha_pago": pago.fecha_pago,
                    "referencia": pago.referencia,
                    "documento_id": pago.documento_id,
                    "estado": pago.estado,
                    "actor_id": pago.actor_id,
                    "movimiento_caja_id": movimiento,
                    "creado_en": pago.creado_en,
                }
            )
        return EgresoResponse(
            id=egreso.id,
            condominio_id=egreso.condominio_id,
            concepto_id=egreso.concepto_id,
            concepto_codigo=concepto.codigo,
            categoria=concepto.categoria,
            proveedor_id=egreso.proveedor_id,
            contrato_id=egreso.contrato_id,
            proveedor=proveedor,
            presupuesto_id=egreso.presupuesto_id,
            item_presupuesto_id=egreso.item_presupuesto_id,
            descripcion=egreso.descripcion,
            justificacion=egreso.justificacion,
            moneda=egreso.moneda,
            fecha_gasto=egreso.fecha_gasto,
            monto_pactado=egreso.monto_pactado,
            monto_solicitado=egreso.monto_solicitado,
            monto_aprobado=egreso.monto_aprobado,
            monto_pagado=egreso.monto_pagado,
            estado=egreso.estado,
            version=egreso.version,
            creado_por=egreso.creado_por,
            creado_en=egreso.creado_en,
            actualizado_en=egreso.actualizado_en,
            documentos=documentos,
            aprobaciones=aprobaciones,
            pagos=pagos,
        )

    async def registrar(
        self, actor: dict, condominio_id: UUID, request: CrearEgresoRequest
    ) -> EgresoResponse:
        cid = self._autorizar(actor, condominio_id, escritura=True)
        if request.proveedor_id is not None or request.contrato_id is not None:
            raise APIError(
                409,
                "PROVEEDOR_NO_DISPONIBLE",
                "El directorio CON-48/49 todavía no está integrado en esta versión.",
            )
        self._validate_text(request)

        try:
            await self._bloquear_contexto(cid, escritura=True)
            await self._validate_links(
                cid,
                concepto_id=request.concepto_id,
                presupuesto_id=request.presupuesto_id,
                item_presupuesto_id=request.item_presupuesto_id,
            )
            ahora = datetime.now(UTC)
            egreso = Egreso(
                id=uuid4(),
                condominio_id=cid,
                concepto_id=request.concepto_id,
                proveedor_id=None,
                contrato_id=None,
                presupuesto_id=request.presupuesto_id,
                item_presupuesto_id=request.item_presupuesto_id,
                descripcion=request.descripcion,
                justificacion=request.justificacion,
                moneda=request.moneda,
                fecha_gasto=request.fecha_gasto,
                monto_pactado=request.monto_pactado,
                monto_solicitado=request.monto_solicitado,
                monto_aprobado=None,
                monto_pagado=Decimal("0.00"),
                estado="BORRADOR",
                version=1,
                creado_por=UUID(actor["sub"]),
                creado_en=ahora,
                actualizado_en=ahora,
            )
            await self.repository.agregar_egreso(egreso)
            await self._auditar(
                actor,
                cid,
                "EGRESO_CREADO",
                "REGISTRO_EGRESO_CON51",
                {},
                _snapshot(egreso),
            )
            await self._commit_or_conflict()
            persistido = await self.repository.obtener_egreso(cid, egreso.id)
            if persistido is None:
                raise APIError(
                    500, "EGRESO_NO_DISPONIBLE", "No se pudo recuperar el egreso creado."
                )
            return self._serializar(persistido)
        except Exception:
            await self._rollback()
            raise

    async def consultar(self, actor: dict, condominio_id: UUID, egreso_id: UUID) -> EgresoResponse:
        cid = self._autorizar(actor, condominio_id, escritura=False)
        if await self.repository.obtener_condominio(cid) is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        egreso = await self.repository.obtener_egreso(cid, egreso_id)
        if egreso is None:
            raise APIError(404, "EGRESO_NO_ENCONTRADO", "No existe el egreso en este condominio.")
        return self._serializar(egreso)

    async def listar(
        self,
        actor: dict,
        condominio_id: UUID,
        *,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        estado: str | None = None,
        proveedor_id: UUID | None = None,
        concepto_id: UUID | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> dict:
        cid = self._autorizar(actor, condominio_id, escritura=False)
        if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
            raise APIError(
                422, "FILTRO_FECHAS_INVALIDO", "fecha_desde no puede superar fecha_hasta."
            )
        if await self.repository.obtener_condominio(cid) is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        egresos, hay_mas = await self.repository.listar_egresos(
            cid,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado=estado,
            proveedor_id=proveedor_id,
            concepto_id=concepto_id,
            offset=offset,
            limit=limit,
        )
        return {"items": [self._serializar(e) for e in egresos], "hay_mas": hay_mas}

    async def actualizar(
        self,
        actor: dict,
        condominio_id: UUID,
        egreso_id: UUID,
        request: ActualizarEgresoRequest,
    ) -> EgresoResponse:
        cid = self._autorizar(actor, condominio_id, escritura=True)
        fields = request.model_fields_set - {"version_esperada"}
        self._validate_text(request)
        if any(
            getattr(request, key) is not None
            for key in ("proveedor_id", "contrato_id")
            if key in fields
        ):
            raise APIError(
                409,
                "PROVEEDOR_NO_DISPONIBLE",
                "El directorio CON-48/49 todavía no está integrado en esta versión.",
            )

        try:
            await self._bloquear_contexto(cid, escritura=True)
            egreso = await self.repository.obtener_egreso(cid, egreso_id, bloquear=True)
            if egreso is None:
                raise APIError(
                    404, "EGRESO_NO_ENCONTRADO", "No existe el egreso en este condominio."
                )
            if egreso.estado != "BORRADOR":
                raise APIError(
                    409,
                    "EGRESO_NO_EDITABLE",
                    "Solo se pueden editar egresos en estado BORRADOR.",
                    {"estado": egreso.estado},
                )
            if egreso.version != request.version_esperada:
                raise APIError(
                    409,
                    "EGRESO_VERSION_OBSOLETA",
                    "El egreso cambió; recargue antes de editarlo.",
                    {"version_actual": egreso.version},
                )

            if "proveedor_id" in fields and request.proveedor_id is None:
                if egreso.contrato_id is not None and "contrato_id" not in fields:
                    raise APIError(
                        422,
                        "REFERENCIA_CONTRATO_INVALIDA",
                        "Elimine el contrato en la misma actualización que el proveedor.",
                    )

            anterior = _snapshot(egreso)
            cambios = request.model_dump(exclude_unset=True, exclude={"version_esperada"})
            cambios.pop("proveedor_id", None)
            cambios.pop("contrato_id", None)
            cambios.pop("version_esperada", None)
            for campo, valor in cambios.items():
                if valor is None and campo in {
                    "concepto_id",
                    "descripcion",
                    "justificacion",
                    "fecha_gasto",
                    "monto_solicitado",
                }:
                    raise APIError(422, "DATOS_EGRESO_INVALIDOS", f"{campo} no admite null.")
            efectivo = {k: v for k, v in cambios.items() if getattr(egreso, k) != v}
            if not efectivo:
                return self._serializar(egreso)

            concepto_id = efectivo.get("concepto_id", egreso.concepto_id)
            presupuesto_id = efectivo.get("presupuesto_id", egreso.presupuesto_id)
            item_id = efectivo.get("item_presupuesto_id", egreso.item_presupuesto_id)
            if any(
                key in efectivo for key in ("concepto_id", "presupuesto_id", "item_presupuesto_id")
            ):
                await self._validate_links(
                    cid,
                    concepto_id=concepto_id,
                    presupuesto_id=presupuesto_id,
                    item_presupuesto_id=item_id,
                )
            for campo, valor in efectivo.items():
                setattr(egreso, campo, valor)
            egreso.version += 1
            egreso.actualizado_en = datetime.now(UTC)
            self.session.add(egreso)
            await self.session.flush()
            await self._auditar(
                actor,
                cid,
                "EGRESO_MODIFICADO",
                "ACTUALIZACION_BORRADOR_CON51",
                anterior,
                _snapshot(egreso),
            )
            await self._commit_or_conflict()
            persistido = await self.repository.obtener_egreso(cid, egreso_id)
            if persistido is None:
                raise APIError(
                    500, "EGRESO_NO_DISPONIBLE", "No se pudo recuperar el egreso actualizado."
                )
            return self._serializar(persistido)
        except Exception:
            await self._rollback()
            raise

    async def adjuntar_documento(
        self,
        actor: dict,
        condominio_id: UUID,
        egreso_id: UUID,
        archivo: UploadFile,
        tipo: str,
    ) -> DocumentoFinancieroResponse:
        cid = self._autorizar(actor, condominio_id, escritura=True)
        if tipo == "EVIDENCIA_PAGO":
            raise APIError(
                409,
                "CON52_NO_DISPONIBLE",
                "La evidencia de pago se habilitará junto con CON-52.",
            )
        if tipo != "SUSTENTO":
            raise APIError(
                422, "TIPO_DOCUMENTO_INVALIDO", "El tipo de documento no es válido para CON-51."
            )

        # Comprueba autorización del recurso antes de consumir o escribir el archivo.
        previo = await self.repository.obtener_egreso(cid, egreso_id)
        if previo is None:
            raise APIError(404, "EGRESO_NO_ENCONTRADO", "No existe el egreso en este condominio.")
        if previo.estado != "BORRADOR":
            raise APIError(
                409,
                "EGRESO_NO_EDITABLE",
                "El sustento solo puede adjuntarse a un egreso BORRADOR.",
            )

        storage = get_egresos_storage()
        limite = settings.VOUCHER_MAX_BYTES
        try:
            datos = await archivo.read(limite + 1)
        finally:
            await archivo.close()
        if len(datos) > limite:
            raise APIError(
                413,
                "ARCHIVO_DEMASIADO_GRANDE",
                f"El archivo excede el límite configurado de {limite} bytes.",
            )
        _, mime = await asyncio.to_thread(storage.validar, datos)
        nombre_storage, mime_guardado = await asyncio.to_thread(storage.guardar, datos)
        nombre_visible = _clean_filename(archivo.filename, nombre_storage)
        digest = sha256(datos).hexdigest()
        storage_created = True
        try:
            await self._bloquear_contexto(cid, escritura=True)
            egreso = await self.repository.obtener_egreso(cid, egreso_id, bloquear=True)
            if egreso is None:
                raise APIError(
                    404, "EGRESO_NO_ENCONTRADO", "No existe el egreso en este condominio."
                )
            if egreso.estado != "BORRADOR":
                raise APIError(
                    409,
                    "EGRESO_NO_EDITABLE",
                    "El sustento solo puede adjuntarse a un egreso BORRADOR.",
                )
            ahora = datetime.now(UTC)
            documento = DocumentoFinanciero(
                id=uuid4(),
                condominio_id=cid,
                egreso_id=egreso.id,
                tipo="SUSTENTO",
                archivo_nombre=nombre_visible,
                mime=mime_guardado or mime,
                tamano_bytes=len(datos),
                sha256=digest,
                storage_key=nombre_storage,
                creado_por=UUID(actor["sub"]),
                creado_en=ahora,
            )
            await self.repository.agregar_documento(documento)
            await self._auditar(
                actor,
                cid,
                "DOCUMENTO_EGRESO_ADJUNTADO",
                "SUSTENTO_EGRESO_CON51",
                _snapshot(egreso),
                {
                    "egreso_id": str(egreso.id),
                    "documento_id": str(documento.id),
                    "tipo": documento.tipo,
                    "sha256": digest,
                    "tamano_bytes": len(datos),
                },
            )
            await self._commit_or_conflict()
            storage_created = False
            return DocumentoFinancieroResponse.model_validate(documento)
        except Exception:
            await self._rollback()
            if storage_created:
                try:
                    await asyncio.to_thread(storage.eliminar, nombre_storage)
                except Exception:
                    # No filtrar claves privadas ni reemplazar el error transaccional original.
                    logger.exception("No se pudo compensar un archivo financiero sin registro")
            raise

    async def consultar_documento(
        self,
        actor: dict,
        condominio_id: UUID,
        egreso_id: UUID,
        documento_id: UUID,
    ) -> tuple[bytes, str, str]:
        cid = self._autorizar(actor, condominio_id, escritura=False)
        if await self.repository.obtener_condominio(cid) is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        documento = await self.repository.obtener_documento(cid, documento_id, egreso_id=egreso_id)
        if documento is None or documento.tipo != "SUSTENTO":
            raise APIError(
                404, "DOCUMENTO_EGRESO_NO_ENCONTRADO", "No existe el documento solicitado."
            )
        storage = get_egresos_storage()
        contenido = await asyncio.to_thread(storage.leer, documento.storage_key)
        return contenido, documento.mime, documento.archivo_nombre
