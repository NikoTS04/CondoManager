"""CON-73: reserva, auditoría y outbox en la transacción financiera de CON-42."""

from datetime import UTC, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import select

from src.core.authorization import autorizar_departamento, contexto_consulta
from src.core.errors import APIError
from src.core.roles import ROLES_ADMINISTRATIVOS
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.reservas.areas.repository import AreasRepository
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.models import EventoReservaOutbox, Reserva
from src.modules.reservas.repository import ReservasRepository
from src.modules.reservas.schemas import (
    CancelarReservaRequest,
    CancelarReservaResponse,
    ReservaResponseDTO,
)
from src.modules.reservas.service import ConflictoHorarioException, ReservasService


class ReservasPersistentesService:
    def __init__(self, solvencia):
        self.solvencia = solvencia
        self.session = solvencia.session
        self.repo = ReservasRepository(self.session)
        self.areas = AreasService(AreasRepository(self.session))

    async def listar(self, usuario, cid=None, area_id=None, fecha=None):
        cid = contexto_consulta(usuario, cid)
        async with self.session.begin():
            if area_id:
                await self.areas.verificar_historial(area_id, usuario)
            return [
                ReservaResponseDTO.model_validate(r)
                for r in await self.repo.listar(cid, usuario, area_id, fecha)
            ]

    async def disponibilidad(self, area_id, fecha, usuario):
        async with self.session.begin():
            area = await self.areas.publica(area_id, usuario)
            if fecha < datetime.now(ZoneInfo("America/Lima")).date():
                raise APIError(422, "FECHA_RESERVA_INVALIDA", "Seleccione hoy o una fecha futura.")
            zona = ZoneInfo("America/Lima")
            apertura = datetime.combine(fecha, time.fromisoformat(area.hora_apertura), zona)
            cierre = datetime.combine(fecha, time.fromisoformat(area.hora_cierre), zona)
            tramos = sorted(
                (max(a.astimezone(zona), apertura), min(b.astimezone(zona), cierre))
                for a, b in await self.repo.ocupaciones(area_id, fecha)
                if a < cierre and b > apertura
            )
            fusionados = []
            for inicio, fin in tramos:
                if fusionados and inicio <= fusionados[-1][1]:
                    fusionados[-1] = (fusionados[-1][0], max(fin, fusionados[-1][1]))
                else:
                    fusionados.append((inicio, fin))
            return [
                {"hora_inicio": a.strftime("%H:%M:00"), "hora_fin": b.strftime("%H:%M:00")}
                for a, b in fusionados
            ]

    async def crear(self, request, usuario):
        autorizar_departamento(
            usuario, request.departamento_id, request.condominio_id, escritura=True
        )
        async with self.solvencia.para_reserva(request, usuario) as evaluacion:
            area = await self.areas.publica(
                request.area_id,
                usuario,
                bloquear=True,
                condominio_id=request.condominio_id,
            )
            depto = await self.solvencia.repo.departamento(request.departamento_id, usuario)
            if area.edificio_id is not None and area.edificio_id != depto[0].edificio_id:
                raise APIError(
                    403, "ACCESO_DENEGADO", "La unidad no pertenece al edificio del área."
                )
            datos_area = area.model_dump()
            datos_area["hora_apertura"] = time.fromisoformat(area.hora_apertura)
            datos_area["hora_cierre"] = time.fromisoformat(area.hora_cierre)
            dto, audit = ReservasService.procesar_reserva(
                request,
                datos_area,
                "AL_DIA",
                evaluacion.saldo_vencido,
                [],
            )
            inicio = datetime.combine(
                request.fecha_reserva, request.hora_inicio, ZoneInfo("America/Lima")
            )
            fin = datetime.combine(
                request.fecha_reserva, request.hora_fin, ZoneInfo("America/Lima")
            )
            if inicio <= datetime.now(UTC):
                raise APIError(422, "FECHA_RESERVA_INVALIDA", "El inicio debe estar en el futuro.")
            if any(
                inicio < b and fin > a
                for a, b in await self.repo.ocupaciones(area.id, request.fecha_reserva)
            ):
                raise ConflictoHorarioException(
                    str(area.id), request.fecha_reserva, request.hora_inicio, request.hora_fin
                )
            reserva = Reserva(
                **dto.model_dump(),
                usuario_id=UUID(usuario["sub"]),
            )
            self.session.add(reserva)
            await self.session.flush()
            await self.solvencia.repo.auditar(
                usuario,
                request.condominio_id,
                request.departamento_id,
                audit.accion_ejecutada,
                audit.motivo,
                audit.estado_anterior,
                audit.estado_posterior,
            )
            self.evento(reserva, "ReservaConfirmadaEvent", area.nombre)
            await self.session.flush()
        return dto

    @staticmethod
    def cancelada(reserva):
        if reserva.fecha_cancelacion is None:
            raise APIError(
                409,
                "CANCELACION_HISTORICA_SIN_FECHA",
                "La cancelación histórica no tiene fecha verificable.",
            )
        return CancelarReservaResponse(
            id=reserva.id,
            fecha_cancelacion=reserva.fecha_cancelacion,
            mensaje=f"Reserva cancelada exitosamente. Motivo: {reserva.motivo_cancelacion}",
        )

    async def cancelar(self, rid, request, usuario, ahora=None):
        async with self.session.begin():
            reserva = await self.session.get(Reserva, rid)
            if reserva is None:
                raise APIError(404, "RESERVA_NO_ENCONTRADA", "No existe la reserva.")
            await self.solvencia.repo.departamento(
                reserva.departamento_id, usuario, escritura=True, bloquear=True
            )
            await self.areas.repo.validar_actor(usuario)
            await self.areas.repo.area(reserva.condominio_id, reserva.area_id, bloquear=True)
            reserva = await self.session.scalar(
                select(Reserva)
                .where(Reserva.id == rid)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if reserva.estado == "CANCELADA":
                return self.cancelada(reserva)
            req = (request or CancelarReservaRequest()).model_copy(
                update={"es_admin": usuario["rol"] in ROLES_ADMINISTRATIVOS},
            )
            datos = {
                k: getattr(reserva, k)
                for k in (
                    "id",
                    "condominio_id",
                    "departamento_id",
                    "estado",
                    "fecha_reserva",
                    "hora_inicio",
                    "zona_horaria",
                )
            }
            if reserva.estado != "CONFIRMADA":
                raise APIError(422, "ESTADO_RESERVA_INVALIDO", "La reserva no admite cancelación.")
            respuesta, audit = ReservasService.procesar_cancelacion(datos, req, ahora)
            reserva.estado = "CANCELADA"
            reserva.fecha_cancelacion = respuesta.fecha_cancelacion
            reserva.cancelado_por = UUID(usuario["sub"])
            reserva.motivo_cancelacion = req.motivo
            await self.solvencia.repo.auditar(
                usuario,
                reserva.condominio_id,
                reserva.departamento_id,
                audit.accion_ejecutada,
                audit.motivo,
                audit.estado_anterior,
                audit.estado_posterior,
            )
            self.evento(reserva, "ReservaCanceladaEvent")
            await self.session.flush()
        return respuesta

    def evento(self, reserva, tipo, area_nombre=None):
        eid = uuid4()
        ahora = datetime.now(UTC)
        data = {
            k: str(getattr(reserva, k))
            for k in (
                "condominio_id",
                "departamento_id",
                "area_id",
                "fecha_reserva",
                "hora_inicio",
                "hora_fin",
                "zona_horaria",
            )
        }
        data["reserva_id"] = str(reserva.id)
        if tipo == "ReservaConfirmadaEvent":
            data.update(
                area_nombre=area_nombre,
                costo_reserva=f"{reserva.costo_reserva:.2f}",
                moneda=reserva.moneda,
            )
        else:
            data.update(
                fecha_cancelacion=reserva.fecha_cancelacion.isoformat(),
                motivo=reserva.motivo_cancelacion,
                ajuste_economico=self.cancelada(reserva).ajuste_economico.model_dump(mode="json"),
            )
        self.session.add(
            EventoReservaOutbox(
                id=eid,
                reserva_id=reserva.id,
                tipo=tipo,
                creado_en=ahora,
                payload={
                    "event_id": str(eid),
                    "event_type": tipo,
                    "schema_version": 1,
                    "producer": "service.reservas",
                    "occurred_at": ahora.isoformat(),
                    "correlation_id": str(eid),
                    "causation_id": None,
                    "data": data,
                },
            )
        )


def get_reservas_service(solvencia=Depends(get_solvencia_service)):
    return ReservasPersistentesService(solvencia)
