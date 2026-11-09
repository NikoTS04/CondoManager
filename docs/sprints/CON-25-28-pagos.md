# CON-25–28 — Conciliación de Anderson, Sprint 3

Base original: `aa2ee99`, rama `feat/CON-25-conciliacion-pagos`.
Entrega publicada en [PR #37](https://github.com/NikoTS04/CondoManager/pull/37) para revisión hacia `develop`.
Este documento no cambia Jira ni acredita revisión de pares, aceptación completa o despliegue compartido.

## Alcance implementado

Se conserva el motor integrado: `PagosPersistentesService`, prelación contable,
reconstrucción diaria, fondos, CON-13, auditoría y outbox. No hay tablas nuevas,
migraciones, motores paralelos ni cambios al contrato de lectura de CON-14.

| Historia | Incremento / comportamiento conservado |
|---|---|
| CON-25 | Guardas de conservación del importe; nuevas aprobaciones legacy excluyen cuotas emitidas después de la fecha bancaria; auditoría con fotos por cuota; recibo privado recuperable y visible. |
| CON-26 | Motivo público y notas privadas separados en UI; recibo con instrucciones; subsanación conserva evidencia e identidad; rechazo definitivo; selección correcta del resultado vigente incluso con timestamps iguales. |
| CON-27 | Se conserva EN_MORA con deuda vencida restante y PAGO_PARCIAL fuera de mora; abono, deuda y solvencia son observables sin reducir el bruto de la cuota. |
| CON-28 | Se conserva origen del crédito y consumo único CON-13; el recibo distingue crédito del comprobante del saldo global; CON-14 no duplica el abono. |

Las decisiones y el GET de resultado responden `Cache-Control: private, no-store`
y `Vary: Authorization`. El frontend conserva importes decimales y códigos de
error, distingue respuesta incierta, consulta sin repetir POST y descarta recibos
tardíos de otro contexto. No se reescriben revisiones ni eventos históricos.

Contrato: [pagos-sprint-3.md](../../specs/05-api/pagos-sprint-3.md).
BDD: `sprint_3_anderson.feature` y `test_pagos_sprint3_bdd.py`.

## Compatibilidad con el equipo

- **Gerardo / CON-14 y CON-77:** no se modifica su proyección de cuenta ni
  autorización; se conserva ledger firmado, fechas de registro y deuda real.
- **Brandon / CON-24 y CON-79:** no se cambian filtros, paginación o storage;
  la bandeja conserva listado y evidencia. Solo se incorpora consulta del recibo.
- **Alejandro / CON-13 y CON-78:** se reutiliza aplicación de crédito; el productor
  mantiene eventos canónicos y el consumidor existente. No se implementa SMTP.
- **Nicolás:** se conserva orden de locks, transacciones, migraciones y workers.

## Verificación local

Los resultados finales del incremento están documentados en los informes
[de Fase B](CON-25-28-fase-b.md), [Fase C](CON-25-28-fase-c.md) y
[Fase D](CON-25-28-fase-d.md). Fase C acreditó 734 pruebas backend sin fallos,
92,37 % de cobertura y 31 pruebas frontend aprobadas. Fase D acreditó 18
capturas, 16 fotografías SQL y 20/20 comprobaciones psql; los tres recorridos
complementarios con API interceptada se reportan separadamente.
Los artefactos detallados permanecen en `tmp/` y no forman parte del PR.
No deben interpretarse las corridas históricas de Sprint 2 como resultado nuevo.

Los casos nuevos se ejecutan con fábrica `autoflush=False`, fechas fijas y una
base PostgreSQL 16 local desechable. Las fixtures migran esquemas propios hasta
0020 y los eliminan al terminar; no se usó Supabase ni una base del equipo.

Casos específicos:

- Prelación de todos los componentes, centavos y exclusión por emisión posterior.
- Pago exacto, parcial vencido/no vencido y excedente con origen en CON-14.
- Consumo CON-13 y aprobación concurrente con emisión real.
- Decisiones concurrentes incompatibles, repeticiones y resultado de otra sesión.
- Fallo tardío de outbox y plan deliberadamente inconsistente: huella SQL y
  archivos idénticos antes/después del rollback.
- Revisiones con igual timestamp, UUID inversos y evidencia subsanada.
- Regresiones existentes de retroactivos, snapshots, crédito consumido, fondos
  comprometidos, relay recuperable, roles y cruces entre condominios.

## Reproducción segura

Con Docker Desktop activo y dependencias de desarrollo declaradas instaladas:

```powershell
docker run --detach --name condomanager-anderson-s3-tests --publish 127.0.0.1:55425:5432 --env POSTGRES_USER=sprint3 --env POSTGRES_PASSWORD=sprint3_local_test --env POSTGRES_DB=sprint3_test --tmpfs /var/lib/postgresql/data postgres:16-alpine
.\.venv\Scripts\python.exe -X utf8 scripts/verificar_pagos_sprint3.py
.\.venv\Scripts\python.exe -X utf8 scripts/verificar_pagos_sprint3.py --full
```

El runner reemplaza las URLs de pruebas heredadas, `DATABASE_URL` y su equivalente
sync antes de importar la aplicación. Rechaza destinos no locales, puerto 5432 y
bases sin sufijo `_test`. Esto no autoriza reutilizar una base compartida: el
PostgreSQL de estos comandos es exclusivo y desechable. No imprimir URLs reales.

Frontend, en otra terminal desde `frontend/`:

```powershell
$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:8045/api/v1'
$env:NEXT_PUBLIC_DEMO_MODE='false'
$env:NEXT_TELEMETRY_DISABLED='1'
node --test tests/*.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/next/dist/bin/next build
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3079
```

Desde la raíz, con Chromium instalado para Playwright:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evidencia_pagos_sprint3.py --confirmar-entorno-pruebas
.\.venv\Scripts\python.exe -X utf8 frontend/e2e/pagos_sprint3.py --url http://127.0.0.1:3079
.\.venv\Scripts\python.exe -X utf8 frontend/e2e/con14_estado_cuenta.py --url http://127.0.0.1:3079
.\.venv\Scripts\python.exe -X utf8 frontend/e2e/con77_aislamiento.py --url http://127.0.0.1:3079
```

El primer guion arranca una API HTTP **real** en 8045 con esquema propio, login
persistido y vouchers sintéticos. Chromium reporta y revisa desde las pantallas;
no intercepta la API. Genera PNG y resumen SQL bajo `tmp/sprint3/evidencias/`,
reinicia la API y recupera el recibo; finalmente elimina solo su esquema.

Los otros tres guiones interceptan la API para controlar errores y respuestas
tardías de interfaz; **no se presentan como evidencia SQL**. Los reportes JUnit,
logs y cobertura del runner quedan en `tmp/sprint3/`, ignorado por Git.

## Límites de cierre

- **CON-26 / CON-78:** se verifica aviso durable en EN_COLA, motivo e instrucciones
  y consumo idempotente. No se certifica recepción de correo real: el transporte
  actual solo es SIMULADO y rechaza PROVEEDOR no configurado. No se implementó
  trabajo de Alejandro ni se informó una entrega ficticia.
- Aceptación en ambiente compartido, revisión de otro integrante y actualización
  de Jira continúan pendientes. El código se publicó en la rama del
  [PR #37](https://github.com/NikoTS04/CondoManager/pull/37) hacia `develop`,
  pero el PR no está fusionado ni supone aprobación funcional definitiva.
- La regla de fecha bancaria frente a emisión de cuotas requiere acuerdo
  funcional con el equipo antes del cierre.
- La protección SQL adicional de auditorías/recibos y los timeouts globales son
  endurecimientos transversales; no se alteraron en este incremento.
