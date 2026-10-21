"""Dobles explícitos para contratos de identidad; no prueban persistencia ni carreras SQL."""

from datetime import time

from src.core.authorization import autorizar_departamento, contexto_consulta, puede_ver_departamento
from src.core.errors import APIError
from src.modules.reservas.areas.service import AreasService
from src.modules.reservas.schemas import CancelarReservaRequest, ReservaResponseDTO
from src.modules.reservas.service import ReservasService

RESERVAS_REGISTRADAS = {}
NOTIFICACIONES_REGISTRADAS = {}


class ReservasContrato:
    def __init__(self, areas, finanzas):
        self.areas = AreasService(areas)
        self.finanzas = finanzas

    async def listar(self, usuario, cid=None, area_id=None, fecha=None):
        cid = contexto_consulta(usuario, cid)
        if area_id:
            await self.areas.verificar_historial(area_id, usuario)
        return [
            ReservaResponseDTO(**r)
            for r in RESERVAS_REGISTRADAS.values()
            if r["condominio_id"] == cid
            and puede_ver_departamento(usuario, r["departamento_id"])
            and (not area_id or r["area_id"] == area_id)
            and (not fecha or r["fecha_reserva"] == fecha)
        ]

    async def disponibilidad(self, aid, fecha, usuario):
        await self.areas.publica(aid, usuario)
        return [
            {"hora_inicio": r["hora_inicio"].isoformat(), "hora_fin": r["hora_fin"].isoformat()}
            for r in RESERVAS_REGISTRADAS.values()
            if r["area_id"] == aid and r["fecha_reserva"] == fecha and r["estado"] == "CONFIRMADA"
        ]

    async def crear(self, request, usuario):
        autorizar_departamento(
            usuario, request.departamento_id, request.condominio_id, escritura=True
        )
        async with self.finanzas.para_reserva(request, usuario) as evaluacion:
            area = (
                await self.areas.publica(
                    request.area_id, usuario, bloquear=True, condominio_id=request.condominio_id
                )
            ).model_dump()
            area["hora_apertura"] = time.fromisoformat(area["hora_apertura"])
            area["hora_cierre"] = time.fromisoformat(area["hora_cierre"])
            dto, _ = ReservasService.procesar_reserva(
                request,
                area,
                "AL_DIA",
                evaluacion.saldo_vencido,
                list(RESERVAS_REGISTRADAS.values()),
            )
            RESERVAS_REGISTRADAS[dto.id] = dto.model_dump()
            return dto

    async def cancelar(self, rid, request, usuario):
        r = RESERVAS_REGISTRADAS.get(rid)
        if r is None:
            raise APIError(404, "RESERVA_NO_ENCONTRADA", "No existe la reserva.")
        autorizar_departamento(usuario, r["departamento_id"], r["condominio_id"], escritura=True)
        req = (request or CancelarReservaRequest()).model_copy(
            update={"es_admin": usuario["rol"] in {"SUPERADMIN", "ADMIN_JUNTA"}}
        )
        dto, _ = ReservasService.procesar_cancelacion(r, req)
        r["estado"] = "CANCELADA"
        return dto


class NotificacionesContrato:
    async def comunicado(self, request, usuario):
        cid = contexto_consulta(usuario, request.condominio_id)
        # Este doble de contrato no configura destinatarios; la aceptación SQL los comprueba.
        return {"condominio_id": str(cid), "generadas": 0, "estado_general": "EN_COLA"}

    async def listar(self, usuario, cid=None, did=None, estado=None, canal=None):
        cid = contexto_consulta(usuario, cid)
        return [
            n
            for n in NOTIFICACIONES_REGISTRADAS.values()
            if n.condominio_id == str(cid) and (did is None or n.departamento_id == str(did))
        ]

    async def despachar(self, request, usuario):
        from src.core.authorization import autorizar_condominio
        from src.modules.notificaciones.schemas import NotificacionLogDTO

        autorizar_condominio(usuario, request.condominio_id, escritura=True)
        log = NotificacionLogDTO(
            **request.model_dump(exclude={"contexto"}), cuerpo="Aviso de contrato"
        )
        NOTIFICACIONES_REGISTRADAS[log.id] = log
        return log

    async def reenviar(self, id, request, usuario):
        from src.core.authorization import autorizar_condominio

        log = NOTIFICACIONES_REGISTRADAS[id]
        autorizar_condominio(usuario, log.condominio_id, escritura=True)
        return log
