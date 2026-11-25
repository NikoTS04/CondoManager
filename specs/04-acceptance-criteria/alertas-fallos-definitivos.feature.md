# CON-84 — Alertas de fallos definitivos con referencia al origen

- **Correo agotado.** Dado un correo cuyo cuarto intento falla, cuando el worker lo marca
  `FALLIDO_PERMANENTE`, entonces existe una sola alerta `INTENTOS_AGOTADOS` con
  `origen_tipo = CORREO` y `origen_id` igual al id de la notificación.
- **Sin alerta mientras haya reintentos.** Dado un correo con fallo temporal en su primer
  intento, cuando queda `REINTENTANDO`, entonces no se crea alerta.
- **Deduplicación de correo.** Dado un correo con alerta `ERROR_DEFINITIVO`, cuando el
  callback del proveedor se repite o el worker vuelve a registrar el fallo del mismo ciclo,
  entonces sigue habiendo una sola alerta; un nuevo ciclo manual que falla crea otra.
- **Job agotado.** Dado el job `diario` que falla con `intentos >= maximo_intentos`, cuando se
  registra el fallo, entonces se crea una alerta `JOB_FALLO_DEFINITIVO` con
  `origen_tipo = JOB`, `origen_id = diario`, sin condominio y con un mensaje sin trazas.
- **Job con reintentos pendientes.** Dado un job que falla con `intentos < maximo_intentos`,
  cuando se registra el fallo, entonces no se crea alerta.
- **Idempotencia de job.** Dado un fallo de job ya alertado, cuando se registra de nuevo el
  mismo job, ciclo y tipo, entonces se conserva una sola alerta, aunque se registre en
  paralelo.
- **Referencia de correlación.** Dado un fallo registrado con referencia, cuando se consulta la
  alerta, entonces devuelve esa referencia; sin referencia devuelve `null`.
- **Aislamiento.** Dadas alertas de dos condominios y una de job, cuando la Junta de un
  condominio consulta `GET /api/v1/notificaciones/alertas`, entonces solo ve las de su
  condominio y nunca la de job ni las ajenas.
- **Cron.** Dado el endpoint `/jobs/diario` o `/jobs/notificaciones` que termina con error,
  cuando responde 503 `JOB_INCOMPLETO`, entonces queda la alerta del job y la respuesta no
  revela la causa interna.
