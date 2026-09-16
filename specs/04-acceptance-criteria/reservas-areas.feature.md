# Criterios de Aceptación: Reservas de Áreas Comunes (BDD / Gherkin)

## Característica: Reserva de Áreas Comunes y Control de Solvencia

### Escenario 1: Bloqueo de reserva para departamento con deuda en mora
```gherkin
Dado que el departamento 501 tiene una deuda vencida en estado "EN_MORA"
Cuando el residente del departamento 501 intenta reservar la "Zona de Parrilla 1" para el 25 de octubre de 19:00 a 22:00
Entonces el sistema rechaza la solicitud de forma inmediata
Y retorna el mensaje de error "No es posible reservar: Su departamento mantiene cuotas vencidas pendientes"
Y el estado de la franja horaria en la parrilla permanece "DISPONIBLE" para otros vecinos.
```

### Escenario 2: Aprobación de reserva para departamento al día en sus pagos
```gherkin
Dado que el departamento 102 no tiene deudas pendientes y está al día
Y la "Sala de Eventos" se encuentra disponible el 15 de noviembre de 16:00 a 20:00
Cuando el residente del departamento 102 solicita la reserva de dicho espacio
Entonces el sistema bloquea inmediatamente el horario
Y la reserva cambia al estado "CONFIRMADA"
Y se envía un correo de confirmación con las normas de convivencia del área al residente.
```

### Escenario 3: Desbloqueo automático de reservas tras cancelar la deuda
```gherkin
Dado que el departamento 302 estaba bloqueado por mora
Cuando el tesorero aprueba en la bandeja de conciliación el pago que salda el 100% de la deuda del departamento 302
Entonces el estado financiero del departamento 302 se actualiza a "AL_DIA"
Y el residente queda automáticamente habilitado para realizar reservas de áreas comunes sin requerir llamada o intervención manual adicional.
```

### Escenario 4: Detección y prevención de colisión de horarios (Concurrencia)
```gherkin
Dado que la "Zona de Parrilla 1" está libre para el día sábado de 13:00 a 17:00
Cuando el residente del dpto 201 y el residente del dpto 304 envían la solicitud de reserva en el mismo milisegundo
Entonces el sistema otorga la reserva a la primera solicitud procesada por la transacción de base de datos
Y la segunda solicitud es rechazada de manera controlada con el mensaje "El horario seleccionado acaba de ser reservado por otro residente".
```
