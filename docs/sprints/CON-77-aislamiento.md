# CON-77 — Aislamiento por condominio: avance local

Fecha: 01/11/2026, America/Lima. Rama: `feat/CORE-con77-aislamiento-condominios`.
Base: `develop`, `fb38af2`. Ticket: [CON-77](https://tarquisoncco2.atlassian.net/browse/CON-77).

## Alcance y resultado

Se conservan los cuatro roles vigentes. La [matriz de accesos](../../specs/01-architecture/matriz-accesos-con77.md)
relaciona las operaciones existentes con rol, contexto, vínculo y suites de prueba.
No se introducen roles de propietario/inquilino ni una nueva capa de identidad.

Los controles existentes ya rechazan los accesos cruzados comprobados en este corte.
Se amplía su evidencia con dos condominios PostgreSQL reales, ambos con departamento
102 y UUID diferentes; login y autorización de producción, sin sustituirlos por JWT
inventados o repositorios en memoria. Cada prueba usa un esquema aislado con las
migraciones actuales y un directorio temporal de vouchers.

Se corrige en `JuntaPortal.tsx` un estado de interfaz que sobrevivía al cambio de
condominio: borrador del comunicado, motivo, confirmación, resultado y estado de
operación pendiente. Un contador de cambios de contexto descarta respuestas de una
visita anterior, también si se vuelve al mismo condominio (B → A → B). Presupuesto
y comunicaciones se remontan por contexto para descartar su estado interno.
Los callbacks de aprobación presupuestal también verifican la visita y el condominio
de origen antes de actualizar el estado compartido; un presupuesto de A no habilita
la emisión desde B aunque su aprobación termine después de cambiar de contexto.
Una petición ya enviada conserva su destino original; su respuesta no altera la
pantalla del nuevo contexto. No se promete cancelar una operación ya recibida por API.

## Casos añadidos

`src/tests/integration/test_aislamiento_con77_db.py` comprueba:

- 96 intentos cruzados (32 operaciones por Junta/Auditor/Residente), por ruta,
  query y body en unidades del portal,
  estructura, usuarios, áreas, disponibilidad, reservas, pagos, vouchers, resultados,
  notificaciones, condiciones de pago, presupuestos, conceptos, fondos y exports.
- Lecturas legítimas de A y B, acceso global de SuperAdmin con selección explícita,
  y residente con asignación en ambos condominios sin heredar vínculos del otro contexto.
- Modificación válida de condiciones por Junta y rechazo de escrituras del Auditor.
- Vínculo responsable y área de otro contexto no utilizables en operaciones de A.
- Revocación real del Auditor y rechazo del token previo en rutas financieras y archivos.
- Reporte aprobado del edificio propio sin el detalle privado de las unidades,
  exportaciones PDF/DOCX autorizadas y rechazo de exportaciones ajenas.
- Huella de todas las tablas ORM y de los archivos de vouchers sin cambios tras
  los intentos denegados, incluyendo auditorías, outbox, saldos y versiones.

`frontend/e2e/con77_aislamiento.py` usa Chromium sobre Next.js local con API
interceptada. Verifica borradores y respuestas tardías de la interfaz; **no sustituye
las pruebas PostgreSQL ni acredita correo real**. Se comprobó que falla sobre el
código original de `develop` porque conserva «Borrador privado A» al seleccionar B,
y pasa sobre el código corregido.

## Reproducción local

Docker Desktop debe estar en funcionamiento. Esta base es efímera, exclusiva de
pruebas y expuesta solo en localhost; las credenciales siguientes son de prueba.
No usar el `.env` operativo ni Supabase como destino de estas pruebas.

```powershell
docker run --detach --name condomanager-con77-postgres --publish 127.0.0.1:55477:5432 --env POSTGRES_USER=con77 --env POSTGRES_PASSWORD=con77_local_test --env POSTGRES_DB=con77_test --tmpfs /var/lib/postgresql/data postgres:16-alpine

$con77Url = 'postgresql+asyncpg://con77:con77_local_test@127.0.0.1:55477/con77_test'
$env:DATABASE_URL = $con77Url
$env:CON13_TEST_DATABASE_URL = $con77Url
$env:CON04_TEST_DATABASE_URL = $con77Url
$env:CON05_TEST_DATABASE_URL = $con77Url
$env:CON06_TEST_DATABASE_URL = $con77Url
$env:CON39_TEST_DATABASE_URL = $con77Url
$env:CON46_TEST_DATABASE_URL = $con77Url
$env:CON73_TEST_DATABASE_URL = $con77Url
.\.venv\Scripts\python.exe -X utf8 -m pytest -q --cov
.\.venv\Scripts\python.exe -X utf8 scripts/verify_sdd_compliance.py
```

Preparar las dependencias declaradas de desarrollo (`pip install -e '.[dev]'`).
En este equipo faltaban `python-docx`, `reportlab` y `pytest-cov`; además pytest
9.1 no cumplía el límite del proyecto. Se completó el entorno local con pytest 9.0.3.
No se cambió `pyproject.toml` por estas instalaciones.

Frontend, desde `frontend/`:

```powershell
node --test tests/*.test.mjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/next/dist/bin/next lint
node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3077
```

Con ese servidor activo, desde la raíz y en otra terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -X utf8 frontend/e2e/con77_aislamiento.py
```

Los XML y logs se mantienen en `tmp/`, ignorado por Git. La ejecución no necesita
Graphify: `graphify-out/` es un índice/caché de relaciones del código, ya retirado
del seguimiento en `c1050ee` e ignorado por `.gitignore`.

## Verificación y límites

| Verificación | Resultado |
|---|---|
| CON-77 con PostgreSQL local, versión final | **15 aprobadas**, 0 fallas, 0 omitidas; 93,59 s |
| Pruebas frontend (`node --test`) | **22 aprobadas**, 0 fallas |
| Chromium | Borradores, B → A → B, respuesta tardía y aprobación de A que termina estando en B: aprobados |
| TypeScript (`tsc --noEmit`) y ESLint | Aprobados |
| Verificador SDD | Aprobado |
| Ruff y formato de los archivos nuevos | Aprobados |
| Regresión backend anterior a CON-77 | **651 aprobadas**, 0 fallas, 0 omitidas |
| Cobertura medida en la ejecución general | **92,21 %**; mínimo 80 % |

La ejecución final específica está en `tmp/con77-postgres-verificado.xml`.
El caso de reporte aprobado se ajustó para enviar la versión requerida al aprobar
y exportar con la versión que devuelve el servidor. Sus fallos previos eran de la
solicitud de prueba, no una modificación de los controles de versión de producción.
Las 15 pruebas se volvieron a ejecutar juntas después del ajuste.

La ejecución general en Linux comenzó antes del ajuste final de esa solicitud:
su salida original es **665 aprobadas y 1 fallida**, exclusivamente el caso nuevo
de reporte aprobado. No se presenta esa ejecución como una corrida completamente
verde. La comprobación posterior de las 15 pruebas de CON-77 es la que acredita
el archivo de pruebas definitivo. Las 651 pruebas anteriores no fallaron ni se
omitieron. Los recuentos separados están en `tmp/con77-resumen.json` y la cobertura
en `tmp/con77-coverage.xml`.

Para la ejecución general se reutilizó la imagen local `condomanager-pr25-tests:local`
(Python 3.12.16, pytest 9.0.3), con el código montado en `/app` en solo lectura,
los resultados en `/evidence` y la red del PostgreSQL efímero. Se definieron
`DATABASE_URL` y `CON13_TEST_DATABASE_URL` hacia `127.0.0.1:5432/con77_test` dentro
de esa red, `COVERAGE_FILE=/evidence/con77.coverage`,
`PYTHONPYCACHEPREFIX=/tmp/con77-pycache` y `PYTHONDONTWRITEBYTECODE=1` para no
reutilizar cachés de bytecode de Windows. El comando de pruebas fue:

```text
python -X utf8 -m pytest -q --cov -p no:cacheprovider --junitxml=/evidence/con77-suite-completa.xml
```

La ejecución final específica de las 15 pruebas se hizo en Windows con Python
3.12.14 y pytest 9.0.3, utilizando el puerto local 55477. El servidor Next.js y
el contenedor PostgreSQL temporal se retiraron al terminar las verificaciones;
Docker Desktop permanece disponible.

`ruff check .` y `ruff format --check .` encuentran observaciones previas en
archivos fuera de CON-77 y en tres generadores de diagramas locales sin seguimiento.
Los archivos nuevos de pruebas pasan Ruff y formato. No se reformatean módulos
ajenos ni se incorporan los diagramas a la rama.

CON-77 permanece pendiente de aceptación final: integrar y volver a probar
identidad/activación y cambios de acceso CON-76/7, estado de cuenta CON-14,
almacenamiento CON-79, eliminación de fuentes en memoria CON-80 y ambiente CON-81,
además de cualquier ruta o permiso nuevo de los demás frentes. El resultado local
solo acredita los casos y el código de este corte; no demuestra ausencia de toda
vulnerabilidad ni certifica la versión final del Sprint 3.

Todo queda local: sin push, PR, despliegue, cambio de estado ni comentarios en Jira.
