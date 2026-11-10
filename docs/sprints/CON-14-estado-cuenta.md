# CON-14 — Estado de cuenta por departamento

Fecha de corte: 02/11/2026, America/Lima. Responsable: Gerardo Raúl León Chacón.
Rama local: `feat/PROC-01-con14-estado-cuenta`, creada desde `develop` en `fb38af2`
y actualizada sobre `57f108b` después de la integración de CON-77.
Historia: [CON-14](https://tarquisoncco2.atlassian.net/browse/CON-14).
El [PR #31 de CON-77](https://github.com/NikoTS04/CondoManager/pull/31) ya figura
fusionado en `develop`; CON-14 se mantiene en una rama local independiente.

Trazabilidad local: especificación primero en `acb3d5a`, implementación y pruebas
en `8d902e9`, seguidas por el commit de esta evidencia.

## Funcionalidad

- Nueva consulta `GET /api/v1/cuotas/departamentos/{departamento_id}/estado-cuenta`.
- Cargos, abonos efectivos, mora y correcciones con identificadores de origen;
  aplicaciones y compensaciones conservadas, sin sumar de nuevo los recibos diarios
  históricos ni el crédito generado por el mismo pago.
- Rango inclusivo de fecha de registro en Lima, saldo inicial/final y totales de
  todo el rango, paginación y orden estable. Fecha bancaria y periodo de la cuota
  se muestran aparte. Sin filtros: mes actual de Lima.
- Deuda/crédito actuales separados del saldo de cierre histórico; EN_REVISION
  separado de los abonos efectivos.
- Residentes solo consultan sus unidades activas; Junta/Auditor su condominio;
  SuperAdmin puede consultar por UUID como soporte global. Sesiones revocadas
  fallan antes de consultar. Las respuestas privadas no se almacenan en caché.
- Transacción PostgreSQL REPEATABLE READ y READ ONLY: consultar no devenga mora,
  concilia ni modifica saldos, archivos, auditorías u outbox. No hay migraciones.
- Pantalla de cuenta del residente con filtros, resumen, movimientos, revisión,
  carga/vacío/error/reintento, paginación y cancelación de respuestas anteriores.
  Cambiar de unidad desmonta el estado anterior. El selector se ajusta en móvil.

Contrato normativo y reglas de apertura:
[estado-de-cuenta.md](../../specs/05-api/estado-de-cuenta.md).
OpenAPI 2.5.0: `estado-cuenta.paths.yaml` y `estado-cuenta.schemas.yaml`.
BDD ejecutable: `estado_cuenta.feature` y `test_estado_cuenta_bdd.py`.

## Casos y límites financieros

Se prueban cargos de 100.00, parcial de 40.00 (pendiente 60.00), segundo abono de
80.00 (deuda 0.00/crédito 20.00) y reporte adicional de 999.99 que permanece en
revisión sin reducir el saldo. Un retroactivo sobre el motor diario conserva
devengos, ajustes e imputaciones originales y devuelve el crédito vigente de
50.00, sin volver a sumar las aplicaciones de recibos obsoletos.

Los importes anteriores sin detalle se identifican como base histórica sin fecha;
no se inventan pagos o fechas para explicarlos. La proyección verifica importes
por comprobante, componentes no negativos y conciliación con deuda/crédito.
Si las fuentes no cuadran, responde 409 `ESTADO_CUENTA_INCONSISTENTE`; no corrige
ni oculta diferencias. La consulta no certifica fechas anteriores al historial
disponible ni adopta automáticamente movimientos legacy ausentes.

## Verificación local

| Comprobación | Resultado |
|---|---|
| Backend: regresión antes de integrar CON-77 | 677 aprobadas, sin fallos ni omisiones; cobertura 92,31 % (mínimo 80 %), módulo nuevo 96,52 % |
| Pruebas nuevas de CON-14 | 26 aprobadas: 13 unitarias, 10 de integración y 3 BDD |
| Verificación conjunta tras actualizar con CON-77 | 41 aprobadas: 26 de CON-14 y 15 de CON-77, sin fallos ni omisiones |
| Frontend Node | 24 aprobadas |
| TypeScript, ESLint y build Next.js de producción | Aprobados |
| Chromium sobre la compilación integrada | CON-14: rango, página, móvil sin desborde, error/reintento y respuesta tardía de otra unidad; CON-77: borradores y respuestas tardías de otro condominio; aprobados |
| Ruff/formato de Python modificado y verificador SDD | Aprobados |
| OpenAPI / Spectral 6.15.0 | Sin errores; 71 advertencias documentales en contratos previos, ninguna en los nuevos |

Se ejecutaron también `ruff check .` y `ruff format --check .`: el repositorio
conserva 38 diagnósticos en 13 archivos previos y 15 archivos pendientes de formato,
todos fuera de los archivos modificados por CON-14. El detalle queda en
`tmp/con14-ruff-global.json` y `tmp/con14-format-global.txt`; no se mezcló esa
limpieza con la historia.

La verificación SQL usa login, autorización y productores financieros reales con
PostgreSQL 16 efímero en localhost:55414, exclusivamente de pruebas, sin Supabase.
Las pruebas específicas fijan las fechas de registro de pagos a octubre de 2026
para seguir siendo reproducibles si cambia el calendario real.

La ejecución general usa la imagen de pruebas local `condomanager-pr25-tests:local`,
una copia del código dentro del contenedor (sin `.env`, `.git`, cachés ni dependencias
locales) y la red del PostgreSQL temporal. Todas las variables de base apuntan a
ese servidor y el JWT es exclusivo de prueba. XML, cobertura y capturas se guardan
en `tmp/`, ignorado por Git.

Los 26 casos específicos se repitieron sobre su versión final con el reloj fijo;
la regresión general verifica el mismo código productivo del backend.

Chromium intercepta la API para comprobar la interfaz y controlar respuestas tardías;
no se presenta como validación SQL. Los flujos con PostgreSQL se verifican aparte
mediante integración y BDD sobre la aplicación real.
Ambos recorridos de Chromium se repitieron con la compilación de producción
integrada, servida temporalmente en localhost:3078.

## Reproducción

Comandos Git utilizados para publicar CON-77 y actualizar la base local de CON-14:

```powershell
git push -u origin feat/CORE-con77-aislamiento-condominios
git fetch origin develop
git rebase --autostash origin/develop
git log --oneline origin/develop..HEAD
```

El PR #31 se creó con la API de GitHub mediante el script local
`tmp/crear_pr_con77.py`, usando Git Credential Manager sin imprimir credenciales.
El rebase restauró automáticamente el cambio de `.gitignore`; se verificó que su
contenido fuera idéntico al anterior.

Con dependencias de desarrollo de `pyproject.toml` y Docker Desktop activos:

```powershell
docker run --detach --name condomanager-con14-postgres --publish 127.0.0.1:55414:5432 --env POSTGRES_USER=con14 --env POSTGRES_PASSWORD=con14_local_test --env POSTGRES_DB=con14_test --tmpfs /var/lib/postgresql/data postgres:16-alpine
$taskDbUrl = 'postgresql+asyncpg://con14:con14_local_test@127.0.0.1:55414/con14_test'
@('DATABASE_URL', 'CON13_TEST_DATABASE_URL', 'CON46_TEST_DATABASE_URL', 'CON39_TEST_DATABASE_URL', 'CON05_TEST_DATABASE_URL', 'CON06_TEST_DATABASE_URL', 'CON04_TEST_DATABASE_URL') | ForEach-Object { Set-Item -Path ('Env:' + $_) -Value $taskDbUrl }
$env:JWT_SECRET = 'con14-clave-publica-exclusiva-de-pruebas-no-produccion'
$env:CONDOMINIO_PILOTO_ID = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
.\.venv\Scripts\python.exe -X utf8 -m pytest src/tests/unit/test_estado_cuenta.py src/tests/integration/test_estado_cuenta_db.py src/tests/bdd/test_estado_cuenta_bdd.py -q
# Verificación conjunta, con CON-77 integrado:
.\.venv\Scripts\python.exe -X utf8 -m pytest src/tests/unit/test_estado_cuenta.py src/tests/integration/test_estado_cuenta_db.py src/tests/bdd/test_estado_cuenta_bdd.py src/tests/integration/test_aislamiento_con77_db.py -q
.\.venv\Scripts\python.exe -X utf8 scripts/verify_sdd_compliance.py
npx.cmd --yes @stoplight/spectral-cli@6.15.0 lint --ruleset .spectral.yaml --fail-severity error specs/03-contracts/openapi/condomanager.openapi.yaml
```

Frontend, desde `frontend/`:

```powershell
node --test tests/*.test.mjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/next/dist/bin/next lint
node node_modules/next/dist/bin/next build
node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3077
```

Con ese servidor activo, desde otra terminal en la raíz:

```powershell
.\.venv\Scripts\python.exe -X utf8 frontend/e2e/con14_estado_cuenta.py
```

El script requiere Playwright/Chromium (`pip install playwright` y
`python -m playwright install chromium` en el entorno virtual).

## Integración y aceptación

La implementación consume el contrato financiero vigente y no modifica el motor
de CON-25/27/28. Corresponde revisar con Anderson los criterios de fecha de registro,
base histórica y lectura de compensaciones, y repetir las pruebas si cambia su
contrato. La nueva ruta se añadió a la matriz transversal de CON-77 después de
integrar el PR #31; su acceso ya se verifica con los cuatro roles vigentes.

Antes de cerrar la historia: revisión de otro integrante y aceptación del recorrido
en el ambiente compartido. No se cambió el estado de Jira, no se publicó esta rama
ni se abrió PR de CON-14. El cambio local del usuario en `.gitignore` permanece fuera
de los commits de la historia.
