# language: es
# Verificado por src/tests/integration/test_recordatorio_revalidacion_db.py (PostgreSQL).
Característica: Revalidación del recordatorio al despachar (CON-33)

  Escenario: Un recordatorio de una cuota pagada antes del despacho no se envía
    Dado un recordatorio de vencimiento en cola para una cuota con saldo
    Cuando la cuota queda pagada antes de que el worker lo despache
    Entonces el recordatorio queda OMITIDO por falta de deuda sin intento de transporte ni alerta

  Escenario: Un pago en curso hace esperar al despacho del recordatorio
    Dado un recordatorio en cola y un pago de la cuota aún sin confirmar
    Cuando el worker intenta despacharlo
    Entonces espera a la confirmación del pago y relee el saldo antes de decidir
