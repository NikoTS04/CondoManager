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

## CON-86 — Persistencia y resolución trazable

- Dado un fallo de correo, cuando se abre o resuelve, entonces el caso se
  persiste con evidencia del proceso de origen, su ciclo y su referencia de
  correlación, y el historial conserva actor, motivo, clave y efecto real.
- Dado un `JOB_FALLO_DEFINITIVO`, cuando `SUPERADMIN` abre la bandeja, entonces
  ve el componente, la operación y la referencia de diagnóstico; Junta no ve
  ese caso y un residente tampoco.
- Dado un fallo del job de notificaciones habilitado, cuando `SUPERADMIN`
  solicita un reintento y repite la clave, entonces el próximo ciclo consume
  una sola solicitud. El caso muestra el resultado real y registra un intento
  como incierto si la ejecución anterior quedó interrumpida.
- Dado el job `diario` (no registrado como seguro), cuando se consultan sus
  acciones, entonces puede cerrarse o quedar pendiente de información y se
  rechaza un reintento.
- Dado un job abierto, cuando SuperAdmin solicita información con motivo y
  responsable, entonces aparece pendiente y conserva la solicitud en el historial.
- Dado un caso con fallo definitivo de correo, cuando se corrige el contacto y
  se reenvía, entonces se guarda el nuevo ciclo y la bandeja distingue
  `ENVIADO` de `ENTREGADO` hasta tener confirmación.
