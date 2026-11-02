# CON-77 — Matriz de accesos y verificación de aislamiento

Base: `develop` en `fb38af2`. Responsable: Gerardo. Alcance: API y pantallas
existentes; aceptación final pendiente de integrar las entregas del Sprint 3.

## Reglas vigentes

Se mantienen `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR` y `RESIDENTE`.
`PROPIETARIO_TITULAR`, `COPROPIETARIO` e `INQUILINO` son relaciones por unidad,
no roles adicionales. No se cambia la decisión de identidad de CON-04/06/76.

- **G**: SuperAdmin global, con selección explícita de condominio cuando la ruta
  consulta un contexto. Puede operar en A y B, sin mezclar sus resultados.
- **C**: Junta/Auditor con asignación activa en el condominio del recurso.
- **U**: residente con vínculo activo a la unidad y contexto de sesión coincidente.
- **L**: lectura; **E**: escritura; **—**: sin acceso.
- La identidad del recurso se resuelve en servidor desde PostgreSQL. Ni el UUID
  enviado ni un número de departamento repetido conceden permisos.
- Ruta, query, body y recursos encadenados deben concordar con el contexto real.
  Una denegación no modifica saldos, versiones, evidencias ni genera eventos de negocio.
- Sin sesión: 401. Rol/contexto/vínculo ajenos: 403; recurso que no pertenece a la
  colección solicitada: 404 según el contrato del módulo. No responder 200 con datos ajenos.
- Las sesiones revocadas se rechazan antes de operar. Cambiar de identidad, rol o
  condominio en la interfaz descarta los datos y acciones pendientes del contexto anterior.

## Operaciones actuales

Rutas relativas a `/api/v1`. La columna «Evidencia» identifica suites existentes
o la ampliación CON-77; su presencia no equivale a una ejecución aprobada.

| Operación | SUPERADMIN | ADMIN_JUNTA | AUDITOR | RESIDENTE | Evidencia |
|---|---|---|---|---|---|
| GET/POST `/condominios`; GET `/condominios/{condominio_id}` | G | — | — | — | `test_condominios_api.py` |
| POST/GET `/condominios/{condominio_id}/usuarios` | G | C | — | — | `test_alta_usuarios_db.py` |
| PATCH `/usuarios/{usuario_id}/estado` | G, contexto del usuario | — | — | — | `test_alta_usuarios_db.py` |
| GET/PUT/DELETE `/condominios/{condominio_id}/usuarios/{usuario_id}/rol` | G | C, sin Junta ni autoasignación | — | — | `test_roles_permisos_db.py` |
| GET `/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos` | G | C | — | — | `test_vinculos_db.py` |
| PUT/DELETE `/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos/{departamento_id}` | G | C | — | — | `test_vinculos_db.py` |
| GET/POST `/condominios/{condominio_id}/edificios` | G L/E | C L/E | C L | — | `test_estructura_db.py` |
| GET `/condominios/{condominio_id}/departamentos` | G L | C L | C L | — | `test_estructura_db.py` |
| POST `/condominios/{condominio_id}/edificios/{edificio_id}/departamentos` | G E | C E | — | — | `test_estructura_db.py` |
| PATCH `/condominios/{condominio_id}/departamentos/{departamento_id}/estado` | G E | C E | — | — | `test_estructura_db.py` |
| POST `/condominios/{condominio_id}/importaciones/previsualizar` y `/importaciones/confirmar` | G E | C E | — | — | `test_estructura_db.py` |
| PUT `/condominios/{condominio_id}/politica-mora` | G E | C E | — | — | CON-77 |
| GET/PUT `/departamentos/{departamento_id}/condiciones-pago` | G L/E | C L/E | C L | — | CON-77 |
| GET `/cuotas/departamentos` | G L | C L | C L | U L | CON-77 |
| GET/PUT `/condominios/{condominio_id}/distribucion` | G L/E | C L/E | C L | — | `test_distribucion_api.py` |
| POST `/presupuestos`; PUT `/presupuestos/{id}`; POST `/presupuestos/{id}/aprobar` | G E | C E | — | — | `test_presupuestos_api.py` |
| GET `/condominios/{condominio_id}/presupuestos/{periodo}` | G L | C L | C L | — | CON-77 |
| GET/POST `/condominios/{condominio_id}/conceptos-presupuestales` | G L/E | C L/E | C L | — | CON-77 |
| POST `/cuotas/emitir-lote` | G E | C E | — | — | `test_emision_db.py` |
| GET `/presupuestos/{presupuesto_id}/prorrateo` y `/prorrateo/exportar` | G L | C L | C L | edificio propio, aprobado y sin detalle privado de unidades | CON-77 |
| GET `/pagos/comprobantes` | G L | C L | C L | U L | CON-77 |
| GET `/pagos/solvencia/{departamento_id}` | G L | C L | C L | U L | CON-77 |
| POST `/pagos/reportar`; PUT `/pagos/{comprobante_id}/voucher` | G E | C E | — | U E | CON-77 y `test_pagos_db.py` |
| GET `/pagos/{comprobante_id}/voucher`, `/evidencias` y `/resultado` | G L | C L | C L | U L | CON-77 |
| POST `/pagos/{comprobante_id}/conciliar`; POST `/moras/evaluar` | G E | C E | — | — | CON-77 |
| GET `/edificios/{edificio_id}/fondos-moras` | G L | C L | C L | — | CON-77 |
| GET/POST `/presupuestos/{presupuesto_id}/aplicaciones-moras`; DELETE `/presupuestos/{presupuesto_id}/aplicaciones-moras/{aplicacion_id}` | G L/E | C L/E | C L | — | CON-77 |
| GET `/areas`; GET `/areas/{area_id}/disponibilidad` | G L | C L | C L | C L, respetando edificio del vínculo | CON-77 y `test_catalogo_areas_db.py` |
| GET `/reservas`; POST `/reservas`; POST `/reservas/{reserva_id}/cancelar` | G L/E | C L/E | C L | U L/E | CON-77 y `test_cancelaciones_db.py` |
| GET/POST `/condominios/{condominio_id}/areas` | G L/E | C L/E | C L | — | `test_catalogo_areas_db.py` |
| GET/PUT `/condominios/{condominio_id}/areas/{area_id}`; PATCH `/condominios/{condominio_id}/areas/{area_id}/estado` | G L/E | C L/E | C L | — | `test_catalogo_areas_db.py` |
| GET `/notificaciones/logs` | G L | C L | C L | U L, solo destinatario propio | CON-77 y `test_reservas_notificaciones_db.py` |
| POST `/notificaciones/despachar`, `/reenviar/{log_id}` y `/comunicado-masivo` | G E | C E | — | — | CON-77 |
| GET `/notificaciones/alertas`; POST `/notificaciones/alertas/{alerta_id}/atender` | G L/E | C L/E | C L | — | `test_alertas_notificaciones_db.py` |
| GET `/auth/me` | sesión propia | sesión propia | sesión propia | sesión propia | `test_alta_usuarios_db.py` |

Login y salud son públicos. `/auth/demo-users` depende de `DEMO_MODE`, sin ampliar
los permisos de las rutas operativas. La activación por token de CON-76 aún debe
añadirse cuando exista su implementación integrada.

## Escenarios y ejecución

La ampliación `src/tests/integration/test_aislamiento_con77_db.py` usa la API con
login y autorización reales, migraciones vigentes y dos condominios en un esquema
efímero de una base **exclusiva de pruebas**. Cada condominio tiene un departamento
102 con UUID diferente. Se verifican lecturas válidas, IDs cruzados, roles de solo
lectura, sesiones revocadas y ausencia de efectos persistentes tras denegaciones.

```powershell
$env:CON13_TEST_DATABASE_URL = '<URL PostgreSQL local exclusiva de pruebas>'
.\.venv\Scripts\python.exe -m pytest src/tests/integration/test_aislamiento_con77_db.py -q
```

Las pruebas no usan Supabase ni el `.env` de operación como base de pruebas.
La evidencia de ejecución, los comandos y los límites del corte se registran en
`docs/sprints/CON-77-aislamiento.md`. No cerrar CON-77 hasta integrar y verificar
CON-14/76/79/80 y el ambiente final de CON-81, además del resto de rutas nuevas.
