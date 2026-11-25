# CON-86 — Persistencia y resolución trazable de excepciones

Responsable: Jerson · Revisión: Gerardo · Sprint 4 · por estimar.

## Entrega

- Migración `20261130_0030`: tablas `excepciones`, `excepciones_resoluciones` y
  `excepciones_evidencias`, más el condominio centinela
  `3709ed64-791a-5cd8-99c7-142ab3ee590c` para auditar decisiones globales sin
  relajar el `NOT NULL` de `auditoria_logs.condominio_id`.
- La bandeja persistiza cada caso al consultarlo o listarlo, con componente,
  operación, ciclo, causa, referencia de correlación y evidencia saneada.
- `SUPERADMIN` consulta y resuelve los `JOB_FALLO_DEFINITIVO`; `ADMIN_JUNTA` sigue
  limitado a los fallos de correo de su condominio.
- `REINTENTAR_JOB` solo se ofrece para jobs idempotentes registrados en
  `JOBES_REINTENTABLES` (hoy `notificaciones`); el job `diario` únicamente admite
  `CERRAR_CON_MOTIVO`. La ejecución revalida bajo `FOR UPDATE` y guarda el estado
  real del proceso de origen.
- Cada decisión se guarda con actor, motivo, clave, huella y efecto, con unicidad
  `(excepcion_id, clave_idempotencia)` y auditoría de siete campos. Repetir la
  clave devuelve la decisión original sin ejecutar dos veces la acción.
- Portal: `Excepciones` disponible para SuperAdmin, con origen, referencia de
  diagnóstico, resultado real y botón de reintento cuando está permitido.

## Verificación

- `ruff check` y `ruff format --check` sobre los archivos tocados: en verde.
- `pytest src/tests/unit -q --no-cov`: 478 pruebas.
- `pytest src/tests/integration -q --no-cov` sobre PostgreSQL 16 desechable:
  3 nuevas pruebas de CON-86 en verde y 5 de CON-66 sin regresiones.
- `npx tsc --noEmit` en `frontend/`: en verde.
- `python scripts/verify_sdd_compliance.py`: en verde.
- Rama `feat/sprint4-jerson`, sobre el commit de CON-57.

## Decisiones

- No se creó un evento de dominio nuevo: las alertas siguen siendo registros SQL
  y la trazabilidad se apoya en `excepciones_resoluciones` y `auditoria_logs`.
- El condominio centinela está inactivo y sin roles, así que no aparece en
  selecciones de condominio ni amplía permisos de Junta.
- `CONTACTO_FALTANTE` continúa derivándose en la lectura; se conserva la política
  de `ENVIADO` distinto de `ENTREGADO`.
