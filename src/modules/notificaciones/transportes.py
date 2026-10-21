"""Adaptadores de transporte y clasificación de errores para notificaciones (CON-37).

Define el protocolo `TransporteNotificacion`, el resultado tipado `ResultadoTransporte`,
la clasificación entre fallos temporales y definitivos (`delivery-policy.md`), el
`TransporteSimulado` (por defecto, explícitamente identificado con `es_simulado=True`)
y el `TransporteSMTP` basado en `smtplib` ejecutado en hilo.
"""

import asyncio
import re
import smtplib
import uuid
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any, Protocol, runtime_checkable

from src.core.config import settings

CODIGOS_TEMPORALES = frozenset(
    {
        "429",
        "500",
        "502",
        "503",
        "504",
        "TIMEOUT",
        "CONNECTION_ERROR",
        "NETWORK_ERROR",
        "TEMPORAL",
    }
)

CODIGOS_DEFINITIVOS = frozenset(
    {
        "550",
        "131026",
        "DESTINATARIO_INVALIDO",
        "INVALID_RECIPIENT",
        "INVALID_EMAIL",
        "MAILBOX_NOT_FOUND",
        "USER_UNKNOWN",
    }
)

PALABRAS_DEFINITIVAS = (
    "550",
    "131026",
    "USER UNKNOWN",
    "USER_UNKNOWN",
    "MAILBOX DOES NOT EXIST",
    "MAILBOX_NOT_FOUND",
    "INVALID_EMAIL",
    "INVALID_RECIPIENT",
    "DESTINATARIO_INVALIDO",
    "DESTINATARIO INVALIDO",
    "UNDELIVERABLE",
)

PALABRAS_TEMPORALES = (
    "TIMEOUT",
    "TIMED OUT",
    "CONNECTION",
    "SERVICE UNAVAILABLE",
    "TOO MANY REQUESTS",
    "BAD GATEWAY",
    "GATEWAY TIMEOUT",
)


def validar_destinatario(destinatario: str | None, canal: str = "EMAIL") -> bool:
    """Valida sintácticamente el destinatario según el canal."""
    if not destinatario or not isinstance(destinatario, str):
        return False
    limpio = destinatario.strip()
    if not limpio or " " in limpio:
        return False
    if canal.upper() == "EMAIL":
        partes = limpio.split("@")
        if len(partes) != 2:
            return False
        local, dominio = partes
        if not local or not dominio or "." not in dominio or dominio.startswith("."):
            return False
        if dominio.endswith("."):
            return False
    return True


def clasificar_fallo(codigo: str | int | None, detalle: str | None = None) -> str:
    """Clasifica un error de transporte en `FALLO_TEMPORAL` o `FALLO_DEFINITIVO`."""
    codigo_str = str(codigo).strip().upper() if codigo is not None else ""
    detalle_upper = (detalle or "").upper()

    if codigo_str in CODIGOS_DEFINITIVOS:
        return "FALLO_DEFINITIVO"
    if codigo_str in CODIGOS_TEMPORALES:
        return "FALLO_TEMPORAL"

    if codigo_str.isdigit():
        num = int(codigo_str)
        if 400 <= num < 500 and num != 429:
            return "FALLO_DEFINITIVO"
        if num == 550:
            return "FALLO_DEFINITIVO"
        if 500 <= num < 600:
            return "FALLO_TEMPORAL"

    for palabra in PALABRAS_DEFINITIVAS:
        if palabra in detalle_upper:
            return "FALLO_DEFINITIVO"

    for palabra in PALABRAS_TEMPORALES:
        if palabra in detalle_upper:
            return "FALLO_TEMPORAL"

    return "FALLO_TEMPORAL"


def es_error_definitivo(codigo: str | int | None, detalle: str | None = None) -> bool:
    """Retorna True si el error corresponde a un fallo permanente sin reintento."""
    return clasificar_fallo(codigo, detalle) == "FALLO_DEFINITIVO"


def es_error_temporal(codigo: str | int | None, detalle: str | None = None) -> bool:
    """Retorna True si el error es transitorio y admite backoff exponencial."""
    return clasificar_fallo(codigo, detalle) == "FALLO_TEMPORAL"


@dataclass(frozen=True)
class ResultadoTransporte:
    """Resultado tipado devuelto por cualquier implementación de `TransporteNotificacion`."""

    aceptado: bool
    proveedor_message_id: str | None = None
    codigo: str | None = None
    detalle: str | None = None
    confirmar_entrega_inmediata: bool = False

    @classmethod
    def ok(
        cls,
        message_id: str | None = None,
        *,
        confirmar_entrega: bool = False,
    ) -> "ResultadoTransporte":
        return cls(
            aceptado=True,
            proveedor_message_id=message_id or f"sim-{uuid.uuid4()}",
            codigo="200",
            detalle=None,
            confirmar_entrega_inmediata=confirmar_entrega,
        )

    @classmethod
    def exito(
        cls,
        message_id: str | None = None,
        *,
        confirmar_entrega: bool = False,
    ) -> "ResultadoTransporte":
        return cls.ok(message_id=message_id, confirmar_entrega=confirmar_entrega)

    @classmethod
    def fallo(cls, codigo: str | int, detalle: str) -> "ResultadoTransporte":
        return cls(
            aceptado=False,
            proveedor_message_id=None,
            codigo=str(codigo),
            detalle=detalle,
            confirmar_entrega_inmediata=False,
        )

    @property
    def es_definitivo(self) -> bool:
        if self.aceptado:
            return False
        return es_error_definitivo(self.codigo, self.detalle)

    @property
    def resultado_intento(self) -> str:
        if self.aceptado:
            return "ACEPTADO"
        return clasificar_fallo(self.codigo, self.detalle)


@dataclass(frozen=True)
class EnvioSimulado:
    """Evidencia en memoria de una llamada al transporte simulado durante pruebas."""

    notificacion_id: uuid.UUID | None
    destinatario: str
    canal: str
    asunto: str | None
    cuerpo: str
    resultado: ResultadoTransporte


@runtime_checkable
class TransporteNotificacion(Protocol):
    """Contrato común para los adaptadores de envío de notificaciones."""

    nombre: str
    es_simulado: bool

    async def enviar(self, notificacion: Any) -> ResultadoTransporte: ...


class TransporteSimulado:
    """Transporte simulado configurable e identificado con `es_simulado = True`."""

    nombre: str = "SIMULADO"
    es_simulado: bool = True

    def __init__(
        self,
        *,
        respuestas: Sequence[ResultadoTransporte | Exception] | None = None,
        por_destinatario: (
            dict[str, Sequence[ResultadoTransporte | Exception] | ResultadoTransporte | Exception]
            | None
        ) = None,
        handler: (
            Callable[[Any], ResultadoTransporte | Awaitable[ResultadoTransporte]] | None
        ) = None,
        confirmar_entrega: bool = False,
        latencia_segundos: float = 0.0,
    ) -> None:
        self._cola: deque[ResultadoTransporte | Exception] = deque(respuestas or ())
        self._por_destinatario: dict[str, deque[ResultadoTransporte | Exception]] = {}
        self._permanente_destinatario: dict[str, ResultadoTransporte | Exception] = {}
        if por_destinatario:
            for patron, valor in por_destinatario.items():
                if isinstance(valor, (ResultadoTransporte, Exception)):
                    self._permanente_destinatario[patron] = valor
                else:
                    self._por_destinatario[patron] = deque(valor)
        self._handler = handler
        self.confirmar_entrega = confirmar_entrega
        self.latencia_segundos = latencia_segundos
        self.envios: list[EnvioSimulado] = []

    @property
    def total_llamadas(self) -> int:
        return len(self.envios)

    def llamadas_para(self, notificacion_id: uuid.UUID) -> int:
        return sum(1 for envio in self.envios if envio.notificacion_id == notificacion_id)

    def programar_fallo(
        self,
        codigo: str | int,
        detalle: str,
        *,
        destinatario: str | None = None,
        veces: int = 1,
    ) -> None:
        item = ResultadoTransporte.fallo(codigo, detalle)
        if destinatario is not None:
            cola = self._por_destinatario.setdefault(destinatario, deque())
            for _ in range(max(1, veces)):
                cola.append(item)
        else:
            for _ in range(max(1, veces)):
                self._cola.append(item)

    def programar_exito(
        self,
        message_id: str | None = None,
        *,
        destinatario: str | None = None,
        confirmar_entrega: bool | None = None,
    ) -> None:
        confirmar = self.confirmar_entrega if confirmar_entrega is None else confirmar_entrega
        item = ResultadoTransporte.ok(message_id=message_id, confirmar_entrega=confirmar)
        if destinatario is not None:
            cola = self._por_destinatario.setdefault(destinatario, deque())
            cola.append(item)
        else:
            self._cola.append(item)

    def _resolver_item_destinatario(
        self, destinatario: str
    ) -> ResultadoTransporte | Exception | None:
        if destinatario in self._por_destinatario and self._por_destinatario[destinatario]:
            return self._por_destinatario[destinatario].popleft()
        if destinatario in self._permanente_destinatario:
            return self._permanente_destinatario[destinatario]
        for patron, cola in self._por_destinatario.items():
            if patron in destinatario and cola:
                return cola.popleft()
        for patron, fijo in self._permanente_destinatario.items():
            if patron in destinatario:
                return fijo
        return None

    async def enviar(self, notificacion: Any) -> ResultadoTransporte:
        if self.latencia_segundos > 0:
            await asyncio.sleep(self.latencia_segundos)

        notif_id = getattr(notificacion, "id", None)
        destinatario = getattr(notificacion, "destinatario", "") or ""
        canal = getattr(notificacion, "canal", "EMAIL") or "EMAIL"
        asunto = getattr(notificacion, "asunto", None)
        cuerpo = getattr(notificacion, "cuerpo", "") or ""

        if self._handler is not None:
            posible = self._handler(notificacion)
            resultado = await posible if inspect_isawaitable(posible) else posible
            self.envios.append(
                EnvioSimulado(notif_id, destinatario, canal, asunto, cuerpo, resultado)
            )
            return resultado

        item = self._resolver_item_destinatario(destinatario)
        if item is None and self._cola:
            item = self._cola.popleft()

        if isinstance(item, Exception):
            codigo_exc = "TIMEOUT" if isinstance(item, TimeoutError) else "CONNECTION_ERROR"
            resultado = ResultadoTransporte.fallo(codigo_exc, str(item))
            self.envios.append(
                EnvioSimulado(notif_id, destinatario, canal, asunto, cuerpo, resultado)
            )
            raise item

        if isinstance(item, ResultadoTransporte):
            self.envios.append(
                EnvioSimulado(notif_id, destinatario, canal, asunto, cuerpo, item)
            )
            return item

        if not validar_destinatario(destinatario, canal):
            invalido = ResultadoTransporte.fallo(
                "DESTINATARIO_INVALIDO",
                "Formato de destinatario inválido para el canal seleccionado.",
            )
            self.envios.append(
                EnvioSimulado(notif_id, destinatario, canal, asunto, cuerpo, invalido)
            )
            return invalido

        exito = ResultadoTransporte.ok(
            message_id=f"sim-{uuid.uuid4()}",
            confirmar_entrega=self.confirmar_entrega,
        )
        self.envios.append(EnvioSimulado(notif_id, destinatario, canal, asunto, cuerpo, exito))
        return exito


def inspect_isawaitable(valor: Any) -> bool:
    return hasattr(valor, "__await__")


class TransporteSMTP:
    """Transporte SMTP real basado en `smtplib` ejecutado en hilo."""

    nombre: str = "SMTP"
    es_simulado: bool = False

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        remitente: str | None = None,
        use_tls: bool | None = None,
        timeout: int | None = None,
    ) -> None:
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.user = user if user is not None else settings.SMTP_USER
        self.password = password if password is not None else settings.SMTP_PASSWORD
        self.remitente = remitente or settings.SMTP_FROM
        self.use_tls = settings.SMTP_USE_TLS if use_tls is None else use_tls
        self.timeout = timeout or settings.SMTP_TIMEOUT_SEGUNDOS

    def _enviar_sincrono(
        self, destinatario: str, asunto: str, cuerpo: str, msg_id: str
    ) -> ResultadoTransporte:
        if not validar_destinatario(destinatario, "EMAIL"):
            return ResultadoTransporte.fallo(
                "DESTINATARIO_INVALIDO", "Dirección de correo electrónico inválida."
            )
        msg = EmailMessage()
        msg["Message-ID"] = msg_id
        msg["From"] = self.remitente
        msg["To"] = destinatario
        msg["Subject"] = asunto or "Notificación CondoManager"
        msg.set_content(cuerpo)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return ResultadoTransporte.ok(message_id=msg_id.strip("<>"))
        except smtplib.SMTPRecipientsRefused as exc:
            errores = list(exc.recipients.values())
            codigo = str(errores[0][0]) if errores else "550"
            detalle = (
                errores[0][1].decode("utf-8", errors="replace")
                if errores and isinstance(errores[0][1], bytes)
                else "Destinatario rechazado por el servidor SMTP."
            )
            return ResultadoTransporte.fallo(codigo, detalle)
        except smtplib.SMTPResponseException as exc:
            codigo_num = exc.smtp_code
            # En SMTP los códigos 4xx (421, 450, 451, 452) son transitorios; se normalizan a 503.
            codigo_norm = "503" if 400 <= codigo_num < 500 else str(codigo_num)
            detalle = (
                exc.smtp_error.decode("utf-8", errors="replace")
                if isinstance(exc.smtp_error, bytes)
                else str(exc.smtp_error)
            )
            return ResultadoTransporte.fallo(codigo_norm, detalle)
        except TimeoutError as exc:
            return ResultadoTransporte.fallo("TIMEOUT", f"Tiempo de espera agotado: {exc}")
        except (OSError, smtplib.SMTPException) as exc:
            return ResultadoTransporte.fallo("CONNECTION_ERROR", f"Error de conexión SMTP: {exc}")

    async def enviar(self, notificacion: Any) -> ResultadoTransporte:
        destinatario = getattr(notificacion, "destinatario", "") or ""
        asunto = getattr(notificacion, "asunto", None) or "Notificación CondoManager"
        cuerpo = getattr(notificacion, "cuerpo", "") or ""
        # Message-ID estable por notificación y ciclo: un reenvío tras una caída del worker
        # se reconoce como el mismo mensaje en el proveedor y en el cliente de correo.
        notif_id = getattr(notificacion, "id", None)
        ciclo = getattr(notificacion, "ciclo", 1)
        msg_id = (
            f"<{notif_id}.{ciclo}@condomanager.pe>"
            if notif_id
            else make_msgid(domain="condomanager.pe")
        )
        return await asyncio.to_thread(
            self._enviar_sincrono, destinatario, asunto, cuerpo, msg_id
        )


_ETIQUETA_FALLOS = re.compile(r"\+falla(\d)@")


def fallo_demostracion(notificacion: Any) -> ResultadoTransporte:
    """Fallos deterministas del transporte simulado para la evidencia de CON-37/CON-75.

    `x+falla2@dominio` responde 503 en los dos primeros intentos del ciclo y luego acepta;
    `x+rebote@dominio` responde 550. Depende de `intentos` persistido, no de memoria,
    de modo que el comportamiento se conserva al reiniciar el worker.
    """
    destinatario = (getattr(notificacion, "destinatario", "") or "").lower()
    if "+rebote@" in destinatario:
        return ResultadoTransporte.fallo("550", "User unknown (simulado)")
    coincidencia = _ETIQUETA_FALLOS.search(destinatario)
    if coincidencia and getattr(notificacion, "intentos", 0) < int(coincidencia.group(1)):
        return ResultadoTransporte.fallo("503", "Service unavailable (simulado)")
    canal = getattr(notificacion, "canal", "EMAIL") or "EMAIL"
    if not validar_destinatario(destinatario, canal):
        return ResultadoTransporte.fallo(
            "DESTINATARIO_INVALIDO", "Formato de destinatario inválido para el canal seleccionado."
        )
    return ResultadoTransporte.ok(message_id=f"sim-{uuid.uuid4()}")


def obtener_transporte() -> TransporteNotificacion:
    """Devuelve el adaptador de transporte según `settings.NOTIFICACIONES_TRANSPORTE`."""
    if settings.NOTIFICACIONES_TRANSPORTE.strip().upper() == "SMTP":
        return TransporteSMTP()
    return TransporteSimulado(handler=fallo_demostracion)
