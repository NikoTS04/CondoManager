# CON-84 — Alertas de fallos definitivos con referencia al origen

Responsable: Alejandro · Revisión: Nicolás · Migración: `20261125_0025_alertas_fallos_definitivos`.

## Qué se hizo

- **Spec primero.** [spec.md §7](../../specs/02-domains/03-notificaciones/spec.md),
  [delivery-policy](../../specs/02-domains/03-notificaciones/delivery-policy.md),
  [escenarios](../../specs/04-acceptance-criteria/alertas-fallos-definitivos.feature.md),
  diccionario de datos, `schema.sql`, OpenAPI (`sprint-2.paths/schemas`) y catálogo de eventos
  (sin evento nuevo).
- **Una sola tabla.** Se reutiliza `notificaciones_alertas` (CON-37), sin mecanismo paralelo.
  Columnas nuevas: `origen_tipo` (`CORREO`|`JOB`), `origen_id` y `referencia_correlacion`
  (nullable, 64 caracteres; CON-82 la llenará). Tipo nuevo `JOB_FALLO_DEFINITIVO`.
- **Deduplicación.** La unicidad pasa a `(origen_tipo, origen_id, ciclo, tipo)`. Las filas
  existentes se migran con `origen_tipo = CORREO` y `origen_id = notificacion_id`.
- **Correo.** `crear_alerta` rellena el origen y devuelve si creó la alerta; los cuatro caminos
  del worker y el callback de Mailjet no cambian.
- **Job.** `crear_alerta_job(db, nombre, intentos, maximo_intentos, …)` solo crea la alerta
  cuando `intentos >= maximo_intentos`. `src/core/jobs.py` llama a
  `registrar_fallo_definitivo_job` cuando `/jobs/diario` o `/jobs/notificaciones` terminan en
  error; corre en su propia transacción, no propaga errores y no revela la causa. Un 409
  `JOB_EN_CURSO` no es un fallo.
- **API.** `GET /notificaciones/alertas` agrega `origen_tipo`, `origen_id` y
  `referencia_correlacion`; `notificacion_id` y `condominio_id` pueden ser nulos. Las alertas
  de job no tienen condominio: no se listan por condominio y `atender` responde 404.

## Evidencias

- `pytest -q`: 476 passed, 431 skipped (los omitidos requieren PostgreSQL real).
- Nuevas pruebas unitarias: `src/tests/unit/test_alertas_fallos_definitivos.py` (12 casos:
  umbral de reintentos, idempotencia, ciclo, truncado de la referencia, origen de correo, DTO,
  migración, hook del cron en ambos endpoints y 409 sin alerta).
- Nueva prueba de integración `test_alerta_de_correo_guarda_origen_y_la_de_job_es_idempotente_y_aislada`
  (3 registros concurrentes → 1 alerta; aislamiento entre condominios). **No se pudo ejecutar
  localmente**: no hay PostgreSQL ni Docker. Debe correr en CI (`Backend / Migraciones`).
- `ruff check` sin errores en los archivos tocados (el lint global conserva su deuda histórica).
  `ruff format --check` limpio en los archivos nuevos; `jobs.py` y `persistencia.py` ya
  tenían deuda de formato previa (no bloqueante en CI).
- `scripts/verify_sdd_compliance.py`: cumple. Spectral 6.15.0: mismos 9 errores y 89 avisos que
  la rama base (sin regresión).
- Migración 0025 sin ejecutar contra PostgreSQL; revisada por inspección y cubierta por el
  `upgrade head → downgrade base → upgrade head` de CI (`REVISIONES_API` actualizado).

## Pendientes y decisiones de negocio por confirmar

1. **Reintentos de un job.** Hoy Hobby ejecuta cada job una vez al día sin reintento propio, así
   que se fijó `MAX_INTENTOS_JOB = 1`: el primer fallo es definitivo. CON-85 debe aportar el
   contador y el máximo reales; confirmar cuántos reintentos corresponden.
2. **Ciclo de un job.** Se usa la fecha UTC `AAAAMMDD` (una alerta por job y día). Confirmar si
   debe ser por ejecución (CON-83 tendrá un id de ejecución).
3. **Alertas de job sin condominio.** Son transversales; solo se verán en la vista global
   (CON-66/68). Falta decidir quién puede atenderlas y cómo se audita, ya que `auditoria_logs`
   exige `condominio_id`. La creación de alertas tampoco se audita (igual que las de correo);
   solo su atención.
4. **Correlación.** El campo existe y se expone, pero nadie lo llena hasta CON-82; no se inventó
   el formato.
5. **Fallo de jobs de Mailjet/Redis** (`recuperar_*`, `procesar_uno`) sigue gestionándose por
   notificación; solo el fallo global del cron genera alerta de job.
