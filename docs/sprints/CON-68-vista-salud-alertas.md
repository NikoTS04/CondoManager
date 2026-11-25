# CON-68 — Vista de salud y alertas visibles para administración

Responsable: Alejandro · Revisión: Nicolás · Sin migración (solo lectura sobre tablas existentes).

## Qué se hizo

- **Spec primero.** [notificaciones §9](../../specs/02-domains/03-notificaciones/spec.md),
  [escenarios](../../specs/04-acceptance-criteria/salud-y-alertas-visibles.feature.md),
  [api-contracts](../../specs/05-api/api-contracts.md), OpenAPI
  [`monitoreo.paths.yaml`](../../specs/03-contracts/openapi/monitoreo.paths.yaml) y la matriz de
  [security-and-rbac](../../specs/01-architecture/security-and-rbac.md). Sin eventos nuevos.
- **`GET /api/v1/monitoreo/salud`** (solo SUPERADMIN): `api`, `postgresql`, `redis` y `correo` con
  `ok`/`error`/`deshabilitado` según el perfil; `estado_general`; último inicio, fin, duración y
  resultado de cada job. Reutiliza `comprobar_postgres`, `estado_dependencia` y `estado_redis` de
  `health.py`; nunca expone URLs, credenciales ni errores del driver. Responde 200 aunque algo
  falle (si PostgreSQL cae, los jobs figuran `SIN_REGISTRO`).
- **`GET /api/v1/monitoreo/alertas`** (SUPERADMIN, ADMIN_JUNTA, AUDITOR): alertas de CON-84 con
  `componente` (`correo`|`job`), `operacion` (tipo de evento o nombre del job) y
  `referencia_diagnostico` (`origen_tipo`, `origen_id`, `referencia_correlacion`, nula hasta
  CON-82). SUPERADMIN ve todas, incluidas las de job sin condominio; Junta y Auditor solo su
  condominio (las de job quedan excluidas por el filtro; condominio ajeno → 403). Filtros
  `estado`, `limit`, `offset`, `condominio_id`.
- **Portal.** Sección «Salud y alertas» en el portal de Junta (`SaludAlertasSection.tsx`,
  entrada en `JuntaNav`). El panel de salud solo se muestra al rol global; las alertas, a los tres
  roles administrativos. Las rutas existentes no cambian.
- **Costura para CON-83.** `src/core/salud_operativa.py::listar_ejecuciones_jobs(db)` es la única
  lectura de ejecuciones. Interfaz esperada: devolver `list[EjecucionJob]` con una fila por job
  (`nombre`, `inicio`, `fin`, `duracion_segundos`, `resultado` en `EN_CURSO|COMPLETADO|INCOMPLETO|
  SIN_REGISTRO`). Hoy lee `estado_job_notificaciones` (traduce `correo` → `notificaciones`) y
  marca `diario` como `SIN_REGISTRO`. CON-83 solo debe reemplazar su cuerpo; el endpoint y la
  pantalla no cambian.

## Evidencias

- `pytest -q`: 531 passed, 432 skipped (los omitidos requieren PostgreSQL real).
- Nuevas: `src/tests/unit/test_monitoreo_con68.py` (18 casos: perfil con Redis/correo
  deshabilitado, PostgreSQL caído sin secretos, duración y job en curso, 403 por rol, filtro de
  condominio en el SQL generado, job solo para SuperAdmin, paginación y validación).
- Integración `test_vista_monitoreo_respeta_rol_y_aislamiento_entre_condominios` (SuperAdmin vs
  Junta, condominio ajeno, salud 403). **No se pudo ejecutar localmente**: no hay PostgreSQL ni
  Docker; debe correr en CI.
- Frontend: `tsc --noEmit`, `npm run lint` y `node --test tests/*.test.mjs` limpios (5 pruebas
  nuevas de presentación). `npm run build` no se ejecutó.
- `scripts/verify_sdd_compliance.py`: cumple. Ruff limpio en los archivos nuevos/tocados (el
  lint global conserva su deuda histórica).

## Pendientes y decisiones por confirmar

1. **Quién ve la salud.** Se restringió a SUPERADMIN porque PostgreSQL, Redis y los jobs son
   globales. ¿La Junta debería ver al menos el estado de los componentes? Es una regla de negocio.
2. **Correo = configuración.** Su estado sale de `MAILJET_ENABLED`; no se sondea Mailjet. Un
   sondeo real (con timeout) queda para CON-83 si se desea.
3. **`diario` sin registro.** El job diario no escribe ejecución hoy; figura `SIN_REGISTRO` hasta
   CON-83/85.
4. **SuperAdmin y filtro por condominio.** La pantalla le muestra siempre todas las alertas; la
   API admite `condominio_id`, pero no hay selector en la UI.
5. **Solo lectura.** No se atienden ni reintentan alertas desde esta vista (CON-66/86). Las de job
   siguen sin poder atenderse (`atender` responde 404).
6. **Correlación.** Se muestra «Sin correlación aún» mientras CON-82 no la llene.
