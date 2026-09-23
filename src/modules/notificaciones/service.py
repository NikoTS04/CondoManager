"""Servicio de Negocio del Dominio de Notificaciones (Alejandro - PROC-03).

Implementa:
1. Orquestación y despacho multicanal (Email / WhatsApp).
2. Renderizado dinámico de plantillas contextualizadas.
3. Política de resiliencia con backoff exponencial (+2m, +10m, +30m).
4. Detección inmediata de hard bounces (550 User unknown / 131026 Undeliverable).
5. Bitácora auditable de envíos (`notificaciones_logs`).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from src.modules.notificaciones.schemas import (
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EnviarComunicadoMasivoRequest,
    EnviarComunicadoMasivoResponse,
    EstadoNotificacionEnum,
    NotificacionLogDTO,
)
from src.modules.notificaciones.templates import PlantillasService

# Matriz de espera exponencial según delivery-policy.md
# Intento 1: Inmediato
# Intento 2: +2 min (120 s)
# Intento 3: +10 min (600 s)
# Intento 4: +30 min (1800 s)
INTERVALOS_REINTENTO_SEGUNDOS = {
    1: 120,    # Para pasar a intento 2
    2: 600,    # Para pasar a intento 3
    3: 1800,   # Para pasar a intento 4
}

# Códigos de error definitivo (Hard Bounces) que abortan inmediatamente los reintentos
ERRORES_DEFINITIVOS = {"550", "131026", "INVALID_EMAIL", "MAILBOX_NOT_FOUND", "USER_UNKNOWN"}


def mock_transport_default(
    destinatario: str, canal: CanalNotificacionEnum, asunto: Optional[str], cuerpo: str
) -> Dict[str, Any]:
    """Transporte simulado por defecto para pruebas y entorno local."""
    return {
        "status": 200,
        "message_id": f"mock-msg-{uuid.uuid4()}",
        "error": None,
    }


class NotificacionesService:
    @staticmethod
    def es_error_definitivo(status_code: int, error_mensaje: str) -> bool:
        """Determina si el error retornado por el transporte es un fallo permanente sin posibilidad de reintento."""
        str_code = str(status_code)
        if str_code in ERRORES_DEFINITIVOS:
            return True
        for err_key in ERRORES_DEFINITIVOS:
            if err_key in error_mensaje.upper():
                return True
        return False

    @classmethod
    def procesar_fallo(
        cls,
        log: NotificacionLogDTO,
        status_code: int,
        error_mensaje: str,
        momento_actual: Optional[datetime] = None,
    ) -> NotificacionLogDTO:
        """Aplica la política de entrega (specs/02-domains/03-notificaciones/delivery-policy.md)."""
        momento_actual = momento_actual or datetime.now(timezone.utc)
        log.fecha_actualizacion = momento_actual
        log.error_mensaje = f"[{status_code}] {error_mensaje}"

        # Caso 1: Error definitivo (Hard bounce) -> FALLIDO_PERMANENTE inmediato sin reintentos
        if cls.es_error_definitivo(status_code, error_mensaje):
            log.estado = EstadoNotificacionEnum.FALLIDO_PERMANENTE
            log.proximo_reintento = None
            return log

        # Caso 2: Error temporal -> Evaluar si quedan intentos en la matriz exponencial
        if log.intentos < 4:
            segundos_espera = INTERVALOS_REINTENTO_SEGUNDOS.get(log.intentos, 120)
            log.estado = EstadoNotificacionEnum.REINTENTANDO
            log.intentos += 1
            log.proximo_reintento = momento_actual + timedelta(seconds=segundos_espera)
        else:
            # Cuarto intento fallido -> Se agota la cuota de reintentos
            log.estado = EstadoNotificacionEnum.FALLIDO_PERMANENTE
            log.proximo_reintento = None

        return log

    @classmethod
    def despachar_notificacion(
        cls,
        request: DespacharNotificacionRequest,
        transport_fn: Optional[Callable] = None,
        momento_actual: Optional[datetime] = None,
    ) -> NotificacionLogDTO:
        """Orquesta el renderizado y el primer intento de envío de una notificación."""
        momento_actual = momento_actual or datetime.now(timezone.utc)
        transport = transport_fn or mock_transport_default

        # 1. Renderizado de plantilla
        asunto, cuerpo = PlantillasService.renderizar(
            tipo_evento=request.tipo_evento, contexto=request.contexto
        )

        # 2. Creación inicial del log en estado EN_COLA
        log = NotificacionLogDTO(
            id=uuid.uuid4(),
            condominio_id=request.condominio_id,
            departamento_id=request.departamento_id,
            tipo_evento=request.tipo_evento,
            canal=request.canal,
            destinatario=request.destinatario,
            asunto=asunto,
            cuerpo=cuerpo,
            estado=EstadoNotificacionEnum.EN_COLA,
            intentos=1,
            fecha_creacion=momento_actual,
            fecha_actualizacion=momento_actual,
        )

        # 3. Despacho por el transporte
        try:
            resultado = transport(
                request.destinatario,
                request.canal,
                asunto,
                cuerpo,
            )
            status_code = resultado.get("status", 200)

            if status_code == 200:
                log.estado = EstadoNotificacionEnum.ENTREGADO
                log.proveedor_message_id = resultado.get("message_id")
                log.error_mensaje = None
                log.proximo_reintento = None
            else:
                error_msg = resultado.get("error", "Error no especificado por transporte")
                cls.procesar_fallo(log, status_code, error_msg, momento_actual)

        except Exception as exc:
            cls.procesar_fallo(log, 500, f"Excepción de transporte: {str(exc)}", momento_actual)

        return log

    @classmethod
    def reenviar_notificacion_manual(
        cls,
        log: NotificacionLogDTO,
        nuevo_destinatario: Optional[str] = None,
        transport_fn: Optional[Callable] = None,
        momento_actual: Optional[datetime] = None,
    ) -> NotificacionLogDTO:
        """Permite a la Junta Directiva rectificar los datos y reintentar un envío fallido."""
        momento_actual = momento_actual or datetime.now(timezone.utc)
        transport = transport_fn or mock_transport_default

        if nuevo_destinatario:
            log.destinatario = nuevo_destinatario

        log.intentos = 1
        log.fecha_actualizacion = momento_actual

        try:
            resultado = transport(
                log.destinatario,
                log.canal,
                log.asunto,
                log.cuerpo,
            )
            status_code = resultado.get("status", 200)

            if status_code == 200:
                log.estado = EstadoNotificacionEnum.ENTREGADO
                log.proveedor_message_id = resultado.get("message_id")
                log.error_mensaje = None
                log.proximo_reintento = None
            else:
                cls.procesar_fallo(
                    log, status_code, resultado.get("error", "Fallo al reenviar"), momento_actual
                )
        except Exception as exc:
            cls.procesar_fallo(log, 500, str(exc), momento_actual)

        return log

    @classmethod
    def despachar_comunicado_masivo(
        cls,
        request: EnviarComunicadoMasivoRequest,
        departamentos: List[Dict[str, Any]],
        transport_fn: Optional[Callable] = None,
    ) -> Tuple[EnviarComunicadoMasivoResponse, List[NotificacionLogDTO]]:
        """Genera y despacha un comunicado general para toda la comunidad de departamentos."""
        logs_generados: List[NotificacionLogDTO] = []

        for dpto in departamentos:
            numero = dpto.get("numero", "000")
            destinatario = dpto.get("email_contacto", f"residente{numero}@condominio.pe")

            req_indiv = DespacharNotificacionRequest(
                condominio_id=request.condominio_id,
                departamento_id=str(numero),
                tipo_evento="NOTIF_COMUNICADO_GENERAL",
                canal=request.canal,
                destinatario=destinatario,
                contexto={
                    "titulo": request.titulo,
                    "mensaje": request.mensaje,
                    "remitente": request.remitente,
                },
            )

            log = cls.despachar_notificacion(req_indiv, transport_fn=transport_fn)
            logs_generados.append(log)

        respuesta = EnviarComunicadoMasivoResponse(
            condominio_id=request.condominio_id,
            total_destinatarios=len(departamentos),
            notificaciones_generadas=len(logs_generados),
            estado_general="ENTREGADO" if all(l.estado == EstadoNotificacionEnum.ENTREGADO for l in logs_generados) else "REINTENTANDO",
        )

        return respuesta, logs_generados
