## Descripción del cambio

<!-- Resume qué cambia y por qué. -->

## Trazabilidad SDD

- Historia / Jira:
- Proceso o módulo (PROC-XX):
- Especificaciones y contrato vinculados:
- Responsable:

## Evidencia de pruebas

<!-- Indica comandos, resultados, corte/commit y limitaciones. Si reutilizas resultados del equipo, enlaza su fuente y aclara que no se ejecutaron de nuevo. Entrega Sprint 2: docs/sprints/CON-75-entrega-sprint-2.md. -->

## Definición de Terminado — Sprint 2

- [ ] Cumple los criterios de aceptación de la historia.
- [ ] Persiste los datos requeridos y contempla reintentos/idempotencia cuando corresponde.
- [ ] Cuenta con evidencia de recuperación entre sesiones/reinicios y concurrencia PostgreSQL aplicable.
- [ ] Respeta autorización y aislamiento por condominio.
- [ ] Actualiza o valida las especificaciones en `specs/` y los contratos de API afectados.
- [ ] Incluye o actualiza escenarios BDD y pruebas automatizadas unitarias/de integración; pasan los checks de CI.
- [ ] Los cálculos financieros usan `Decimal`, no `float`, cuando corresponde.
- [ ] Los cambios transaccionales registran auditoría inmutable con los siete campos requeridos.
- [ ] Los eventos representan operaciones confirmadas y sus consumidores toleran reentregas.
- [ ] El recorrido y sus errores están documentados; se distingue transporte simulado de entrega confirmada.
- [ ] Otro integrante del equipo revisó el cambio y aprobó el PR.

<!-- Si un punto no aplica, justifícalo; no lo marques como cumplido sin evidencia. -->

## Riesgos y pendientes

<!-- Migraciones, compatibilidad, pasos manuales o deuda técnica. -->
