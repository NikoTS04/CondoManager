"""Calendario peruano independiente de la zona horaria del servidor."""

from datetime import datetime
from zoneinfo import ZoneInfo


def fecha_lima():
    return datetime.now(ZoneInfo("America/Lima")).date()
