"""CON-22/70: operaciones financieras reales; nunca usa el almacén piloto."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import contexto_consulta, puede_ver_departamento
from src.core.database import get_db_session
from src.core.errors import APIError
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.pagos.contabilidad import CERO, MAX_MONEDA, plan_imputacion, saldo_en_mora
from src.modules.pagos.fondos import FondosMorasService
from src.modules.pagos.models import ComprobantePago, ImputacionPago
from src.modules.pagos.models_persistencia import ArchivoVoucher, EventoPagoOutbox, RevisionPago
from src.modules.pagos.mora_diaria import MoraDiariaService
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.pagos.schemas import (
    ComprobantePagoDTO,
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ConciliarPagoRequest,
    ReportarPagoRequest,
)
from src.modules.pagos.service import PagosService
from src.modules.pagos.storage import MAX_BYTES, VoucherStorage
from src.shared.fechas import fecha_lima


class PagosPersistentesService:
    def __init__(self, session: AsyncSession, storage: VoucherStorage | None = None):
        self.session = session
        self.repo = SQLAlchemyPagosRepository(session)
        self.storage = storage or VoucherStorage()

    @staticmethod
    def dto(c: ComprobantePago) -> ComprobantePagoDTO:
        return ComprobantePagoDTO(
            id=c.id,
            departamento_id=c.departamento_id,
            banco=c.banco_origen,
            numero_operacion=c.numero_operacion,
            fecha_operacion=c.fecha_operacion,
            monto=c.monto,
            estado=c.estado,
            idempotency_hash=c.idempotency_hash,
            url_voucher=f"/api/v1/pagos/{c.id}/voucher",
            motivo_rechazo=c.motivo_rechazo,
        )

    async def listar(self, usuario, condominio_id=None):
        cid = contexto_consulta(usuario, condominio_id)
        async with self.session.begin():
            query = (
                select(ComprobantePago)
                .join(Departamento, ComprobantePago.departamento_id == Departamento.id)
                .join(Edificio, Departamento.edificio_id == Edificio.id)
                .where(Edificio.condominio_id == cid)
                .order_by(ComprobantePago.creado_en.desc(), ComprobantePago.id)
            )
            return [
                self.dto(c)
                for c in await self.session.scalars(query)
                if puede_ver_departamento(usuario, c.departamento_id)
            ]

    async def departamentos_portal(self, usuario, condominio_id=None):
        cid = contexto_consulta(usuario, condominio_id)
        async with self.session.begin():
            condominio = await self.session.get(Condominio, cid)
            if condominio is None or not condominio.activo:
                raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo.")
            departamentos = await self.session.scalars(
                select(Departamento)
                .join(Edificio)
                .where(Edificio.condominio_id == cid, Departamento.activo.is_(True))
                .order_by(Departamento.numero, Departamento.id)
            )
            resultado = []
            for depto in departamentos:
                if not puede_ver_departamento(usuario, depto.id):
                    continue
                cuotas = await self.repo.cuotas(depto.id)
                saldo = saldo_en_mora(cuotas, condominio.dias_gracia, fecha_lima())
                resultado.append(
                    {
                        "id": depto.id,
                        "condominio_id": cid,
                        "numero": depto.numero,
                        "piso": depto.piso,
                        "coeficiente": depto.coeficiente_participacion,
                        "saldo_a_favor": depto.saldo_a_favor,
                        "estado_financiero": "EN_MORA" if saldo > CERO else "AL_DIA",
                        "deuda_vencida": saldo,
                        "activo": depto.activo,
                    }
                )
            return resultado

    @asynccontextmanager
    async def archivo_nuevo(self, did, archivo, usuario):
        datos = await archivo.read(MAX_BYTES + 1)
        nombre, content_type = await asyncio.to_thread(self.storage.guardar, datos)
        try:
            subida = ArchivoVoucher(
                nombre=nombre,
                departamento_id=did,
                usuario_id=UUID(usuario["sub"]),
                content_type=content_type,
                size_bytes=len(datos),
            )
            self.session.add(subida)
            yield subida
            await self.session.flush()
        except BaseException:
            await asyncio.to_thread(self.storage.eliminar, nombre)
            raise
        # El commit se realiza fuera: su respuesta perdida nunca autoriza borrar evidencia.

    async def reportar(self, request: ReportarPagoRequest, archivo: UploadFile, usuario: dict):
        async with self.session.begin():
            depto, condominio = await self.repo.departamento(
                request.departamento_id, usuario, escritura=True, bloquear=True
            )
            hash_id = PagosService.calcular_hash_idempotencia(
                str(condominio.id),
                request.banco,
                request.numero_operacion,
                request.fecha_operacion,
                request.monto,
            )
            previo = await self.session.scalar(
                select(ComprobantePago).where(ComprobantePago.idempotency_hash == hash_id)
            )
            if previo is not None:
                if previo.departamento_id != depto.id:
                    raise APIError(
                        409,
                        "VOUCHER_UNIDAD_DISTINTA",
                        "El comprobante no puede reutilizarse en otra unidad.",
                    )
                if previo.estado == "APROBADO":
                    raise APIError(
                        409, "VOUCHER_YA_CONCILIADO", "El comprobante ya fue conciliado."
                    )
                if previo.estado in {"OBSERVADO", "RECHAZADO"}:
                    raise APIError(
                        409,
                        "VOUCHER_REQUIERE_SUBSANACION"
                        if previo.estado == "OBSERVADO"
                        else "VOUCHER_RECHAZADO",
                        "Subsane el voucher observado."
                        if previo.estado == "OBSERVADO"
                        else "La operación fue rechazada.",
                    )
                return ComprobanteRecibidoResponse(
                    comprobante_id=previo.id,
                    estado=previo.estado,
                    mensaje="El comprobante ya fue recibido y se encuentra en revisión.",
                    idempotency_hash=hash_id,
                    codigo="VOUCHER_EN_EVALUACION",
                ), False
            async with self.archivo_nuevo(depto.id, archivo, usuario) as subida:
                nuevo = ComprobantePago(
                    id=uuid4(),
                    departamento_id=depto.id,
                    banco_origen=request.banco,
                    numero_operacion=request.numero_operacion,
                    fecha_operacion=request.fecha_operacion,
                    monto=request.monto,
                    url_voucher=subida.nombre,
                    idempotency_hash=hash_id,
                    estado="EN_REVISION",
                )
                self.session.add(nuevo)
                await self.session.flush()
                subida.comprobante_id = nuevo.id
                await self.repo.auditar(
                    usuario,
                    condominio.id,
                    depto.id,
                    "COMPROBANTE_REPORTADO",
                    "REPORTE_PAGO_CON22",
                    {},
                    {
                        "comprobante_id": str(nuevo.id),
                        "estado": nuevo.estado,
                        "monto": f"{nuevo.monto:.2f}",
                    },
                )
                self._evento(nuevo, condominio.id, "PagoReportadoEvent")
            resultado = ComprobanteRecibidoResponse(
                comprobante_id=nuevo.id,
                estado=nuevo.estado,
                mensaje="Comprobante recibido. Pendiente de revisión por la junta.",
                idempotency_hash=hash_id,
            )
        return resultado, True

    async def subsanar(self, id, archivo, usuario):
        async with self.session.begin():
            comprobante, depto, condominio = await self.repo.comprobante(
                id, usuario, escritura=True, bloquear=True
            )
            comprobante = await self.session.scalar(
                select(ComprobantePago)
                .where(ComprobantePago.id == id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if comprobante.estado != "OBSERVADO":
                raise APIError(
                    409,
                    "ESTADO_COMPROBANTE_INVALIDO",
                    "Solo puede subsanar un comprobante observado.",
                )
            anterior = {"estado": comprobante.estado, "archivo": comprobante.url_voucher}
            async with self.archivo_nuevo(depto.id, archivo, usuario) as subida:
                subida.comprobante_id = id
                comprobante.url_voucher = subida.nombre
                comprobante.estado = "EN_REVISION"
                comprobante.motivo_rechazo = None
                comprobante.conciliado_por = None
                comprobante.conciliado_en = None
                await self.repo.auditar(
                    usuario,
                    condominio.id,
                    depto.id,
                    "COMPROBANTE_SUBSANADO",
                    "NUEVA_EVIDENCIA_CON72",
                    anterior,
                    {"estado": "EN_REVISION", "archivo": subida.nombre},
                )
                self._evento(comprobante, condominio.id, "PagoReportadoEvent")
            return ComprobanteRecibidoResponse(
                comprobante_id=id, idempotency_hash=comprobante.idempotency_hash
            )

    async def revisar(self, id: UUID, request: ConciliarPagoRequest, usuario: dict):
        if usuario.get("rol") not in {"SUPERADMIN", "ADMIN_JUNTA"}:
            raise APIError(403, "ACCESO_DENEGADO", "Solo la administración puede revisar pagos.")
        motivo = (request.motivo_rechazo or "").strip() if request.decision != "APROBADO" else ""
        notas = (request.notas_internas or "").strip() or None
        if request.decision != "APROBADO" and not motivo:
            raise APIError(422, "MOTIVO_REQUERIDO", "Indique el motivo de observación o rechazo.")
        async with self.session.begin():
            comprobante, depto, condominio = await self.repo.comprobante(
                id, usuario, escritura=True, bloquear=True
            )
            cuotas = await self.repo.cuotas(depto.id, bloquear=True)
            comprobante = await self.session.scalar(
                select(ComprobantePago)
                .where(ComprobantePago.id == id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if comprobante.estado != "EN_REVISION":
                revision = await self.revision_vigente(comprobante)
                if (
                    revision is not None
                    and revision.decision == request.decision
                    and (revision.motivo or "") == motivo
                    and revision.notas_internas == notas
                ):
                    return self.resultado_revision(revision)
                raise APIError(
                    409,
                    "ESTADO_COMPROBANTE_INVALIDO",
                    "La decisión ya es definitiva; no se vuelve a aplicar.",
                )
            ahora = datetime.now(UTC)
            hoy = fecha_lima()
            anterior = {"estado": comprobante.estado, "saldo_a_favor": str(depto.saldo_a_favor)}
            total_aplicado, credito = CERO, CERO
            if request.decision == "APROBADO" and comprobante.fecha_operacion > hoy:
                raise APIError(422, "FECHA_BANCARIA_FUTURA", "La fecha bancaria no puede ser futura en Lima.")
            motor = await MoraDiariaService(self.session).reconstruir(
                depto, condominio, cuotas, usuario, hoy,
                nuevo=comprobante if request.decision == "APROBADO" else None,
                pausar_revision=False, ahora=ahora,
            )
            if request.decision == "APROBADO":
                if motor is not None:
                    total_aplicado, credito = motor["monto_imputado"], motor["credito"]
                else:
                    plan = plan_imputacion(cuotas, comprobante.monto, comprobante.fecha_operacion)
                    imputaciones = {}
                    credito = plan["remanente"]
                    if depto.saldo_a_favor + credito > MAX_MONEDA:
                        raise APIError(
                            422, "SALDO_FUERA_DE_RANGO", "El saldo a favor excede el límite contable."
                        )
                    for cuota in cuotas:
                        aplicado = plan["aplicaciones"].get(cuota.id, CERO)
                        if aplicado <= CERO:
                            continue
                        cuota.monto_pagado += aplicado
                        if cuota.monto_pagado == cuota.monto_total_exigible:
                            cuota.estado = "PAGADA"
                        elif saldo_en_mora([cuota], condominio.dias_gracia, hoy) > CERO:
                            cuota.estado = "EN_MORA"
                        else:
                            cuota.estado = "PAGO_PARCIAL"
                        imputacion_id = uuid4()
                        self.session.add(ImputacionPago(id=imputacion_id, comprobante_id=id,
                                                        cuota_id=cuota.id, monto_aplicado=aplicado))
                        imputaciones[id, cuota.id] = imputacion_id
                        total_aplicado += aplicado
                    depto.saldo_a_favor += credito
                    await FondosMorasService(self.session).registrar_cobros(
                        depto, condominio, {}, {(id, cid, "MORA"): importes[0]
                            for cid, importes in plan["componentes"].items() if importes[0]},
                        {}, usuario, legacy=imputaciones)
                depto.estado_financiero = (
                    "EN_MORA"
                    if saldo_en_mora(cuotas, condominio.dias_gracia, hoy) > CERO
                    else "AL_DIA"
                )
            comprobante.estado = request.decision
            comprobante.motivo_rechazo = motivo if request.decision != "APROBADO" else None
            comprobante.conciliado_por = UUID(usuario["sub"])
            comprobante.conciliado_en = ahora
            resultado = ConciliacionResultResponse(
                comprobante_id=id,
                estado_final=request.decision,
                monto_imputado=total_aplicado,
                nuevo_saldo_departamento=sum(
                    (c.monto_total_exigible - c.monto_pagado for c in cuotas), CERO
                ),
                saldo_a_favor_generado=credito,
                departamento_habilitado_reservas=saldo_en_mora(
                    cuotas, condominio.dias_gracia, hoy
                )
                == CERO,
                motivo_rechazo=comprobante.motivo_rechazo,
            )
            revision = RevisionPago(
                id=uuid4(),
                comprobante_id=id,
                decision=request.decision,
                motivo=motivo or None,
                actor_id=UUID(usuario["sub"]),
                creado_en=ahora,
                resultado=resultado.model_dump(mode="json"),
                archivo_nombre=comprobante.url_voucher,
                notas_internas=notas,
            )
            self.session.add(revision)
            await self.repo.auditar(
                usuario,
                condominio.id,
                depto.id,
                f"REVISION_PAGO_{request.decision}",
                motivo or "APROBACION_PAGO_CON70",
                anterior,
                {**resultado.model_dump(mode="json"), "saldo_a_favor": str(depto.saldo_a_favor)},
            )
            evento = {
                "APROBADO": "PagoConciliadoEvent",
                "OBSERVADO": "PagoRevisadoEvent",
                "RECHAZADO": "PagoRevisadoEvent",
            }[request.decision]
            self._evento(
                comprobante,
                condominio.id,
                evento,
                {
                    "revision_id": str(revision.id),
                    "motivo": motivo or None,
                    "resultado": revision.resultado,
                },
            )
            await self.session.flush()
        return resultado

    async def resultado(self, id, usuario):
        async with self.session.begin():
            comprobante, _, _ = await self.repo.comprobante(id, usuario)
            revision = await self.revision_vigente(comprobante)
            if revision is None:
                raise APIError(
                    404, "RESULTADO_NO_DISPONIBLE", "El comprobante aún no tiene revisión."
                )
            return self.resultado_revision(revision)

    async def revision_vigente(self, comprobante):
        if comprobante.estado == "EN_REVISION":
            return None
        revision = await self.session.scalar(
            select(RevisionPago)
            .where(
                RevisionPago.comprobante_id == comprobante.id,
            )
            .order_by(RevisionPago.creado_en.desc(), RevisionPago.id.desc())
            .limit(1)
        )
        return (
            revision
            if revision is not None and revision.archivo_nombre in (None, comprobante.url_voucher)
            else None
        )

    @staticmethod
    def resultado_revision(revision):
        return ConciliacionResultResponse.model_validate(
            {
                **revision.resultado,
                "motivo_rechazo": revision.resultado.get("motivo_rechazo", revision.motivo)
                if revision.decision != "APROBADO"
                else None,
            }
        )

    async def evidencias(self, id, usuario):
        async with self.session.begin():
            await self.repo.comprobante(id, usuario)
            rows = await self.session.execute(
                select(RevisionPago.id, ArchivoVoucher.content_type, RevisionPago.creado_en)
                .join(ArchivoVoucher, RevisionPago.archivo_nombre == ArchivoVoucher.nombre)
                .where(RevisionPago.comprobante_id == id, ArchivoVoucher.comprobante_id == id)
                .order_by(RevisionPago.creado_en.desc(), RevisionPago.id.desc())
            )
            return [dict(evidencia_id=r.id, content_type=r.content_type, creado_en=r.creado_en) for r in rows]

    async def voucher(self, id, usuario, evidencia_id=None):
        async with self.session.begin():
            comprobante, _, _ = await self.repo.comprobante(id, usuario)
            nombre = comprobante.url_voucher
            if evidencia_id is not None:
                nombre = await self.session.scalar(
                    select(ArchivoVoucher.nombre)
                    .join(RevisionPago, RevisionPago.archivo_nombre == ArchivoVoucher.nombre)
                    .where(RevisionPago.id == evidencia_id, RevisionPago.comprobante_id == id,
                           ArchivoVoucher.comprobante_id == id)
                )
                if nombre is None:
                    raise APIError(404, "EVIDENCIA_NO_ENCONTRADA", "No existe evidencia autorizada.")
            ruta = await asyncio.to_thread(self.storage.ruta, nombre)
            return ruta, nombre

    def _evento(self, comprobante, cid, tipo, extra=None):
        id = uuid4()
        ahora = datetime.now(UTC)
        data = {
            "comprobante_id": str(comprobante.id),
            "departamento_id": str(comprobante.departamento_id),
            "condominio_id": str(cid),
        }
        if tipo == "PagoReportadoEvent":
            data.update(
                estado="EN_REVISION",
                monto=f"{comprobante.monto:.2f}",
                fecha_operacion=comprobante.fecha_operacion.isoformat(),
            )
        else:
            resultado = extra["resultado"]
            campos = (
                ("estado_final", "motivo_rechazo")
                if tipo == "PagoRevisadoEvent"
                else (
                    "estado_final",
                    "monto_imputado",
                    "nuevo_saldo_departamento",
                    "saldo_a_favor_generado",
                    "departamento_habilitado_reservas",
                )
            )
            data.update({k: resultado[k] for k in campos})
        self.session.add(
            EventoPagoOutbox(
                id=id,
                comprobante_id=comprobante.id,
                creado_en=ahora,
                payload={
                    "event_id": str(id),
                    "event_type": tipo,
                    "schema_version": 1,
                    "producer": "service.pagos",
                    "occurred_at": ahora.isoformat(),
                    "correlation_id": str(comprobante.id),
                    "causation_id": None,
                    "data": data,
                },
            )
        )


def get_pagos_service(session: AsyncSession = Depends(get_db_session, use_cache=False)):
    # La sesión financiera es distinta de la consulta de autenticación.
    return PagosPersistentesService(session)
