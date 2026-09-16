# Criterios de Aceptación: Notificaciones y Comunicaciones (BDD / Gherkin)

## Característica: Envío Automático y Resiliencia de Notificaciones

### Escenario 1: Envío de recordatorio preventivo previo al vencimiento
```gherkin
Dado que el departamento 204 tiene una cuota que vence en 3 días
Y no se ha recibido el pago correspondiente
Cuando el planificador de tareas se ejecuta a las 08:00 horas
Entonces el sistema genera una notificación de tipo "NOTIF_RECORDATORIO_PREVIO"
Y despacha el correo electrónico al propietario y al inquilino registrado
Y almacena el registro con estado "ENTREGADO" en la tabla "notificaciones_logs".
```

### Escenario 2: Notificación inmediata de conciliación exitosa de pago
```gherkin
Dado que el administrador aprueba el comprobante de pago del departamento 105
Cuando la transacción de base de datos se confirma
Entonces se dispara el evento "PagoConciliadoEvent"
Y el módulo de notificaciones envía un mensaje de confirmación al residente adjuntando el nuevo estado de cuenta con saldo cero.
```

### Escenario 3: Política de reintento automático ante caída de servicio externo
```gherkin
Dado que el sistema intenta enviar un correo de alerta de mora al departamento 601
Y el servidor de correo responde con error 503 "Service Unavailable"
Cuando el worker detecta el fallo
Entonces el estado de la notificación cambia a "REINTENTANDO" con contador de intentos = 1
Y el sistema programa el segundo intento para dentro de 2 minutos
Y si el servicio no se restablece tras 4 intentos, el estado pasa a "FALLIDO_PERMANENTE" y genera una alerta en la campana del Administrador.
```
