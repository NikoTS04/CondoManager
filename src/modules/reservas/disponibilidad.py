"""Lectura y normalización del calendario de CON-40, sin modificar reservas."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import APIError
from src.modules.reservas.schemas import HorarioOcupado

ZONA_LIMA = timezone(timedelta(hours=-5), name="America/Lima")


class DisponibilidadRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def reservas_confirmadas(self, area_id: UUID, condominio_id: UUID, fecha: date):
        # Incluye estados históricos para descartar copias piloto obsoletas.
        # El servicio selecciona únicamente CONFIRMADA para ocupar el calendario.
        try:
            return await self._leer_reservas(area_id, condominio_id, fecha)
        except SQLAlchemyError as exc:
            raise APIError(
                503,
                "DISPONIBILIDAD_NO_DISPONIBLE",
                "No se pudo consultar el calendario. Intente nuevamente más tarde.",
            ) from exc

    async def _leer_reservas(self, area_id: UUID, condominio_id: UUID, fecha: date):
        # CON-39 puede ejecutarse antes de que CON-73 cree/adopte reservas.
        # Solo la ausencia de la tabla permite continuar con el almacén piloto;
        # un fallo SQL se propaga y nunca se presenta como calendario vacío.
        if not await self.session.scalar(text("SELECT to_regclass('reservas') IS NOT NULL")):
            return []

        resultado = await self.session.execute(
            text(
                """
                SELECT r.id, r.fecha_reserva, r.hora_inicio, r.hora_fin, r.estado,
                       COALESCE(to_jsonb(r)->>'zona_horaria', 'UTC') AS zona_horaria
                FROM reservas r
                JOIN areas_comunes a ON a.id = r.area_id
                WHERE a.id = :area_id AND a.condominio_id = :condominio_id
                  AND r.fecha_reserva BETWEEN :fecha AND :fecha_hasta
                """
            ),
            {
                "area_id": area_id,
                "condominio_id": condominio_id,
                "fecha": fecha,
                # Un horario UTC de mañana puede pertenecer al día local consultado.
                "fecha_hasta": fecha + timedelta(days=1) if fecha < date.max else fecha,
            },
        )
        return [dict(fila) for fila in resultado.mappings()]


class DisponibilidadService:
    @staticmethod
    def combinar_fuentes(persistidas, piloto):
        ids_sql = {str(r["id"]) for r in persistidas}
        return [r for r in persistidas if r.get("estado", "CONFIRMADA") == "CONFIRMADA"] + [
            r for r in piloto if r["estado"] == "CONFIRMADA" and str(r["id"]) not in ids_sql
        ]

    @staticmethod
    def validar_fecha(fecha: date) -> None:
        if fecha < datetime.now(ZONA_LIMA).date():
            raise APIError(
                422, "FECHA_RESERVA_INVALIDA", "Seleccione hoy o una fecha futura en hora de Lima."
            )

    @staticmethod
    def horarios_ocupados(
        fecha: date, ocupaciones, apertura: str, cierre: str
    ) -> list[HorarioOcupado]:
        """Recibe ocupaciones activas; CON-73 puede sumar bloqueos al mismo formato.

        Cada ocupación contiene fecha_reserva, hora_inicio, hora_fin y zona_horaria.
        La ausencia histórica de zona significa UTC. La respuesta solo contiene horas.
        """
        desde = datetime.combine(fecha, time.fromisoformat(apertura), ZONA_LIMA)
        hasta = datetime.combine(fecha, time.fromisoformat(cierre), ZONA_LIMA)
        intervalos = []
        for ocupacion in ocupaciones:
            nombre_zona = ocupacion.get("zona_horaria") or "UTC"
            if nombre_zona not in {"America/Lima", "UTC"}:
                raise APIError(
                    503,
                    "DISPONIBILIDAD_NO_DISPONIBLE",
                    "No se pudo interpretar el calendario. Intente consultar nuevamente más tarde.",
                )
            zona = ZONA_LIMA if nombre_zona == "America/Lima" else timezone.utc
            inicio = datetime.combine(
                ocupacion["fecha_reserva"], ocupacion["hora_inicio"], zona
            ).astimezone(ZONA_LIMA)
            fin = datetime.combine(
                ocupacion["fecha_reserva"], ocupacion["hora_fin"], zona
            ).astimezone(ZONA_LIMA)
            inicio, fin = max(inicio, desde), min(fin, hasta)
            if inicio >= fin:
                continue
            # Conserva la ocupación si un registro histórico tiene segundos.
            inicio = inicio.replace(second=0, microsecond=0)
            if fin.second or fin.microsecond:
                fin = fin.replace(second=0, microsecond=0) + timedelta(minutes=1)
            intervalos.append((inicio, fin))

        fusionados = []
        for inicio, fin in sorted(intervalos):
            if fusionados and inicio < fusionados[-1][1]:
                fusionados[-1] = (fusionados[-1][0], max(fin, fusionados[-1][1]))
            else:
                fusionados.append((inicio, fin))
        return [
            HorarioOcupado(
                hora_inicio=inicio.strftime("%H:%M:00"), hora_fin=fin.strftime("%H:%M:00")
            )
            for inicio, fin in fusionados
        ]
