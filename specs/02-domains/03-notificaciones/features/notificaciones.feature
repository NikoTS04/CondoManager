# language: es
Característica: Orquestación y despacho de notificaciones multicanal
  Como residente del condominio
  Quiero recibir avisos oportunos sobre mis cuotas, pagos y estados
  Para estar siempre al día y evitar penalidades de mora

  Escenario: Envío automático de confirmación de pago validado
    Dado que el residente del departamento "105" tiene registrado el correo "residente105@gmail.com"
    Cuando la junta directiva aprueba el comprobante de pago del departamento "105"
    Entonces el despachador de notificaciones envía un correo con asunto "CondoManager: Su pago ha sido validado con éxito"
    Y el registro en "notificaciones_logs" queda en estado "ENTREGADO" con intentos igual a 1

  Escenario: Reintento automático tras caída temporal del servidor de correo
    Dado que el sistema intenta despachar un aviso de mora al departamento "601"
    Y el servidor SMTP responde con error temporal 503 "Service Unavailable"
    Cuando el worker de tareas asíncronas detecta el fallo
    Entonces el estado de la notificación cambia a "REINTENTANDO"
    Y se programa un segundo intento para dentro de 2 minutos
    Y el contador de intentos se incrementa a 2

  Scenario: Un recordatorio de una cuota pagada antes del despacho no se envía
    Given un recordatorio de vencimiento en cola para una cuota con saldo
    When la cuota queda pagada antes de que el worker lo despache
    Then el recordatorio queda OMITIDO por falta de deuda sin intento de transporte ni alerta

  Scenario: Un pago en curso hace esperar al despacho del recordatorio
    Given un recordatorio en cola y un pago de la cuota aún sin confirmar
    When el worker intenta despacharlo
    Then espera a la confirmación del pago y relee el saldo antes de decidir
