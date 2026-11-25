# CON-66 — Bandeja de excepciones de Junta

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
