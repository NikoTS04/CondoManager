# CON-32 / CON-34 / CON-36 / CON-37 — Entrega y guion de notificaciones

Responsable: Alejandro. Rama: `feat/proc-03-notificaciones-cierre`. Contrato:
[dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md) y
[política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md).

## Qué se entrega

| Historia | Entrega |
| :--- | :--- |
| CON-32 | Aviso de cuota emitida consumido desde el outbox real de cuotas, con destinatarios tomados de los vínculos y plantilla con periodo, departamento, monto, vencimiento y medios de pago. Reentregar el evento no crea avisos lógicos duplicados. |
| CON-34 | Avisos de recepción y de resultado de pago (aprobado, observado, rechazado) generados solo con datos persistidos. Las plantillas ya no inventan valores: si falta una variable obligatoria se lanza `PlantillaIncompletaError`, no se crea el aviso y se registra la incidencia `DATOS_PLANTILLA_INCOMPLETOS`. |
| CON-36 | Avisos de confirmación y cancelación de reservas desde el outbox de reservas, con registro de destinatario, canal, operación, estado e intentos. |
| CON-37 | Reintentos con transporte simulado determinista, alertas administrativas persistentes (`notificaciones_alertas`, migraciones `20261021_0014` y `20261021_0015`), API `GET /notificaciones/alertas` y `POST /notificaciones/alertas/{id}/atender`, y pantalla de alertas en Comunicados de la Junta. |

El contrato HTTP está en [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml)
y el modelo en el [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md).

## Arranque de la demostración

Con `.env` apuntando a la base de demostración, desde la raíz:

```bash
alembic upgrade head
docker compose up -d --build --wait --wait-timeout 180 backend frontend notificaciones-worker
```

`alembic upgrade head` debe terminar en `20261021_0015` (cabeza única). El worker
también puede lanzarse fuera de Docker:

```bash
python -m src.modules.notificaciones.worker
```

Para probar fallos, el transporte simulado interpreta el correo del destinatario:

- `residente+falla1@dominio`: el primer intento devuelve 503 y el segundo tiene éxito
  (`falla{n}` falla mientras los intentos acumulados sean menores o iguales que n).
- `residente+rebote@dominio`: responde 550 (buzón inexistente), error definitivo.

## Recorrido funcional

1. Entrar como SuperAdmin demo (`superadmin@condomanager.pe` / `SuperAdmin123!`) y
   seleccionar condominio. Tener un residente vinculado a un departamento cuyo
   contacto sea `residente+falla1@dominio`.
2. Emitir un lote de cuotas. El worker consume el evento del outbox y crea un aviso
   por destinatario en `EN_COLA`, con la plantilla de nueva cuota.
3. Primer intento: el transporte responde 503 (error temporal). El aviso pasa a
   `REINTENTANDO`, `intentos=1`, con próximo reintento programado según la política.
4. Segundo intento: el transporte acepta el mensaje. El aviso pasa a `ENVIADO` y no
   se genera ninguna alerta. Un reinicio del worker entre ambos intentos conserva
   el estado y no duplica el envío.
5. Cambiar el contacto del residente a `residente+rebote@dominio` y emitir otro
   aviso (por ejemplo, un resultado de pago). El transporte responde 550: el aviso
   queda en `FALLIDO_PERMANENTE` sin reintentos y se crea una alerta `ERROR_DEFINITIVO`
   con el mensaje "El correo del residente del Dpto. N rebotó. Actualice los datos
   de contacto." (sin contactos ni datos sensibles). Si se agotan los cuatro
   intentos de un fallo temporal, la alerta es `INTENTOS_AGOTADOS`.
6. Entrar como Junta, abrir **Comunicados**. La sección de alertas muestra la
   alerta abierta con departamento, tipo de evento y mensaje.
7. Corregir el contacto del residente a una dirección válida y pulsar el reenvío del
   aviso fallido (`POST /notificaciones/reenviar/{log_id}`). Se abre un nuevo ciclo,
   el aviso se envía y, en la misma transacción, la alerta abierta de esa notificación
   queda atendida con el actor como `atendida_por`.
8. También es posible atender una alerta sin reenviar (`POST .../atender`). La
   operación es idempotente: repetirla devuelve la misma alerta sin cambiar
   `atendida_en` ni `atendida_por`, y se audita como `NOTIFICACION_ALERTA_ATENDIDA`.
   Una alerta inexistente devuelve 404 `ALERTA_NO_HALLADA`.
9. Filtrar por estado `ATENDIDA` para ver el historial. Si un nuevo ciclo manual vuelve
   a fallar, se genera otra alerta (la unicidad es por notificación, ciclo y tipo).
10. Entrar como Auditor: ve las alertas (abiertas y atendidas) en modo solo lectura;
    intentar atender devuelve 403 `ACCESO_DENEGADO`. Un residente recibe 403 también
    al listar.

## Límites

- El transporte `SIMULADO` solo acredita aceptación (`ENVIADO`); nunca se declara
  `ENTREGADO`. No hay proveedor real de correo ni de WhatsApp configurado; con
  transporte `PROVEEDOR` sin configuración se registra la alerta `PROVEEDOR_NO_CONFIGURADO`.
- Los medios de pago de la plantilla de cuota son un texto de instrucción: el esquema
  actual no persiste cuentas ni CCI, por lo que no se inventan datos bancarios.
- Una aceptación incierta (intento interrumpido) se conserva para revisión y genera
  alerta `ACEPTACION_INCIERTA`; no se reenvía automáticamente.
- Las invitaciones de CON-04 siguen diferidas.

## Arreglos ajenos para dejar el CI verde

Para que `alembic upgrade head` y la suite completa pasaran fue necesario corregir
problemas de ramas integradas que no pertenecen a notificaciones:

| Commit | Causa raíz |
| :--- | :--- |
| `8e93182` fix(migraciones): unir las cabezas de reservas CON-46 y convergencia CON-72 | `20261021_0012` (CON-46) y `20261020_0012` (CON-73) partían de 0011 y ambas creaban `reservas` y `eventos_reserva_outbox`. CON-46 pasa a apoyarse en `20261020_0012` y adopta las columnas extendidas por CON-73 en lugar de recrearlas; `20261021_0014` une esa rama con `20261021_0013` en una sola cabeza, sin DDL propio. |
| `a616f92` fix(ci): adaptar el reporte en memoria de pagos al contrato sin url_voucher | CON-72 retiró `url_voucher` de la solicitud; el servicio en memoria y sus pruebas seguían usándolo. La URL la genera el servidor. |
| `9805b8c` fix(ci): alinear reservas y fixtures de pruebas con la cabeza de migraciones | El fixture `db_usuarios` migraba una lista parcial de revisiones y anulaba el repositorio real de reservas; ahora usa la cabeza única. Se ajustan modelos y repositorio de reservas a la tabla unificada y se aísla el estado piloto global entre pruebas. |
| `8c49366` fix(ci): aislar y migrar el esquema de la prueba de persistencia de condominios | `test_api_condominio_persistencia_postgres` usaba el esquema público y asumía que ya estaba migrado; en Backend / Pruebas la base está limpia y fallaba con `relation "condominios" does not exist`. Ahora crea un esquema aislado migrado con Alembic y lo elimina al terminar. |
| `54c8f81` fix(ci): alinear la reconciliación de esquema legacy con la cabeza 20261021_0015 | Llegó con develop (PR #26) sellando en `20261021_0013` y retirando la unicidad `uq_evento_reserva_tipo`, que el modelo vigente exige; su prueba no quitaba `notificaciones_alertas` y fallaba por la FK. Ahora aplica también la migración de alertas, conserva la unicidad y sella en la cabeza actual. |
| `63ef543` test(CON-72): completar el contexto del despacho manual con remitente | Efecto de este cambio: `NOTIF_COMUNICADO_GENERAL` exige `remitente`, que antes inventaba la plantilla; la prueba de convergencia recibía `422 CONTEXTO_PLANTILLA_INCOMPLETO`. |
| `a013aff` fix(CON-36): completar el contexto de la notificación del recorrido piloto | Efecto de este cambio: `scripts/verify_pilot_e2e.py` (Docker / Smoke) despachaba `NOTIF_RESERVA_CONFIRMADA` sin costo, moneda ni normas. Usa la tarifa de la reserva aprobada del escenario y el texto de normas del consumidor. |

## Pruebas automatizadas

Pruebas nuevas o ampliadas:
`src/tests/integration/test_notificaciones_emision_db.py` (CON-32),
`src/tests/integration/test_notificaciones_pagos_db.py` (CON-34),
`src/tests/integration/test_alertas_notificaciones_db.py` (CON-37: alertas,
reintentos deterministas, idempotencia entre workers),
`src/tests/unit/test_notificaciones_alertas.py` y `src/tests/unit/test_notificaciones_service.py`.

```bash
.venv/bin/python -m pytest -q src/tests/integration/test_alertas_notificaciones_db.py \
  src/tests/integration/test_notificaciones_emision_db.py \
  src/tests/integration/test_notificaciones_pagos_db.py src/tests/bdd/test_notificaciones_bdd.py
```

## Resultados de las pruebas

Verificación local del 21/10/2026 sobre `ff77e08`, reproduciendo cada job de `.github/workflows/`.
Suite específica de notificaciones (alertas, emisión, pagos, BDD, unitarias y reservas de CON-73): `65 passed`.

| Job | Resultado |
| :--- | :--- |
| Lint | Verde. 41 archivos Python modificados respecto de `develop`; 0 avisos Ruff nuevos; `ruff format --check` sin fallos nuevos (formato previo pendiente en 4 archivos heredados, no bloqueante). |
| Pruebas + cobertura | Verde. `533 passed, 10 warnings` (JUnit: 533 tests, 0 failures, 0 errors, 0 skipped); cobertura **91,40 %** (mínimo 80 %). Base PostgreSQL 16 limpia sin migrar y sin Redis. En develop: 98 failed, 393 passed, 2 errors. |
| Migraciones | Verde. Base limpia: `upgrade head` → `downgrade base` → `upgrade head` correctos (cabeza única `20261021_0015`); `pytest -q src/tests/integration`: `276 passed, 9 warnings`. |
| Contrato API | Verde. `alembic upgrade head`, `seed_usuarios_demo` y `seed_areas_demo`; schemathesis `56 passed` con y sin `-k 'not reporte_pago'`; convergencia CON-72 con el entorno de `specs.yml`: `1 passed, 23 skipped` (ese job solo define `CON73_TEST_DATABASE_URL`, igual que en develop); con base de pruebas, `24 passed`. |
| SDD | Verde. `verify_sdd_compliance.py`: todas las reglas satisfechas. |
| Spectral | Verde. Spectral 6.15.0, `--fail-severity error`: exit 0. |
| Frontend | Verde. `node --test`: 22 tests, 22 pass, 0 fail; ESLint sin avisos; `tsc --noEmit` sin errores; `next build` compilado (7/7 páginas). |
| Docker build/smoke | Verde. Imágenes `condomanager-api:ci` y `condomanager-web:ci` construidas; compose `up --wait` sano; `alembic upgrade head` en `20261021_0015 (head)`; seed piloto 139 unidades; `verify_pilot_e2e.py` 100 % de etapas; `/health` `ok`; web HTTP 200; `down -v`. |
| Gitleaks | Verde. Gitleaks 8.24.3 con `.gitleaks.toml`, `--log-opts=--all`: 106 commits, ~14,25 MB, `no leaks found`. |
