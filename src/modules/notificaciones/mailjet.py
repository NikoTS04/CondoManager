"""Adapter preparado, desactivado por defecto; no acredita entrega física."""

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.core.config import settings


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transporte_mailjet(log, clave):
    if not settings.MAILJET_ENABLED:
        return {"status": 503, "error": "MAILJET_DESHABILITADO"}
    if log.canal != "EMAIL":
        return {"status": 400, "error": "CANAL_NO_SOPORTADO"}
    credencial = base64.b64encode(
        (settings.MAILJET_API_KEY.get_secret_value() + ":" +
         settings.MAILJET_SECRET.get_secret_value()).encode()
    ).decode()
    payload = {"Messages": [{
        "From": {"Email": settings.MAILJET_FROM_EMAIL},
        "To": [{"Email": log.destinatario}],
        "Subject": log.asunto or "",
        "TextPart": log.cuerpo,
        # Mailjet CustomID es correlación, no garantía de idempotencia.
        "CustomID": clave,
    }]}
    request = Request(
        "https://api.mailjet.com/v3.1/send",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Basic {credencial}", "Content-Type": "application/json"},
        method="POST",
    )
    incierto = {"status": 0, "error": "ACEPTACION_INCIERTA", "incierto": True}
    try:
        with build_opener(SinRedireccion()).open(request, timeout=15) as response:
            datos = response.read(65537)
            if len(datos) > 65536:
                return incierto
            mensaje = json.loads(datos)["Messages"][0]
            if mensaje["Status"] != "success":
                return incierto
            message_id = mensaje["To"][0]["MessageID"]
            if not message_id:
                return incierto
            return {"status": 200, "message_id": str(message_id)}
    except HTTPError as exc:
        if 400 <= exc.code < 500 and exc.code != 408:
            return {"status": exc.code, "error": "MAILJET_RECHAZO"}
        return incierto
    except (URLError, OSError, ValueError, KeyError, IndexError, TypeError):
        return incierto
