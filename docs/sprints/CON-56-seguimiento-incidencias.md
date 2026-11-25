# CON-56 — Seguimiento, evidencias, costos e historial de incidencias

Responsable: Jerson · Revisión: Anderson · Sprint 4 · 5 puntos.

## Entrega

- Migración `20261128_0028`: `incidencias_actualizaciones` guarda comentarios, cambios de
  estado, repuestos, importes `NUMERIC(12,2)`, evidencia privada, actor y fecha.
- `POST /api/v1/incidencias/{id}/seguimiento` (multipart): registro de avance con
  comentario, repuesto, monto decimal y foto JPEG/PNG de hasta 3 MiB. Desde `ASIGNADO`
  transiciona a `EN_PROCESO`; un archivo inválido se descarta con advertencia y no
  elimina el avance.
- `POST /api/v1/incidencias/{id}/resolucion` (multipart): solo desde `EN_PROCESO`,
  transiciona a `RESUELTO`. El proveedor no puede resolver ni cerrar.
- `GET /api/v1/incidencias/{id}/historial` y
  `GET /api/v1/incidencias/{id}/actualizaciones/{id}/evidencia`: Junta y Auditor del
  condominio ven costos y sustentos; el residente solo las actualizaciones públicas
  de sus propios reportes.
- Cada mutación registra auditoría de siete campos (`SEGUIMIENTO_TICKET_INCIDENCIA`,
  `RESOLUCION_TICKET_INCIDENCIA`) con estado anterior y posterior en la misma
  transacción, y controla la versión del ticket.
- Portal: historial con fechas, actores y montos, formulario de avance y de resolución,
  descarga privada de evidencia.

## Verificación

- `ruff check` y `ruff format --check` sobre los archivos tocados: en verde.
- `pytest src/tests/unit -q --no-cov`: 474 pruebas.
- `pytest src/tests/integration -q --no-cov` sobre PostgreSQL 16 desechable: 4 nuevas
  pruebas de CON-56 en verde, sin regresiones en incidencias.
- `npx tsc --noEmit` en `frontend/`: en verde.
- `python scripts/verify_sdd_compliance.py`: en verde.
- Rama `feat/sprint4-jerson`, sobre el commit de CON-55.

## Decisiones

- El importe se valida como `Decimal` (nunca `float`) con `condecimal(max_digits=12,
  decimal_places=2)` y se normaliza con `redondear_moneda`.
- El historial usa una sola tabla de actualizaciones con `estado_anterior`/`estado_nuevo`
  en lugar de una tabla separada; cada cambio de estado conserva actor, fecha y
  observación en la misma fila.
