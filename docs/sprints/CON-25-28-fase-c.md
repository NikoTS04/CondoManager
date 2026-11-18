# CON-25–28 — Regresión completa y validación técnica, Fase C

Fecha: 08/11/2026. Rama conservada: `feat/CON-25-conciliacion-pagos`.
HEAD: `28fe57e21c7347dcb755d33b1212d26eb12dab68`.
Se incorporan a la copia evaluada los dos archivos nuevos de Fase B:
`docs/sprints/CON-25-28-fase-b.md` y
`src/tests/integration/test_pagos_fase_b_db.py`, todavía sin commit.

## Versión exacta y aislamiento

- Versión de ejecución: **`phase-c-28fe57e-d3b747646565`**.
- SHA-256 del conjunto ordenado de 498 archivos:
  `d3b7476465655e76cdaf456d9ed6d88267137e0644078a3ed92da489609b198e`.
- Manifiesto por archivo, TAR y huella del TAR:
  `tmp/sprint3/phase-c/manifest.json` y `codigo.tar`.
- Las fuentes se congelaron antes de ejecutar; las verificaciones finales
  confirmaron que ni el repositorio evaluado, ni la copia de trabajo, ni las
  herramientas de ejecución cambiaron durante las suites. Este informe se añade
  después de finalizar; no modifica código o pruebas de la versión evaluada.
- PostgreSQL 16.15 en dos instancias nuevas: una para pruebas y otra vacía para
  migraciones. Red interna exclusiva, sin puertos publicados, datos tmpfs.
- Recursos: prefijo `condomanager-anderson-s3-phasec-20261108`. No se arrancan ni
  modifican los contenedores anteriores. El pytest temporal usa `--no-healthcheck`.
- Imagen backend inmutable:
  `sha256:009038208cf298023f6b80f8795f5de8a173e44c9fda1505d4194d087bf44b66`.
- Backend: Python 3.12.15, pytest 9.0.3, SQLAlchemy 2.1.5, asyncpg 0.32.0.
  Frontend: Node 22.20.0, Next.js 14.2.35, TypeScript 5.9.3, ESLint 8.57.1.
  Versiones completas conservadas en los JSON de entorno.

## Backend: una ejecución completa, sin exclusiones

Se ejecutó `pytest src/tests -vv --tb=long --maxfail=1 --cov`, con JUnit y cobertura
en el anfitrión. Un plugin temporal ordena los grupos, pero no excluye ni modifica
casos. Se guardan eventos por fase de cada test, checkpoints XML y datos de
cobertura parciales; no se depende solo del cierre final para conservar evidencia.

| Categoría disjunta | Aprobadas | Fallidas | Errores | Omitidas |
|---|---:|---:|---:|---:|
| Historias CON-25–28, incluidos los casos nuevos de Fase B | 27 | 0 | 0 | 0 |
| BDD de pagos y morosidad | 12 | 0 | 0 | 0 |
| Regresión financiera y contratos: cuotas, mora, crédito, ledger, auditoría, outbox y respuestas/eventos | 261 | 0 | 0 | 0 |
| Integraciones CON-13, CON-14 y CON-77 | 94 | 0 | 0 | 0 |
| Resto del backend y sus BDD | 340 | 0 | 0 | 0 |
| **Total** | **734** | **0** | **0** | **0** |

- Tiempo pytest: **1992,75 s (33 min 12 s)**. Salida de pytest y contenedor: **0**.
- Se completaron setup/call/teardown de los 734 casos.
- Comparación de colección, sin ejecutar otra suite sobre la base: se conservan
  los **692 casos de aa2ee99**, más **42 casos añadidos**, sin casos base ausentes.
- PostgreSQL permaneció running/healthy en las **399 muestras** de la ejecución
  completa y saludable al terminar. Cero esquemas residuales de las fixtures
  consultadas (`con04_%`, `con11_%`, `con13_%`, `con3_%`).
- **Cobertura global: 92,37 %**, superior al mínimo de **80 %**. Se cubrieron
  5849 de 6332 líneas; se conserva la configuración del proyecto, sin exclusiones
  adicionales de código productivo. No se suman corridas históricas para este total.

## Frontend y empaquetado

| Verificación | Resultado |
|---|---|
| Pruebas JavaScript | 31 aprobadas, 0 fallidas/omitidas/canceladas |
| TypeScript (`--noEmit --incremental false`) | Código 0 |
| ESLint | Código 0, sin advertencias ni errores |
| Build de producción final | Código 0, paquete standalone generado |

El primer build de la copia aislada compiló, pero Windows impidió copiar un
symlink de node_modules al paquete standalone (EPERM). **No se consideró aprobado
ese empaquetado**, aunque Next devolviera código 0. Se conservó el log y se repitió
solo el build en otra copia con dependencias físicas, sin reinstalar ni modificar
fuentes o configuración productiva. Las versiones de dependencias coinciden.

El segundo build pasó sin esa advertencia; se verificaron `standalone/server.js`,
`standalone/node_modules` y las huellas de todas las fuentes frontend, idénticas
al manifiesto. Las pruebas de recibos, observaciones, errores y parciales están
incluidas en las 31 pruebas JavaScript. No se inició un servidor ni se ejecutaron
recorridos finales de navegador: corresponden a Fase D.

## Migraciones, contratos y calidad

- Alembic: cabeza única **20261025_0020**. Ciclo
  `upgrade head → downgrade base → upgrade head` aprobado **solo en la instancia
  nueva vacía de migraciones**. Inicio sin tablas; después de downgrade queda
  únicamente alembic_version vacío; ambos upgrades llegan a 0020 con 40 tablas.
- `alembic check` sigue detectando drift previo: tres índices y comentarios de
  tablas/columnas. No se aplicó autogenerate ni se alteró el esquema para ocultarlo.
  Se repitió el diagnóstico con fuentes de **aa2ee99** contra el mismo esquema:
  las diferencias son idénticas, descontando direcciones de memoria del log.
  Además, los 37 archivos ORM/migraciones comparados no presentan diferencias.
- SDD: aprobado.
- Spectral 6.15.0: **0 errores, 71 advertencias**, idénticas a aa2ee99; **0 nuevas**.
- Ruff y formato: **13 archivos Python modificados aprobados**.
- Ruff global: **38 avisos**, los mismos 38 de aa2ee99; **0 nuevos**. No se
  reformatearon módulos ajenos ni se cambió la política de calidad del proyecto.
- Sin enlaces relativos rotos en los Markdown modificados. Se conservan las
  reglas actuales de cuota EN_MORA/PAGO_PARCIAL, recibo histórico, crédito y
  subsanación; los contratos y consumidores se verifican en la suite completa.
- Backend registra 18 advertencias previas de dependencias/configuración/tests:
  Starlette/httpx, alias HTTP 422, path_separator Alembic, ciclo de metadatos y
  una marca asyncio en un test síncrono. No se silencian ni se cuentan como fallos.

## Cambios y evidencia

Durante Fase C **no se modificó código productivo, pruebas, dependencias,
contratos, migraciones ni configuración productiva**. El único nuevo entregable
del repositorio es este informe. No hay commits, pushes ni cambios de rama.

En `tmp/sprint3/phase-c/` (ignorado por Git) se conservan:

- `manifest.json`, `herramientas-sha256.json`, `codigo.tar` y copias congeladas.
- `backend-completo.xml`, `backend.log`, `backend-resumen.json`, `coverage.xml`,
  `.coverage`, colección, eventos JSONL y checkpoints por categoría.
- Logs y JSON de frontend, con el primer intento y el build físico final separados.
- Resultados de SDD, Ruff, Spectral, comparación de colección y comparación de drift.
- `backend-ejecucion.json`, salud JSONL, versiones y `preservacion.json`:
  recursos anteriores preservados y herramientas sin cambios.

La evidencia anterior no se elimina ni sobrescribe. Los contenedores de pruebas
actuales quedan detenidos con código 0 y PostgreSQL continúa saludable, sin
exposición de puertos. No se ejecutó limpieza automática.

## Evaluación y siguiente fase

| Historia | Evaluación técnica de Fase C | Pendiente de aceptación |
|---|---|---|
| CON-25 | Aprobación, prelación, fecha bancaria, conservación, rollback, concurrencia, auditoría/outbox y recuperación verificados | Recorrido final de navegador y revisión funcional del acuerdo fecha bancaria/emisión |
| CON-26 | Decisiones, motivos, privacidad, subsanación, resultado vigente e independencia del transporte verificados | **Correo real CON-78**, navegador y aceptación del equipo |
| CON-27 | Abono, deuda restante, estados y bloqueo/habilitación de reservas reales verificados | Recorrido final de navegador y aceptación del equipo |
| CON-28 | Excedente, origen, consumo único CON-13 y concurrencia con emisión verificados | Recorrido final de navegador y aceptación del equipo |

**Listo técnicamente para Fase D, que requiere autorización.** No equivale a
cierre de Jira, aprobación de PR o despliegue compartido. CON-26 no se declara
completamente aceptada mientras no se acredite recepción real de correo CON-78.
