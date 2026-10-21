"""CON-46: cancelación atómica, resultado repetible y evento durable.

CON-41/73 mantienen la creación. Mientras se integra su productor SQL, se puede
adoptar una reserva del piloto en la misma transacción que la cancela. SQL tiene
precedencia y la memoria solo se actualiza después del commit.
"""

from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.authorization import autorizar_departamento, puede_ver_departamento
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.modules.condominios.models import Condominio
from src.modules.pagos.models import ComprobantePago
from src.modules.reservas.areas.models import AreaComun
from src.modules.reservas.areas.repository import AreasRepository
from src.modules.reservas.models import (
    CancelacionReserva,
    CobroReserva,
    EventoReservaOutbox,
    Reserva,
)
from src.modules.reservas.schemas import CancelarReservaResponse, ReservaResponseDTO
from src.modules.reservas.service import CancelacionInvalidaException, ReservasService


class CancelacionesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.areas = AreasRepository(session)

    @staticmethod
    def representar(reserva, area):
        return {
            **{col.name: getattr(reserva, col.name) for col in Reserva.__table__.columns},
            "condominio_id": area.condominio_id,
        }

    async def _reserva(self, rid, bloquear=False):
        query = (
            select(Reserva, AreaComun)
            .join(AreaComun, AreaComun.id == Reserva.area_id)
            .where(Reserva.id == rid)
            .execution_options(populate_existing=True)
        )
        if bloquear:
            query = query.with_for_update(of=Reserva)
        return (await self.session.execute(query)).one_or_none()

    async def historial(self, cid, actor, area_id=None, fecha=None):
        """Permite consultar las cancelaciones desde otra sesión o tras reiniciar."""
        try:
            if not await self.session.scalar(text("SELECT to_regclass('reservas') IS NOT NULL")):
                return []
            query = (
                select(Reserva, AreaComun, Condominio.moneda)
                .join(AreaComun, AreaComun.id == Reserva.area_id)
                .join(Condominio, Condominio.id == AreaComun.condominio_id)
                .where(AreaComun.condominio_id == cid)
                .order_by(Reserva.fecha_reserva, Reserva.hora_inicio, Reserva.id)
            )
            if area_id is not None:
                query = query.where(Reserva.area_id == area_id)
            if fecha is not None:
                query = query.where(Reserva.fecha_reserva == fecha)
            return [
                ReservaResponseDTO(
                    **self.representar(reserva, area), area_nombre=area.nombre, moneda=moneda
                )
                for reserva, area, moneda in await self.session.execute(query)
                if puede_ver_departamento(actor, reserva.departamento_id)
            ]
        except SQLAlchemyError as exc:
            raise APIError(
                503, "RESERVAS_NO_DISPONIBLES", "No se pudo consultar las reservas."
            ) from exc

    async def _cobro(self, reserva):
        cobro = await self.session.scalar(
            select(CobroReserva).where(CobroReserva.reserva_id == reserva.id).with_for_update()
        )
        if cobro is None:
            return None
        comprobante = await self.session.get(ComprobantePago, cobro.comprobante_id)
        if (
            comprobante is None
            or comprobante.estado != "APROBADO"
            or comprobante.conciliado_en is None
            or comprobante.departamento_id != reserva.departamento_id
            or cobro.monto > comprobante.monto
        ):
            raise APIError(
                409,
                "COBRO_RESERVA_INCONSISTENTE",
                "El cobro vinculado requiere revisión financiera.",
            )
        return {
            "monto": cobro.monto,
            "monto_compensado": cobro.monto_compensado,
            "reembolsable": cobro.reembolsable,
        }

    async def _guardar(self, reserva, datos, resultado, auditoria, actor):
        reserva.estado = "CANCELADA"
        auditoria.hash_previo = await self.areas.ultimo_hash(datos["condominio_id"])
        auditoria.estado_posterior = resultado.model_dump(mode="json")
        self.session.add(
            AuditoriaLogORM(
                **auditoria.model_dump(exclude={"hash_actual", "condominio_id", "departamento_id"}),
                condominio_id=datos["condominio_id"],
                departamento_id=reserva.departamento_id,
                hash_actual=auditoria.calcular_hash(),
            )
        )
        self.session.add(
            CancelacionReserva(
                reserva_id=reserva.id,
                actor_id=UUID(actor["sub"]),
                motivo=auditoria.motivo,
                fecha_cancelacion=resultado.fecha_cancelacion,
                resultado=resultado.model_dump(mode="json"),
            )
        )
        eid = uuid4()
        self.session.add(
            EventoReservaOutbox(
                id=eid,
                reserva_id=reserva.id,
                creado_en=resultado.fecha_cancelacion,
                payload={
                    "event_id": str(eid),
                    "event_type": "ReservaCanceladaEvent",
                    "schema_version": 1,
                    "producer": "service.reservas",
                    "occurred_at": resultado.fecha_cancelacion.isoformat(),
                    "correlation_id": str(eid),
                    "causation_id": None,
                    "data": {
                        "condominio_id": str(datos["condominio_id"]),
                        "departamento_id": str(reserva.departamento_id),
                        "reserva_id": str(reserva.id),
                        "area_id": str(reserva.area_id),
                        "fecha_reserva": reserva.fecha_reserva.isoformat(),
                        "hora_inicio": reserva.hora_inicio.isoformat(timespec="seconds"),
                        "hora_fin": reserva.hora_fin.isoformat(timespec="seconds"),
                        "zona_horaria": reserva.zona_horaria,
                        "fecha_cancelacion": resultado.fecha_cancelacion.isoformat(),
                        "motivo": auditoria.motivo,
                        "ajuste_economico": resultado.ajuste_economico.model_dump(mode="json"),
                    },
                },
            )
        )
        await self.session.flush()

    async def cancelar(self, rid, request, actor, piloto=None):
        try:
            async with self.session.begin():
                row = await self._reserva(rid)
                datos = self.representar(*row) if row else dict(piloto or {})
                if not datos:
                    raise APIError(404, "RESERVA_NO_ENCONTRADA", "Reserva no encontrada.")
                cid, did = datos["condominio_id"], datos["departamento_id"]
                autorizar_departamento(actor, did, cid, escritura=True)
                # Orden compartido con creación: condominio -> departamento ->
                # área -> reserva. El condominio también serializa la cadena auditada.
                if await self.areas.contexto(cid, bloquear=True) is None:
                    raise APIError(403, "ACCESO_DENEGADO", "El condominio no está habilitado.")
                actor = await self.areas.validar_actor(actor)
                autorizar_departamento(actor, did, cid, escritura=True)
                depto = await self.areas.identidad.departamento(cid, did, bloquear=True)
                if depto is None:
                    raise APIError(403, "ACCESO_DENEGADO", "La unidad no pertenece al condominio.")
                area = await self.areas.area(cid, datos["area_id"], bloquear=True)
                if area is None:
                    raise APIError(404, "AREA_NO_ENCONTRADA", "El área no pertenece al condominio.")
                row = await self._reserva(rid, bloquear=True)
                if row:
                    reserva = row[0]
                    datos = self.representar(*row)
                    # Revalidar también los identificadores del registro bloqueado.
                    autorizar_departamento(
                        actor, reserva.departamento_id, row[1].condominio_id, escritura=True
                    )
                else:
                    # Puente temporal: solo datos del servidor, nunca del cuerpo HTTP.
                    try:
                        creador_id = UUID(str(datos["usuario_id"]))
                    except (KeyError, TypeError, ValueError):
                        raise APIError(
                            409,
                            "RESERVA_REQUIERE_RECONCILIACION",
                            "La reserva piloto no conserva un creador válido. Requiere revisión.",
                        ) from None
                    reserva = Reserva(
                        **{
                            col.name: datos[col.name]
                            for col in Reserva.__table__.columns
                            if col.name in datos
                        },
                    )
                    reserva.usuario_id = creador_id
                    reserva.zona_horaria = datos.get("zona_horaria") or "UTC"
                    self.session.add(reserva)
                    await self.session.flush()
                if reserva.estado == "CANCELADA":
                    anterior = await self.session.get(CancelacionReserva, rid)
                    if anterior is None:
                        raise APIError(
                            422,
                            "ESTADO_RESERVA_INVALIDO",
                            "La cancelación histórica no dispone de un resultado verificable.",
                        )
                    return CancelarReservaResponse.model_validate(anterior.resultado)
                resultado, auditoria = ReservasService.procesar_cancelacion(
                    datos, request, actor=actor
                )
                resultado.ajuste_economico = ReservasService.ajuste_cancelacion(
                    await self._cobro(reserva)
                )
                await self._guardar(reserva, datos, resultado, auditoria, actor)
            return resultado
        except CancelacionInvalidaException as exc:
            raise APIError(422, exc.error_code, exc.mensaje) from exc
        except SQLAlchemyError as exc:
            raise APIError(
                503,
                "CANCELACION_NO_DISPONIBLE",
                "No se pudo confirmar la cancelación. Puede reintentar la solicitud.",
            ) from exc


def get_cancelaciones_service(
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    # No compartir la transacción usada para autenticar la solicitud.
    return CancelacionesService(session)
