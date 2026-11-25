# CON-68 — Vista de salud y alertas visibles

- **Componentes sanos.** Dado un perfil con PostgreSQL y Redis disponibles, cuando el
  SuperAdmin consulta `GET /api/v1/monitoreo/salud`, entonces `api`, `postgresql` y `redis`
  están `ok` y `estado_general` es `ok`.
- **Redis deshabilitado.** Dado un perfil con `REDIS_REQUIRED=false`, cuando se consulta la
  salud, entonces `redis` figura `deshabilitado` y no cuenta como fallo.
- **Correo deshabilitado.** Dado `MAILJET_ENABLED=false`, entonces `correo` figura
  `deshabilitado`.
- **Dependencia caída.** Dado PostgreSQL caído, cuando se consulta la salud, entonces responde
  200 con `postgresql = error`, `estado_general = degradado` y sin URLs, credenciales ni
  mensajes del driver.
- **Último job.** Dado un job `notificaciones` completado, cuando se consulta la salud,
  entonces muestra inicio, fin, `duracion_segundos` y `resultado = COMPLETADO`; un job en curso
  tiene `duracion_segundos` nulo; el job `diario` sin registro figura `SIN_REGISTRO`.
- **Salud solo global.** Dado un ADMIN_JUNTA, AUDITOR o RESIDENTE, cuando consulta la salud,
  entonces recibe 403.
- **Alertas con diagnóstico.** Dada una alerta de correo y una de job, cuando se listan,
  entonces cada una trae `componente`, `operacion` y `referencia_diagnostico` con
  `origen_tipo`, `origen_id` y `referencia_correlacion` (nulo si aún no existe).
- **Job solo para SuperAdmin.** Dada una alerta de job sin condominio, cuando la consulta el
  SuperAdmin entonces aparece; cuando la consulta la Junta o el Auditor, entonces no.
- **Aislamiento.** Dadas alertas de dos condominios, cuando la Junta de uno consulta, entonces
  solo ve las suyas; si pide el `condominio_id` ajeno recibe 403.
- **Auditor y residente.** El AUDITOR consulta en solo lectura su condominio; el RESIDENTE
  recibe 403.
- **Estado y paginación.** Sin `estado` se devuelven las ABIERTAS; `estado=ATENDIDA` devuelve
  las atendidas; `limit` y `offset` acotan la lista.
- **Sin datos sensibles.** Ninguna respuesta incluye contactos, trazas, URLs ni credenciales.
