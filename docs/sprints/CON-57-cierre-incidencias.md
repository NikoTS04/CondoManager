# CON-57 — Confirmación, calificación, cierre y reapertura de incidencias

Responsable: Jerson · Revisión: Gerardo · Sprint 4 · 5 puntos.

## Entrega

- Migración `20261129_0029`: `calificacion`, `motivo_reapertura`, `fecha_cierre` y
  `cerrado_por` en `incidencias`, con checks de calificación 1–5 y de cierre
  `CERRADO ⇔ fecha_cierre y cerrado_por presentes`.
- `POST /api/v1/incidencias/{id}/confirmacion`: el residente reportante confirma con
  calificación y cierra; registra `CIERRE_CONFORME_TICKET`.
- `POST /api/v1/incidencias/{id}/reapertura`: el residente reabre desde `RESUELTO`
  con motivo obligatorio; el ticket vuelve a `EN_PROCESO` y registra
  `REAPERTURA_TICKET_INCIDENCIA`.
- `POST /api/v1/incidencias/{id}/cierre-administrativo`: Junta cierra con decisión
  autorizada y motivo; registra `CIERRE_ADMINISTRATIVO_TICKET`. El proveedor no cierra.
- Cada decisión crea una entrada pública en el historial, incrementa la versión,
  valida vínculo activo y condominio, y escribe auditoría de siete campos en la
  misma transacción.
- Portal: calificación y comentario, reapertura con motivo y cierre administrativo
  en el detalle de la incidencia.

## Verificación

- `ruff check` y `ruff format --check` sobre los archivos tocados: en verde.
- `pytest src/tests/unit -q --no-cov`: 475 pruebas.
- `pytest src/tests/integration -q --no-cov` sobre PostgreSQL 16 desechable: 4 nuevas
  pruebas de CON-57 en verde.
- `npx tsc --noEmit` en `frontend/`: en verde.
- `python scripts/verify_sdd_compliance.py`: en verde.
- Rama `feat/sprint4-jerson`, sobre el commit de CON-56.

## Decisiones

- `CERRADO` es terminal; para volver a trabajar, el residente debe reabrir desde
  `RESUELTO`, no desde `CERRADO`.
- El cierre administrativo es público en el historial para que el residente conozca
  el motivo, sin exponer sustentos internos de costos.
