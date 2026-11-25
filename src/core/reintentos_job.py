"""Registro de procesos automáticos que pueden repetirse sin riesgo (CON-86).

CON-85 podrá ampliar este conjunto cuando cada job exponga su propio control
de idempotencia. El job `diario` queda fuera hasta entonces: solo ejecuta
informes y no tiene una ejecución reproducible por lotes.
"""

JOBES_REINTENTABLES = frozenset({"notificaciones"})


def puede_reintentar_job(nombre: str) -> bool:
    return nombre in JOBES_REINTENTABLES
