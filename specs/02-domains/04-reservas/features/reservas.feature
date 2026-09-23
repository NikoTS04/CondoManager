# language: es
Característica: Gestión de reservas de áreas comunes y control de solvencia
  Como residente del condominio
  Quiero consultar disponibilidad y reservar áreas comunes
  Para disfrutar de los espacios compartidos respetando las normas de convivencia

  Escenario: Rechazo automático de reserva para departamento con deuda en mora
    Dado que el departamento "501" mantiene una cuota vencida en estado "EN_MORA"
    Cuando el residente del departamento "501" intenta reservar la "Zona de Parrilla 1" para el "2026-10-25" de "19:00" a "22:00"
    Entonces el sistema deniega la reserva con código de error "DEUDA_MORA_ACTIVA"
    Y el calendario de disponibilidad del área permanece inalterado para otros residentes

  Escenario: Reserva exitosa de área común para residente solvente
    Dado que el departamento "102" se encuentra al día y sin deudas vencidas
    Y la "Sala de Eventos" se encuentra disponible para el "2026-11-15" de "16:00" a "20:00"
    Cuando el residente del departamento "102" solicita la reserva de dicho espacio
    Entonces la reserva queda registrada en estado "CONFIRMADA"
    Y se envía un correo de confirmación con las normas de uso del espacio

  Escenario: Prevención de conflicto por concurrencia simultánea
    Dado que la "Zona de Parrilla 1" está disponible para el "2026-10-31" de "13:00" a "17:00"
    Cuando dos residentes solventes envían solicitudes de reserva concurrentes sobre el mismo espacio y horario
    Entonces la primera solicitud en confirmar la transacción es aprobada
    Y la segunda solicitud es rechazada de forma controlada con error "HORARIO_NO_DISPONIBLE"
