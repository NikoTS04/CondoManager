# CON-50 — Alertas contractuales de 60 y 30 días

- **Aviso a 60 días.** Dado un contrato con vigencia que termina en 60 días, cuando corre la
  revisión diaria, entonces se genera un aviso `INFORMATIVA` para la Junta de su condominio.
- **Recuperación a 59 días.** Dado un contrato cuyo aviso de 60 días no se generó, cuando el job
  vuelve con 59 días restantes, entonces genera ese aviso una sola vez, y una segunda
  ejecución no lo duplica.
- **Aviso a 30 días.** Dado un aviso de 60 ya generado, cuando faltan 30 días, entonces se genera
  el aviso `PRIORITARIO` de 30.
- **Recuperación a 29 días.** Dado un contrato sin avisos, cuando el job vuelve con 29 días
  restantes, entonces genera solo el de 30 días y registra el de 60 como `OMITIDO` por prioridad.
- **Deduplicación.** Dado un aviso existente para (contrato, vigencia, umbral), cuando la revisión
  se ejecuta de nuevo, entonces no se crea otro registro ni otra auditoría.
- **Renovación.** Dado un contrato con avisos de la vigencia anterior, cuando se renueva con una
  nueva vigencia y fecha de término, entonces inicia su propio calendario y los avisos de la
  vigencia anterior se conservan intactos.
- **Dos condominios.** Dados contratos de dos condominios con la misma fecha de término, cuando
  corre la revisión, entonces cada condominio recibe sus avisos y ninguno aparece en el otro.
- **Contrato vencido.** Dado un contrato cuya vigencia terminó, cuando corre la revisión,
  entonces no se generan avisos nuevos.
- **Auditoría.** Dado un aviso generado u omitido, entonces existe un registro
  `ALERTA_VENCIMIENTO_CONTRATO` con actor `SISTEMA_AUTOMATICO` y el estado resultante.
