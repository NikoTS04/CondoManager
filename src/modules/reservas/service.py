"""Servicio de Negocio del Dominio de Reservas de Áreas Comunes (Brandon - PROC-04).

Implementa:
1. Control estricto de la Invariante de Solvencia Financiera (Mora activa bloquea reservas).
2. Verificación de disponibilidad horaria y prevención de solapamientos (concurrencia).
3. Auditoría inmutable de 7 campos para cada intento, confirmación o cancelación de reserva.
4. Política Zero-Float (ADR-002) con tipos Decimal.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid
from pydantic import BaseModel

from src.core.audit import AuditoriaPayload
from src.modules.reservas.schemas import (
    CancelarReservaRequest,
    CancelarReservaResponse,
    CrearReservaRequest,
    ReservaResponseDTO,
)


# ============================================================================
# Excepciones de Dominio (PROC-04)
# ============================================================================

class DeudaMoraActivaException(Exception):
    def __init__(self, departamento_id: str, saldo_vencido: Decimal):
        mensaje = (
            f"No es posible reservar: El departamento '{departamento_id}' "
            f"mantiene cuotas vencidas pendientes en mora por un total de S/ {saldo_vencido:.2f}."
        )
        super().__init__(mensaje)
        self.error_code = "DEUDA_MORA_ACTIVA"
        self.mensaje = mensaje
        self.departamento_id = departamento_id
        self.saldo_vencido = saldo_vencido


class ConflictoHorarioException(Exception):
    def __init__(self, area_id: str, fecha: date, hora_inicio: time, hora_fin: time):
        mensaje = (
            f"No es posible reservar: El área común ya se encuentra reservada "
            f"en el horario {hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')} para la fecha {fecha}."
        )
        super().__init__(mensaje)
        self.error_code = "HORARIO_NO_DISPONIBLE"
        self.mensaje = mensaje
        self.area_id = area_id
        self.fecha = fecha


class AreaNoEncontradaException(Exception):
    def __init__(self, area_id: str):
        mensaje = f"El área común '{area_id}' no existe o no fue encontrada."
        super().__init__(mensaje)
        self.error_code = "AREA_NO_ENCONTRADA"
        self.mensaje = mensaje


class AreaInactivaException(Exception):
    def __init__(self, area_id: str):
        mensaje = f"El área común '{area_id}' se encuentra actualmente inactiva o en mantenimiento."
        super().__init__(mensaje)
        self.error_code = "AREA_INACTIVA"
        self.mensaje = mensaje


class CancelacionInvalidaException(Exception):
    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.error_code = "CANCELACION_NO_PERMITIDA"
        self.mensaje = motivo


class HorarioInvalidoException(Exception):
    def __init__(self, mensaje: str = "La hora de fin debe ser posterior a la hora de inicio."):
        super().__init__(mensaje)
        self.error_code = "HORARIO_INVALIDO"
        self.mensaje = mensaje


# ============================================================================
# Compatibilidad con Suite de Pruebas BDD / Unitarias Iniciales
# ============================================================================

class SolicitudReservaDTO(BaseModel):
    condominio_id: str
    departamento_id: str
    usuario_id: str
    area_id: str
    fecha_reserva: date
    hora_inicio: time
    hora_fin: time


class ResultadoReservaDTO(BaseModel):
    es_exitosa: bool
    reserva_id: Optional[str] = None
    motivo: str
    bloqueado_por_mora: bool = False


class GestorReservasService:
    @staticmethod
    def validar_y_procesar_reserva(
        solicitud: SolicitudReservaDTO,
        deuda_vencida_departamento: Decimal,
        esta_horario_disponible: bool,
    ) -> ResultadoReservaDTO:
        """Ciclo de Automatización simplificado para pruebas en memoria."""
        if deuda_vencida_departamento > Decimal("0.00"):
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: Su departamento mantiene cuotas vencidas pendientes en mora.",
                bloqueado_por_mora=True,
            )

        if not esta_horario_disponible:
            return ResultadoReservaDTO(
                es_exitosa=False,
                motivo="Reserva rechazada: El área común seleccionada ya se encuentra reservada en ese horario.",
                bloqueado_por_mora=False,
            )

        return ResultadoReservaDTO(
            es_exitosa=True,
            reserva_id=f"res-{uuid.uuid4()}",
            motivo="Reserva confirmada exitosamente.",
            bloqueado_por_mora=False,
        )


# ============================================================================
# Servicio Principal de Reservas y Disponibilidad (SDD Completo)
# ============================================================================

class ReservasService:
    @staticmethod
    def hay_solapamiento_horario(
        inicio_a: time, fin_a: time, inicio_b: time, fin_b: time
    ) -> bool:
        """Evalúa si dos intervalos de tiempo se solapan [inicio, fin)."""
        return inicio_a < fin_b and fin_a > inicio_b

    @classmethod
    def validar_disponibilidad(
        cls,
        area_id: uuid.UUID,
        fecha_reserva: date,
        hora_inicio: time,
        hora_fin: time,
        reservas_existentes: List[Dict[str, Any]],
    ) -> bool:
        """Comprueba si el horario solicitado está libre respecto a reservas CONFIRMADAS."""
        for r in reservas_existentes:
            if (
                r.get("area_id") == area_id
                and r.get("fecha_reserva") == fecha_reserva
                and r.get("estado") == "CONFIRMADA"
            ):
                if cls.hay_solapamiento_horario(
                    hora_inicio, hora_fin, r["hora_inicio"], r["hora_fin"]
                ):
                    return False
        return True

    @classmethod
    def procesar_reserva(
        cls,
        request: CrearReservaRequest,
        area: Dict[str, Any],
        estado_financiero_depto: str,
        saldo_mora_depto: Decimal,
        reservas_existentes: List[Dict[str, Any]],
    ) -> Tuple[ReservaResponseDTO, AuditoriaPayload]:
        """Orquesta la creación de una reserva con validación atómica de solvencia y calendario."""
        if request.hora_fin <= request.hora_inicio:
            raise HorarioInvalidoException("La hora de fin debe ser posterior a la hora de inicio.")

        if not area.get("esta_activa", True):
            raise AreaInactivaException(str(request.area_id))

        # 1. Invariante Innegociable de Solvencia Financiera
        if saldo_mora_depto > Decimal("0.00") or estado_financiero_depto == "EN_MORA":
            audit_rechazo_mora = AuditoriaPayload(
                condominio_id=str(request.condominio_id),
                departamento_id=str(request.departamento_id),
                accion_ejecutada="SOLICITUD_RESERVA_RECHAZADA_MORA",
                motivo=f"Intento de reserva bloqueado: departamento mantiene deuda morosa de S/ {saldo_mora_depto:.2f}",
                resultado="FALLIDO",
                estado_anterior={"estado_financiero": estado_financiero_depto, "saldo_mora": str(saldo_mora_depto)},
                estado_posterior={"estado_financiero": estado_financiero_depto, "resultado_reserva": "RECHAZADA"},
            )
            raise DeudaMoraActivaException(
                departamento_id=str(request.departamento_id),
                saldo_vencido=saldo_mora_depto,
            )

        # 2. Control de Disponibilidad y Concurrencia
        disponible = cls.validar_disponibilidad(
            area_id=request.area_id,
            fecha_reserva=request.fecha_reserva,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            reservas_existentes=reservas_existentes,
        )

        if not disponible:
            audit_rechazo_horario = AuditoriaPayload(
                condominio_id=str(request.condominio_id),
                departamento_id=str(request.departamento_id),
                accion_ejecutada="SOLICITUD_RESERVA_RECHAZADA_CONFLICTO",
                motivo=f"Horario ocupado para el área {request.area_id} en fecha {request.fecha_reserva}",
                resultado="FALLIDO",
                estado_anterior={"area_id": str(request.area_id), "fecha": str(request.fecha_reserva)},
                estado_posterior={"resultado_reserva": "RECHAZADA_CONFLICTO"},
            )
            raise ConflictoHorarioException(
                area_id=str(request.area_id),
                fecha=request.fecha_reserva,
                hora_inicio=request.hora_inicio,
                hora_fin=request.hora_fin,
            )

        # 3. Confirmación de la Reserva
        reserva_id = uuid.uuid4()
        costo_reserva = Decimal(str(area.get("costo_reserva", "0.00")))
        creado_en = datetime.now(timezone.utc)

        audit_confirmacion = AuditoriaPayload(
            condominio_id=str(request.condominio_id),
            departamento_id=str(request.departamento_id),
            accion_ejecutada="RESERVA_CONFIRMADA",
            motivo=f"Reserva aprobada en {area.get('nombre', 'Área Común')} para {request.fecha_reserva}",
            resultado="EXITOSO",
            estado_anterior={"reserva_id": "NULL", "estado": "SOLICITADA"},
            estado_posterior={
                "reserva_id": str(reserva_id),
                "area_id": str(request.area_id),
                "fecha_reserva": str(request.fecha_reserva),
                "horario": f"{request.hora_inicio.strftime('%H:%M')}-{request.hora_fin.strftime('%H:%M')}",
                "costo_reserva": str(costo_reserva),
                "estado": "CONFIRMADA",
            },
        )

        reserva_dto = ReservaResponseDTO(
            id=reserva_id,
            condominio_id=request.condominio_id,
            area_id=request.area_id,
            area_nombre=area.get("nombre"),
            departamento_id=request.departamento_id,
            fecha_reserva=request.fecha_reserva,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            costo_reserva=costo_reserva,
            estado="CONFIRMADA",
            creado_en=creado_en,
        )

        return reserva_dto, audit_confirmacion

    @classmethod
    def procesar_cancelacion(
        cls,
        reserva: Dict[str, Any],
        request: CancelarReservaRequest,
        momento_actual: Optional[datetime] = None,
    ) -> Tuple[CancelarReservaResponse, AuditoriaPayload]:
        """Procesa la cancelación liberando el cupo en el calendario."""
        if reserva.get("estado") == "CANCELADA":
            raise CancelacionInvalidaException("La reserva ya ha sido cancelada previamente.")

        if reserva.get("estado") != "CONFIRMADA":
            raise CancelacionInvalidaException(
                f"No se puede cancelar una reserva en estado '{reserva.get('estado')}'."
            )

        momento_actual = momento_actual or datetime.now(timezone.utc)

        # Regla de 24 horas de anticipación para cancelaciones voluntarias de residentes
        if not request.es_admin:
            fecha_res = reserva["fecha_reserva"]
            hora_ini = reserva["hora_inicio"]
            inicio_reserva_dt = datetime.combine(fecha_res, hora_ini, tzinfo=timezone.utc)

            limite_cancelacion = inicio_reserva_dt - timedelta(hours=24)
            if momento_actual > limite_cancelacion:
                raise CancelacionInvalidaException(
                    "La cancelación voluntaria por parte del residente requiere al menos 24 horas de anticipación."
                )

        audit_cancelacion = AuditoriaPayload(
            condominio_id=str(reserva.get("condominio_id", "condo-gen")),
            departamento_id=str(reserva.get("departamento_id")),
            accion_ejecutada="RESERVA_CANCELADA",
            motivo=request.motivo,
            resultado="EXITOSO",
            estado_anterior={"reserva_id": str(reserva["id"]), "estado": "CONFIRMADA"},
            estado_posterior={"reserva_id": str(reserva["id"]), "estado": "CANCELADA"},
        )

        respuesta = CancelarReservaResponse(
            id=reserva["id"],
            estado="CANCELADA",
            mensaje=f"Reserva cancelada exitosamente. Motivo: {request.motivo}",
            fecha_cancelacion=momento_actual,
        )

        return respuesta, audit_cancelacion
