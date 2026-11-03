"""CON-78: adaptador SMTP con errores normalizados, sin red ni base de datos."""

import smtplib
import socket
from email import message_from_bytes
from types import SimpleNamespace

import pytest

from src.modules.notificaciones.transporte_smtp import ConfigSMTP, TransporteSMTP

CONFIG = ConfigSMTP(
    host="smtp.ejemplo.test",
    port=587,
    remitente="avisos@condo.test",
    usuario="api",
    password="secreto-no-visible",
)
LOG = SimpleNamespace(destinatario="ana@ejemplo.test", asunto="Aviso", cuerpo="Hola Ana")


class SMTPFalso:
    """Registra los comandos y permite fallar en una fase concreta."""

    def __init__(self, *, rcpt=250, mail=250, data=250, falla=None):
        self.respuestas = {"rcpt": rcpt, "mail": mail, "data": data}
        self.falla = falla or {}
        self.comandos = []
        self.enviado = None

    def _paso(self, nombre):
        self.comandos.append(nombre)
        if nombre in self.falla:
            raise self.falla[nombre]

    def ehlo(self):
        self._paso("ehlo")

    def starttls(self, context=None):
        self._paso("starttls")

    def login(self, usuario, password):
        self._paso("login")

    def mail(self, remitente):
        self._paso("mail")
        return self.respuestas["mail"], b""

    def rcpt(self, destino):
        self._paso("rcpt")
        return self.respuestas["rcpt"], b""

    def data(self, contenido):
        self._paso("data")
        self.enviado = contenido
        return self.respuestas["data"], b"2.0.0 queued"

    def quit(self):
        self.comandos.append("quit")

    def close(self):
        self.comandos.append("close")


def transporte(smtp, config=CONFIG):
    return TransporteSMTP(config, smtp_factory=lambda: smtp)


def test_aceptacion_devuelve_message_id_estable_y_cabeceras():
    smtp = SMTPFalso()
    resultado = transporte(smtp)(LOG, "nid-1-1")
    assert resultado == {"status": 200, "message_id": "<nid-1-1@condo.test>"}
    assert smtp.comandos == ["ehlo", "starttls", "ehlo", "login", "mail", "rcpt", "data", "quit"]
    msg = message_from_bytes(smtp.enviado)
    assert msg["To"] == "ana@ejemplo.test"
    assert msg["Message-ID"] == "<nid-1-1@condo.test>"
    assert msg["X-CondoManager-Notificacion"] == "nid-1-1"
    assert msg["Auto-Submitted"] == "auto-generated"
    assert "avisos@condo.test" in msg["From"]


def test_sin_credenciales_ni_tls_no_autentica():
    config = ConfigSMTP(
        host="mailpit", port=1025, remitente="avisos@condo.test", seguridad="NINGUNA"
    )
    smtp = SMTPFalso()
    assert transporte(smtp, config)(LOG, "k")["status"] == 200
    assert "login" not in smtp.comandos and "starttls" not in smtp.comandos


@pytest.mark.parametrize(("codigo", "esperado"), [(550, 550), (553, 550), (450, 503), (452, 503)])
def test_destinatario_rechazado_distingue_definitivo_y_temporal(codigo, esperado):
    smtp = SMTPFalso(rcpt=codigo)
    assert transporte(smtp)(LOG, "k")["status"] == esperado
    assert "data" not in smtp.comandos


@pytest.mark.parametrize(
    "fase",
    [
        ("ehlo", smtplib.SMTPServerDisconnected("x")),
        ("starttls", smtplib.SMTPNotSupportedError("x")),
        ("login", smtplib.SMTPAuthenticationError(535, b"bad")),
        ("mail", socket.timeout("x")),
    ],
)
def test_fallos_antes_de_datos_son_temporales(fase):
    smtp = SMTPFalso(falla=dict([fase]))
    assert transporte(smtp)(LOG, "k") == {"status": 503, "error": "FALLO_TEMPORAL"}


def test_conexion_rechazada_es_temporal():
    def factory():
        raise ConnectionRefusedError()

    assert TransporteSMTP(CONFIG, smtp_factory=factory)(LOG, "k")["status"] == 503


@pytest.mark.parametrize(
    ("codigo", "esperado"), [(554, ("FALLO_DEFINITIVO", 422)), (451, ("FALLO_TEMPORAL", 503))]
)
def test_rechazo_del_comando_data(codigo, esperado):
    smtp = SMTPFalso(falla={"data": smtplib.SMTPDataError(codigo, b"no")})
    resultado = transporte(smtp)(LOG, "k")
    assert (resultado["error"], resultado["status"]) == esperado


@pytest.mark.parametrize(("codigo", "status"), [(552, 422), (421, 503)])
def test_respuesta_tras_contenido(codigo, status):
    assert transporte(SMTPFalso(data=codigo))(LOG, "k")["status"] == status


@pytest.mark.parametrize(
    "error", [socket.timeout("x"), smtplib.SMTPServerDisconnected("x"), ConnectionResetError()]
)
def test_sin_respuesta_tras_contenido_es_aceptacion_incierta(error):
    smtp = SMTPFalso(falla={"data": error})
    resultado = transporte(smtp)(LOG, "k")
    assert resultado == {"status": 0, "error": "ACEPTACION_INCIERTA", "incierto": True}
    assert smtp.comandos[-1] == "quit"


def test_errores_no_exponen_textos_del_servidor_ni_credenciales():
    smtp = SMTPFalso(falla={"login": smtplib.SMTPAuthenticationError(535, b"secreto-no-visible")})
    assert "secreto" not in repr(transporte(smtp)(LOG, "k"))


def ajustes(**cambios):
    base = dict(
        EMAIL_TRANSPORTE="SMTP",
        SMTP_HOST="smtp.ejemplo.test",
        SMTP_PORT=587,
        SMTP_USUARIO="",
        SMTP_PASSWORD="",
        SMTP_SEGURIDAD="STARTTLS",
        SMTP_REMITENTE="avisos@condo.test",
        SMTP_TIMEOUT_SEGUNDOS=10,
        SMTP_NOMBRE_REMITENTE="CondoManager",
    )
    return SimpleNamespace(**{**base, **cambios})


def test_configuracion_completa_crea_proveedor():
    assert ConfigSMTP.desde_settings(ajustes()).host == "smtp.ejemplo.test"


@pytest.mark.parametrize(
    "cambio",
    [
        {"EMAIL_TRANSPORTE": "SIMULADO"},
        {"SMTP_HOST": ""},
        {"SMTP_REMITENTE": ""},
        {"SMTP_USUARIO": "api"},  # usuario sin contraseña
        {"SMTP_SEGURIDAD": "OTRA"},
    ],
)
def test_configuracion_incompleta_no_crea_proveedor(cambio):
    assert ConfigSMTP.desde_settings(ajustes(**cambio)) is None
