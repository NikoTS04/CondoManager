# CON-66 — Bandeja de excepciones operativas

- Dado un fallo definitivo de correo, cuando Junta abre la bandeja, entonces
  ve el origen, la causa, la prioridad, el estado y la evidencia del caso.
  Otro condominio y un residente quedan fuera de alcance.
- Dado un fallo abierto, cuando Junta cierra con motivo, entonces el aviso
  queda omitido y el historial conserva al actor, la fecha y el efecto.
- Dado un contacto corregido y autorizado, cuando Junta pide un reenvío y
  repite la solicitud, entonces se inicia un solo ciclo. El caso queda en
  proceso hasta que exista un resultado de envío.
- Dado un envío cuya aceptación es incierta, cuando Junta consulta el caso,
  entonces lo revisa mediante el flujo existente de correo.
- Dado un fallo de un job global, cuando SuperAdmin abre la bandeja, entonces
  ve el detalle. Junta no puede consultarlo ni actuar sobre él.
- Dado un fallo del job de notificaciones habilitado, cuando SuperAdmin
  reintenta y repite la solicitud, entonces el programador toma un único
  intento. El resultado queda ligado al caso y se registra como incierto
  si la ejecución anterior quedó interrumpida.
- Dado un job abierto, cuando SuperAdmin solicita información con motivo y
  responsable, entonces aparece pendiente y conserva la solicitud en el historial.
