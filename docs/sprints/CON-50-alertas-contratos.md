# CON-50 — Alertas contractuales de 60 y 30 días

Responsable: Alejandro. Revisa: Nicolás. Sprint 4, [PROC-06](../../specs/02-processes-and-automations/proc-06-egresos-y-proveedores.md).

## Qué se hizo

- **Spec primero:** [alertas de contratos](../../specs/02-domains/06-egresos-proveedores/alertas-contratos.md),
  [escenarios](../../specs/04-acceptance-criteria/alertas-contratos.feature.md), PROC-06 §4.2.1,
  catálogo de eventos, diccionario de datos y nota en el contrato API (sin endpoints nuevos).
- **Evaluación pura** (`src/modules/alertas_contratos/evaluacion.py`): entrada fecha de término, hoy y
  umbrales ya registrados; salida los avisos a generar u omitir. Un umbral vence con
  `0 <= días <= umbral`; entre pendientes se genera el menor y los mayores se omiten por prioridad.
- **Interfaz mínima con contratos** (`contratos.py`): `ContratoVigente` (`id`, `condominio_id`,
  `fecha_fin`, `vigencia`) y `FuenteContratos`. Hoy se usa `FuenteContratosVacia`.
- **Persistencia propia** (`avisos_contrato`, migración `20261126_0026`): estado `GENERADO`/`OMITIDO`,
  umbral, vigencia, prioridad, rol destinatario `ADMIN_JUNTA` y única por (contrato, vigencia, umbral).
  `contrato_id` **sin llave foránea** porque la tabla de contratos no existe.
- **Servicio** (`service.py`): una transacción por condominio con su lock, inserción idempotente y
  auditoría `ALERTA_VENCIMIENTO_CONTRATO` (actor `SISTEMA_AUTOMATICO`, siete campos y contexto).
- **Job:** `evaluar_contratos` corre dentro de `ejecutar_diario` (`src/core/jobs.py`), bajo su lock existente.

## Evidencias

| Verificación | Resultado |
|---|---|
| `src/tests/unit/test_alertas_contratos.py` (59, 29, 60, 30, vencido, idempotencia, renovación) | 18 aprobadas |
| `src/tests/integration/test_alertas_contratos_db.py` (59, 29, renovación, dos condominios; PostgreSQL 16) | 4 aprobadas |
| Alembic `upgrade head`, `downgrade base`, `upgrade head` | Correcto (con `down_revision` temporal en 0024; ver abajo) |
| `alembic check` | Falla por diferencias previas (comentarios e índices); ninguna menciona `avisos_contrato` |
| `scripts/verify_sdd_compliance.py` | Correcto |
| Ruff en los archivos nuevos o modificados | Limpio. `ruff check .` global ya tenía errores previos en otros archivos |

## Qué falta conectar

- **CON-49:** implementar `FuenteContratos` y devolver su fuente en `obtener_fuente_contratos()`.
  Debe exponer `vigencia` (cambia en cada renovación) y `fecha_fin`. Opcional: añadir la llave foránea a `avisos_contrato.contrato_id`.
- **CON-85:** la revisión usa hoy el lock del job diario. Falta su registro de ejecución, recuperación y derivación de fallos finales.
- **Consulta para Junta:** no hay endpoint ni vista del panel; requiere OpenAPI y permisos tras CON-49.
- **Correo a Junta:** no se encola. `notificaciones_logs` exige un departamento para finalidad `OPERATIVA`.
- **Migración:** `down_revision = "20261125_0025"` (CON-84), que no existe en esta rama. Al integrar, también
  registrar `20261126_0026_alertas_contratos` en `REVISIONES_API` de `src/tests/usuarios_db.py` tras la 0025.

## Decisiones de negocio por confirmar

1. Hoy el cron de Vercel corre a las 05:15 UTC (`vercel.json`), no a las 01:00 UTC. No se cambió.
2. Un contrato ya vencido sin avisos previos no genera ninguno. ¿Se desea un aviso de vencido?
3. Si la fecha de término se edita dentro de la misma vigencia (sin renovar), no se reinicia el calendario.
4. ¿Los avisos deben llegar también por correo a cada integrante de Junta, o basta el panel?
