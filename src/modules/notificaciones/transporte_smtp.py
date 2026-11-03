"""CON-78: transporte SMTP real con errores normalizados y aceptación incierta.

El adaptador solo acredita aceptación del servidor (`ENVIADO`). SMTP no informa la
entrega final al buzón; `ENTREGADO` requiere evidencia posterior del proveedor.

Contrato de resultado (mismo que `transporte_simulado`):
- `{"status": 200, "message_id": ...}`: el servidor aceptó el mensaje (250 tras DATA).
- `{"status": 550, "error": "550"}`: el servidor rechazó definitivamente el destinatario.
- `{"status": 422, "error": "FALLO_DEFINITIVO"}`: contenido rechazado de forma definitiva.
- `{"status": 503, "error": "FALLO_TEMPORAL"}`: el mensaje no llegó a enviarse; se reintenta.
- `{"status": 0, "error": "ACEPTACION_INCIERTA", "incierto": True}`: el contenido se
  transmitió pero no se conoce la respuesta. No se reenvía automáticamente.

Los errores nunca incluyen textos del servidor: pueden repetir direcciones o credenciales.
"""

import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, parseaddr

TEMPORAL = {"status": 503, "error": "FALLO_TEMPORAL"}
INCIERTO = {"status": 0, "error": "ACEPTACION_INCIERTA", "incierto": True}
SEGURIDADES = ("STARTTLS", "SSL", "NINGUNA")


@dataclass(frozen=True)
class ConfigSMTP:
    host: str
    port: int
    remitente: str
    usuario: str = ""
    password: str = ""
    seguridad: str = "STARTTLS"
    timeout: float = 15.0
    nombre_remitente: str = "CondoManager"

    @property
    def dominio(self):
        return parseaddr(self.remitente)[1].rpartition("@")[2] or "condomanager.local"

    @classmethod
    def desde_settings(cls, settings):
        """Devuelve None si el proveedor no está completo; no se inventan valores."""
        if settings.EMAIL_TRANSPORTE != "SMTP":
            return None
        if not settings.SMTP_HOST or not settings.SMTP_REMITENTE:
            return None
        if settings.SMTP_SEGURIDAD not in SEGURIDADES:
            return None
        if bool(settings.SMTP_USUARIO) != bool(settings.SMTP_PASSWORD):
            return None
        return cls(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            remitente=settings.SMTP_REMITENTE,
            usuario=settings.SMTP_USUARIO,
            password=settings.SMTP_PASSWORD,
            seguridad=settings.SMTP_SEGURIDAD,
            timeout=settings.SMTP_TIMEOUT_SEGUNDOS,
            nombre_remitente=settings.SMTP_NOMBRE_REMITENTE,
        )


def message_id(clave, dominio):
    """Identificador estable por intento: permite reconciliar con los registros del proveedor."""
    return f"<{clave}@{dominio}>"


def construir_mensaje(config, log, clave):
    msg = EmailMessage()
    msg["From"] = formataddr((config.nombre_remitente, config.remitente))
    msg["To"] = log.destinatario
    msg["Subject"] = log.asunto or "CondoManager"
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = message_id(clave, config.dominio)
    msg["X-CondoManager-Notificacion"] = clave
    # Mensajes del sistema: los servidores no deben contestar con respuestas automáticas.
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(log.cuerpo)
    return msg


class TransporteSMTP:
    """Callable `(log, clave) -> resultado`, ejecutado por el worker fuera de locks SQL."""

    def __init__(self, config, smtp_factory=None, ssl_context=None):
        self.config = config
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.smtp_factory = smtp_factory or self._conexion

    def _conexion(self):
        c = self.config
        if c.seguridad == "SSL":
            return smtplib.SMTP_SSL(c.host, c.port, timeout=c.timeout, context=self.ssl_context)
        return smtplib.SMTP(c.host, c.port, timeout=c.timeout)

    def __call__(self, log, clave):
        msg = construir_mensaje(self.config, log, clave)
        try:
            smtp = self.smtp_factory()
        except (OSError, smtplib.SMTPException):
            return dict(TEMPORAL)
        try:
            return self._enviar(smtp, msg)
        finally:
            try:
                smtp.quit()
            except (OSError, smtplib.SMTPException):
                smtp.close()

    def _enviar(self, smtp, msg):
        c = self.config
        # Fase segura: nada se transmitió aún, cualquier fallo permite reintentar.
        try:
            smtp.ehlo()
            if c.seguridad == "STARTTLS":
                smtp.starttls(context=self.ssl_context)
                smtp.ehlo()
            if c.usuario:
                smtp.login(c.usuario, c.password)
            codigo, _ = smtp.mail(c.remitente)
            if codigo != 250:
                return dict(TEMPORAL)
            codigo, _ = smtp.rcpt(msg["To"])
            if codigo not in (250, 251):
                if 500 <= codigo < 600:
                    return {"status": 550, "error": "550"}
                return dict(TEMPORAL)
        except (OSError, smtplib.SMTPException):
            # Conexión, TLS, autenticación o remitente: problema del proveedor o su
            # configuración. Se reintenta y, si persiste, se alerta INTENTOS_AGOTADOS.
            return dict(TEMPORAL)
        # Fase de datos. `data()` lanza SMTPDataError solo si el servidor rechaza el
        # comando DATA, antes de transmitir el contenido: es una respuesta conocida.
        # Una desconexión o timeout posterior deja la aceptación sin confirmar.
        try:
            codigo, _ = smtp.data(msg.as_bytes())
        except smtplib.SMTPDataError as exc:
            return _rechazo_data(exc.smtp_code)
        except (OSError, socket.timeout, smtplib.SMTPException):
            return dict(INCIERTO)
        if codigo != 250:
            return _rechazo_data(codigo)
        return {"status": 200, "message_id": msg["Message-ID"]}


def _rechazo_data(codigo):
    if 500 <= codigo < 600:
        return {"status": 422, "error": "FALLO_DEFINITIVO"}
    if 400 <= codigo < 500:
        return dict(TEMPORAL)
    return dict(INCIERTO)


def transporte_proveedor(settings):
    """Transporte configurado por entorno o None si el proveedor no está completo."""
    config = ConfigSMTP.desde_settings(settings)
    return TransporteSMTP(config) if config else None
