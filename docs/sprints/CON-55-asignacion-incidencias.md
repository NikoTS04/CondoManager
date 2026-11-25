# CON-55 — Asignación de incidencias con responsable, plazo y avisos

Responsable: Jerson · Revisión: Gerardo · Sprint 4 · 3 puntos.

## Entrega

- Máquina de estados compartida en `src/modules/incidencias/estados.py` y documentada en
  `specs/03-data-models/state-machines.md`, con permisos en
  `specs/01-architecture/security-and-rbac.md`.
- `POST /api/v1/incidencias/{id}/asignacion`: responsable interno vigente del condominio
  o proveedor externo con nombre y correo opcional, plazo futuro y versión vigente.
  Idempotencia por `Idempotency-Key`: repetir la clave con los mismos datos devuelve la
  asignación original; otra clave reasigna y conserva las anteriores.
- `GET /api/v1/incidencias/{id}/avisos`: estado por destinatario (`RESIDENTE`/`PROVEEDOR`),
  intentos, alerta abierta y `CONTACTO_FALTANTE`, sin correos ni contenido del mensaje.
  Junta y Auditor del condominio; residente 403; otro condominio 404.
- Avisos encolados en la misma transacción con `clave_asignacion` y auditoría de siete
  campos bajo `ASIGNACION_TICKET_INCIDENCIA`.
- Migración `20261127_0027`: tabla `incidencias_asignaciones`, campos de asignación en
  `incidencias` y `destinatario_externo_id` en `notificaciones_logs` con unicidad que
  contempla `NULL`. El responsable proveedor es un `UUID` sin FK hasta CON-48.
- Portal de Junta: formulario de asignación, estado y avisos en el detalle de la incidencia.

## Verificación

- `ruff check` y `ruff format --check` sobre los archivos tocados: en verde.
- `pytest src/tests/unit -q --no-cov`: 473 pruebas.
- `pytest src/tests/integration -q --no-cov`: 466 pruebas sobre PostgreSQL 16 desechable
  (`scripts/pg_pruebas.sh`), incluidas 5 nuevas de CON-55.
- `npx tsc --noEmit` y `node --test tests/*.test.mjs` en `frontend/`: en verde.
- `python scripts/verify_sdd_compliance.py`: en verde.
- Rama `feat/sprint4-jerson`, base `develop` en `0ee2389`.

## Decisiones

- El proveedor externo es un `UUID` sin llave foránea, como puente al directorio de CON-48;
  no se bloqueó CON-55 a la espera de ese ticket.
- `CONTACTO_FALTANTE` se deriva en la lectura: un proveedor sin correo no genera aviso ni
  alerta persistida, porque `notificaciones_alertas.notificacion_id` sigue siendo NOT NULL.
