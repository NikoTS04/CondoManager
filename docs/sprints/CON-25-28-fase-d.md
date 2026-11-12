# CON-25–28 — Evidencias finales de aceptación local, Fase D

Fecha: **08/11/2026, America/Lima** (artefactos UTC del 09/11/2026).
Rama conservada: `feat/CON-25-conciliacion-pagos`.
Commit evaluado: **`02bfee0d58bf8bba41b0e4bf95e3f0d7f56ef923`**.
Alcance: exclusivamente Fase D. **Fase E no ejecutada.**

## Resultado ejecutivo

| Historia | Resultado del recorrido real | Situación de aceptación |
|---|---|---|
| CON-25 | Registro, aprobación en Junta, imputación de 100,00, saldo cero, auditoría y recibo del residente comprobados | Evidencia local satisfactoria; pendiente revisión funcional y del equipo |
| CON-26 | Observación, motivo/instrucciones, subsanación, nueva revisión y rechazo definitivo sin acreditación; notas internas privadas | **Aceptación parcial: recepción real de correo CON-78 pendiente** |
| CON-27 | Parcial de 40,00 deja deuda vencida de 60,00; reserva bloqueada por UI y HTTP 403; liquidación posterior permite reserva real HTTP 201 | Evidencia local satisfactoria; pendiente aceptación del equipo |
| CON-28 | Pago de 80,00 aplica 60,00 y genera crédito de 20,00; CON-13 lo consume una sola vez; CON-14 no duplica el abono | Evidencia local satisfactoria; pendiente aceptación del equipo |

El recorrido definitivo terminó con **código 0**, **18 capturas**, **16 fotografías
SQL**, **20/20 comprobaciones independientes mediante psql**, recuperación del
recibo después de reiniciar la API y cero errores JavaScript/peticiones externas
del navegador. Los tres guiones complementarios de UI también terminaron con
código 0, pero sus respuestas interceptadas **no cuentan como evidencia SQL real**.

## Versión evaluada y conservación de Fase C

- Identificador: **`phase-d-02bfee0-dd7c2c49f378`**.
- SHA-256 del conjunto ordenado de archivos:
  `dd7c2c49f378154f11c0ac281855d9e4f30ce87d57455e015c82feb76e316399`.
- SHA-256 del TAR congelado:
  `503a0b664d932cb2907da779e8d1603c1283f1410a6b1639617ccfcdfe00a542`.
- Manifiesto por archivo y copia evaluada: `tmp/sprint3/phase-d/manifest.json`,
  `codigo.tar` y `workspace/`. Se excluyeron archivos `.env`, salvo `.env.example`.
- Se compararon las fuentes de backend, frontend, pruebas, scripts, contratos y
  migraciones con el manifiesto de Fase C: **ninguna diferencia**. Se mantienen
  sus 734 pruebas backend, 92,37 % de cobertura y 31 pruebas frontend como
  evidencia de esa fase; **no se volvieron a ejecutar**.
- Se reutilizó, mediante una copia independiente, el paquete standalone físico
  ya validado en Fase C. Sus archivos coinciden por SHA-256. No se repitieron
  build, TypeScript, ESLint, SDD ni el ciclo de migraciones.
- No se cambió código productivo, pruebas versionadas, dependencias, contratos,
  migraciones ni configuración productiva. El único entregable nuevo no ignorado
  por Git es este informe. Herramientas y resultados temporales quedan en `tmp/`.

## Entorno realmente utilizado

- PostgreSQL **16.15**, contenedor nuevo y exclusivo
  `condomanager-anderson-s3-phased-20261108-pg`, base `phased_test`, datos tmpfs.
- Publicación SQL limitada a **127.0.0.1:55425**. Red interna exclusiva `…-net`
  y una segunda red exclusiva `…-hostnet` para hacer accesible esa publicación
  desde Windows/Docker Desktop. No se conectó ningún contenedor anterior.
- Esquema definitivo: **`con04_d13a4422cabb4165af31a5e7b78d806f`**.
  Las fixtures existentes crean el esquema, aplican sus upgrades hasta 0020 y
  cargan usuarios, unidades, cuotas y vouchers **sintéticos**. No hay operaciones
  bancarias reales ni acceso a Supabase, bases compartidas o servicios productivos.
- API HTTP real: `127.0.0.1:8045`; frontend standalone: `127.0.0.1:3079`.
  `DEMO_MODE=false`; sin broker/worker externo y sin transporte de correo invocado.
- Python **3.12.10** en Windows; FastAPI **0.150.0**, Uvicorn **0.54.0**,
  SQLAlchemy **2.1.5**, asyncpg **0.32.0**, Playwright **1.64.1**,
  Chromium **156.0.8078.4**. Node **22.20.0**, Next.js **14.2.35**.
  Versiones ampliadas: `versiones-backend.json` del recorrido y `frontend-paquete.json`.
  El Python anfitrión difiere del Python 3.12.15 de los contenedores de Fase C;
  no se presenta este recorrido como una nueva regresión completa.
- **27/27 muestras** del recorrido definitivo: PostgreSQL running/healthy.
  Usuarios residente102, moroso402 y admin utilizan contextos Chromium separados,
  login persistido y permisos reales. No se intercepta ninguna respuesta en ese recorrido.

Se reutilizan `preparar`, `servidor` y `resumen_sql` de
`scripts/evidencia_pagos_sprint3.py`, los pasos de sus formularios, `fijar_reloj`,
`crear_base`, `imagen` y `solicitud` de las pruebas existentes. La extensión temporal
añade checkpoints, reservas y emisión real, sin introducir otro motor financiero.
El reloj financiero de pagos es el **20/10/2026**, con fecha bancaria **10/10/2026**;
reservas y emisión posterior conservan su reloj real. Esta combinación es explícita,
no una recepción bancaria o de correo real.

## CON-25 — Aprobar pagos

Comprobante: `5221212c-1f1f-4524-ae94-74290df4b6bd`, departamento 402.

1. El residente reportó **100,00** y adjuntó un PNG sintético desde la interfaz:
   HTTP 202. El checkpoint previo a aprobar conserva las finanzas sin cambios.
2. Junta aprobó desde Conciliación: HTTP 200, importe aplicado **100,00**, deuda
   **0,00**, crédito generado **0,00** y reservas habilitadas al revisar.
3. PostgreSQL confirma una imputación de 100,00, cuota **PAGADA**, bruto y pagado
   iguales a 100,00. La auditoría `REVISION_PAGO_APROBADO` conserva fotografías
   de pagado **0,00 → 100,00**.
4. El residente recuperó el mismo recibo por GET después de recargar. Se comprobó
   `Cache-Control: private, no-store` y `Vary: Authorization`; otro residente recibió
   403. El voucher privado se descargó con autenticación.
5. Después de detener y arrancar nuevamente el servidor API, con nuevas conexiones
   SQL y otro login, el recibo permaneció idéntico, sin otro POST de conciliación.

Evidencia: capturas `CON-25-01` a `CON-25-03`; SQL `00` a `02`;
`api-reiniciada.json` y SQL `15-tras-reinicio-api.json`.

## CON-26 — Observar, subsanar y rechazar

Comprobante: `d38865f0-7f28-4cb2-9823-19d19c270e39`, importe **50,00**, unidad 102.

1. Junta observó con motivo público: «Adjunta una imagen legible para verificar la
   operación». El residente vio motivo y la instrucción de usar **Subsanar voucher**;
   el recibo informa expresamente que no se acreditó el comprobante.
2. Se registró una nota interna identificable. Existe en `revisiones_pago`, pero
   está ausente del recibo, listado de comprobantes, avisos del residente, cuerpos
   de notificaciones y payloads del outbox verificados. Las capturas del residente
   tampoco la muestran.
3. El residente adjuntó otro PNG, con bytes diferentes: PUT 202 y **mismo UUID**.
   La evidencia original sigue descargándose con su huella original; la vigente
   tiene otra huella. Mientras vuelve a EN_REVISION, GET resultado devuelve 404,
   sin presentar la revisión antigua como vigente.
4. Junta revisó la subsanación y rechazó con el motivo «La operación no figura
   acreditada. Contacta con administración». El residente vio el rechazo y las
   instrucciones de contacto, sin botón para subsanar. Otro PUT obtuvo **409**.
5. Las dos revisiones conservan dos referencias de archivo. El endpoint de
   evidencias enumera **archivos revisados**: inmediatamente tras subsanar todavía
   enumera la revisión antigua; después del rechazo enumera ambas. Los dos archivos
   ya estaban persistidos antes de la segunda revisión.
6. Las fotografías financieras de cuotas, saldos, imputaciones y aplicaciones de
   crédito son **idénticas** antes de observar, después de observar, tras subsanar
   y después del rechazo. Cero imputaciones y cero crédito del pago rechazado;
   el crédito previo de 20,00 no se incrementa por los 50,00 rechazados.
7. El consumidor existente procesó los diez eventos de pagos; repetir cada consumo
   no duplicó avisos. PostgreSQL conserva **10 avisos EN_COLA, transporte SIMULADO,
   cero intentos y ningún proveedor_message_id**. La pantalla Avisos muestra su
   condición simulada. **No se ejecutó el transporte ni se afirmó recepción.**

**CON-26 NO se declara completamente aceptada.** CON-78 debe configurar y verificar
el proveedor, entregar a un buzón de pruebas autorizado y aportar evidencia real
de recepción de observación/rechazo, con motivo e instrucciones y sin notas internas.
Eso no se sustituyó por un envío simulado ni por un estado EN_COLA.

Evidencia: capturas `CON-26-01` a `CON-26-06`; SQL `07` a `11`; respuestas de
evidencias/vouchers/resultado/avisos en `api/`; `resumen-sql-guion-existente.json`.

## CON-27 — Parcial, morosidad y reservas

Comprobante parcial: `83921865-a7f9-483c-a17e-9b7cb1dbfd13`, unidad 102.

- Junta aprobó **40,00** contra la cuota vencida de **100,00**. PostgreSQL conserva
  bruto 100,00, pagado 40,00 y estado **EN_MORA**. API y recibo reportan deuda
  restante **60,00** y reservas no habilitadas.
- La interfaz mostró **Reserva bloqueada por mora** y no ofreció Confirmar Reserva.
  Un POST HTTP real de la misma unidad devolvió **403 / DEUDA_MORA_ACTIVA**;
  SQL confirmó cero reservas y cero eventos de reserva.
- Posteriormente se aprobó otro pago de **80,00**: **60,00** completaron la deuda y
  **20,00** quedaron a favor. Este mismo paso sirve al caso CON-28; no se presenta
  como una prueba adicional de pago exacto de 60,00.
- Con la cuota **PAGADA**, pagado 100,00 y deuda cero, el formulario quedó habilitado.
  El residente creó desde él una reserva: **HTTP 201**, estado **CONFIRMADA**, un
  registro SQL y un evento `ReservaConfirmadaEvent`.
- Reserva: `8792a383-338c-4ea4-9e3d-8d8de9e173d5`, 18/11/2026, 19:00–22:00,
  Zona de Parrilla 1. No se condonó deuda ni se habilitó el botón mediante fixtures.

Evidencia: capturas `CON-27-01` a `CON-27-04`; SQL `03` a `06`;
respuestas `CON27-reserva-bloqueada` y `CON27-reserva-201-ui`.

## CON-28 — Excedente, CON-13 y CON-14

Comprobante: `6f62f7ca-e5b1-46a1-a0e1-54a207bc0f51`, unidad 102.

- Junta aprobó **80,00** frente a deuda de **60,00**. Se verificó conservación:
  **80,00 = 60,00 imputados + 20,00 de crédito**; cuota original pagada y saldo
  a favor global 20,00. El residente vio el mismo recibo. La captura móvil de
  390 × 844 no presenta desbordamiento horizontal.
- Antes de consumirlo, CON-14 devuelve deuda 0,00, crédito 20,00 y abonos 120,00
  (40,00 + 80,00), con un solo movimiento PAGO_APROBADO para el excedente.
- Se preparó el presupuesto sintético aprobado y la distribución equitativa como
  en la prueba existente. **POST /cuotas/emitir-lote real → 201** emitió noviembre
  para las 139 unidades activas. La cuota de 102 conserva bruto **30,00**, aplica
  **20,00** mediante CON-13, deja pendiente **10,00** y crédito global **0,00**.
- La llamada de reintento al servicio existente CON-13 devolvió la **misma aplicación**,
  sin cambios financieros ni nueva fila. Repetir la emisión HTTP devuelve **409**,
  sin otro lote ni consumo duplicado.
- CON-14 mantiene abonos **120,00** después de consumir el crédito. El movimiento
  APLICACION_CREDITO identifica 20,00 como detalle, con abono **0,00**. Cargos del
  rango 130,00, saldo final/deuda 10,00: no hay un segundo abono del crédito.
- El recibo histórico sigue indicando los 20,00 **generados por ese pago**, aunque
  el crédito global actual ya sea cero; se comprobaron ambos en API e interfaz.

Evidencia: capturas `CON-28-01` a `CON-28-05`; SQL `05`, `12` y `13`;
respuestas CON14 antes/después, emisión 201 y repetición 409.

## Artefactos y verificaciones cruzadas

Raíz: **`tmp/sprint3/phase-d/`** (ignorada por Git; debe conservarse por separado
del informe versionable). Ejecución de aceptación: **`recorridos/05-final/`**.

- `recorrido-resultados.json`, `fin.json`, `ejecucion.json` y `recorrido.log`.
- `capturas/`: 18 PNG reales; `pantallas/`: texto visible y viewport de cada captura.
- `sql/`: 16 fotografías; `comprobaciones.sql`: consultas usadas en los checkpoints.
- `aceptacion.sql`, `aceptacion-psql.log`, `aceptacion-sql.json`: **20/20**
  comprobaciones adicionales, ejecutadas con psql en transacción **READ ONLY**.
- `postgres-final.sql`: dump del esquema definitivo, SHA-256
  `19566e18b7076697227738142cf256543d9c0e9d6e905dca9c28eefd59442819`.
- `api/`, `api-reiniciada.json`, `navegador-red.json` y tres trazas Playwright
  separadas por usuario. Los tokens y datos presentes son exclusivamente sintéticos.
- **152 filas de auditoría** al finalizar: hashes recalculados y cadena completa
  verificados, incluidas las aplicaciones CON-13 del lote real. Antes del lote,
  el resumen del guion original comprueba 12 auditorías, 5 revisiones,
  3 imputaciones, 10 eventos y 10 avisos.
- `complementarios/`: guiones existentes `pagos_sprint3.py`,
  `con14_estado_cuenta.py` y `con77_aislamiento.py`, sin modificar; los tres con
  código 0. Comprueban errores, respuestas tardías, aislamiento, rango/paginación
  y móvil **con API interceptada**, separados del recorrido real.
- `manifest.json`, `frontend-paquete.json`, copias/huellas de herramientas por
  intento, `entorno-final.json`, `preservacion-final.json`, `resumen-final.json`
  y `sha256-artefactos.json` permiten identificar fuentes, binarios y resultados.

## Incidencias de instrumentación conservadas

Los intentos anteriores no se borran ni se cuentan como recorridos completos
aprobados. Cada reintento usa un esquema nuevo del PostgreSQL exclusivo.

| Intento | Resultado y ajuste exclusivamente temporal |
|---|---|
| Inicial, archivos en la raíz de phase-d | Conexión rechazada desde Windows a la red Docker interna; ninguna fixture creada. Se añadió la red exclusiva hostnet, conservando el bind a 127.0.0.1 |
| `02-red-local` | El checkpoint SQL usaba asyncio.run dentro del loop síncrono de Playwright; se aisló la consulta en otro hilo con sesiones NullPool |
| `03-checkpoints-sql` | La aserción esperaba dos evidencias revisadas antes de revisar la subsanación; se corrigió según el contrato existente y se verificaron archivos/vouchers por separado |
| `04-historial-revisado` | Selector exacto «Desde» no coincidía con la etiqueta requerida «Desde*»; se reutilizó el selector del guion CON-14 existente |
| **`05-final`** | **Recorrido completo aprobado, código 0** |

No se demostró un defecto productivo que requiriera cambiar código. Persiste el
aviso previo Starlette/TestClient sobre httpx al importar las fixtures; no se
silenció ni se modificaron dependencias. El servidor frontend se detuvo
intencionalmente al terminar; su proceso Windows devuelve 1 al ser detenido,
lo que **no es** el código del recorrido, que es 0. La API también quedó detenida.

## Limitaciones y preparación para Fase E

1. **Recepción real CON-78 pendiente: bloquea la aceptación completa de CON-26.**
2. La evidencia es local y con datos sintéticos; no acredita validación bancaria,
   despliegue compartido, recepción de correo ni firma de aceptación del equipo.
3. Sigue pendiente la revisión funcional del acuerdo fecha bancaria/emisión de
   CON-25. Los casos diarios, parcial no vencido, otra deuda, rollback y concurrencia
   mantienen la evidencia B/C; no se afirma haberlos recorrido todos en este navegador.
4. No se hizo una auditoría visual/de accesibilidad completa ni se probaron otros
   motores de navegador. Se documenta Chromium de escritorio y la captura móvil.
5. Drift Alembic y advertencias preexistentes de Fase C no se alteraron ni se
   revalidaron como si fueran correcciones de esta fase.
6. Fuentes, evidencias B/C y contenedores anteriores permanecen conservados.
   PostgreSQL nuevo, sus esquemas y el dump quedan disponibles para inspección;
   los datos tmpfs requieren conservar el contenedor vivo o restaurar el dump.

**Preparados técnicamente para solicitar Fase E, con estas reservas explícitas;
no preparados para declarar cerrado todo el Sprint 3 ni CON-26 completamente
aceptada.** No se avanzó a Fase E, no se actualizó Jira y no se hicieron commits,
pushes ni cambios de rama.
