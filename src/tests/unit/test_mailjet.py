import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest
from pydantic import SecretStr

from src.core.config import settings
from src.modules.notificaciones import mailjet


@pytest.fixture
def preparado(monkeypatch):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", True)
    monkeypatch.setattr(settings, "MAILJET_API_KEY", SecretStr("api-prueba"))
    monkeypatch.setattr(settings, "MAILJET_SECRET", SecretStr("secreto-prueba"))
    monkeypatch.setattr(settings, "MAILJET_FROM_EMAIL", "verificado@example.test")
    return SimpleNamespace(
        canal="EMAIL", destinatario="destino@example.test", asunto="Prueba", cuerpo="Contenido privado",
    )


def test_deshabilitado_no_contacta_proveedor(monkeypatch, preparado):
    monkeypatch.setattr(settings, "MAILJET_ENABLED", False)
    monkeypatch.setattr(mailjet, "build_opener", lambda *a: pytest.fail("No debe contactar Mailjet"))
    assert mailjet.transporte_mailjet(preparado, "clave")["status"] == 503


def test_aceptacion_y_secreto_solo_en_cabecera(monkeypatch, preparado):
    solicitudes = []
    class Transporte:
        def open(self, request, **kwargs):
            solicitudes.append(request)
            return io.BytesIO(json.dumps({"Messages": [{"Status": "success", "To": [{"MessageID": 123}]}]}).encode())
    monkeypatch.setattr(mailjet, "build_opener", lambda *a: Transporte())
    assert mailjet.transporte_mailjet(preparado, "intento-1") == {"status": 200, "message_id": "123"}
    req = solicitudes[0]
    assert req.full_url == "https://api.mailjet.com/v3.1/send"
    assert req.get_header("Authorization").startswith("Basic ")
    mensaje = json.loads(req.data)["Messages"][0]
    assert mensaje["TextPart"] == preparado.cuerpo and mensaje["CustomID"] == "intento-1"
    assert "secreto-prueba" not in req.full_url and b"secreto-prueba" not in req.data


@pytest.mark.parametrize("codigo", [400, 401, 403, 429, 500, 408, 302])
def test_rechazo_o_aceptacion_incierta(monkeypatch, preparado, codigo):
    class Transporte:
        def open(self, *args, **kwargs):
            raise HTTPError("https://secreto", codigo, "no divulgar", {}, None)
    monkeypatch.setattr(mailjet, "build_opener", lambda *a: Transporte())
    resultado = mailjet.transporte_mailjet(preparado, "clave")
    assert resultado.get("incierto", False) is (codigo in (500, 408, 302))
    assert "no divulgar" not in str(resultado)


def test_timeout_no_acredita_envio(monkeypatch, preparado):
    class Transporte:
        def open(self, *args, **kwargs):
            raise URLError("aceptación desconocida")
    monkeypatch.setattr(mailjet, "build_opener", lambda *a: Transporte())
    assert mailjet.transporte_mailjet(preparado, "clave")["incierto"] is True


@pytest.mark.parametrize("datos", [
    None, [], {"Messages": []},
    {"Messages": [{"Status": "success", "To": [{"MessageID": 0}]}]},
    {"Messages": [{"Status": "success", "To": [{"MessageID": True}]}]},
    {"Messages": [{"Status": "error", "Errors": [{"ErrorMessage": "privado"}]}]},
])
def test_respuesta_invalida_no_acredita_envio(monkeypatch, preparado, datos):
    class Transporte:
        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps(datos).encode())
    monkeypatch.setattr(mailjet, "build_opener", lambda *a: Transporte())
    resultado = mailjet.transporte_mailjet(preparado, "clave")
    assert resultado["incierto"] is True and "privado" not in str(resultado)
