# CondoManager

Sistema de gestión de cuotas de mantenimiento, pagos y reservas para condominios. El equipo trabaja con especificaciones en `specs/`, API en FastAPI y un portal web en Next.js.

## Estado de la entrega del Sprint 1

Esta rama `release/sprint-1` prepara la entrega a partir de `ce09564` (merge del PR #9 de emisión de cuotas). La publicación propuesta es `v0.1.0`; su aprobación, tag y GitHub Release están pendientes. El alcance de esta entrega es el siguiente:

| Historia | Funcionalidad | Estado en este corte |
|---|---|---|
| CON-2 | Configurar un condominio y sus reglas generales. | Implementación integrada. |
| CON-3 | Registrar edificios y departamentos, incluyendo importación CSV. | Implementación integrada. |
| CON-9 | Registrar, modificar y aprobar el presupuesto mensual. | Implementación integrada. |
| CON-10 | Configurar distribución equitativa o por alícuota. | Implementación integrada. |
| CON-11 | Emitir cuotas desde el presupuesto aprobado, manualmente o mediante worker. | Implementación integrada. |
| CON-13 | Aplicar saldos a favor durante la emisión, conservando su trazabilidad. | Implementación integrada. |
| CON-22 | Reportar un comprobante de pago con su voucher. | **No terminada; trasladada al Sprint 2. Responsable: Anderson.** |
| CON-23 | Evitar comprobantes duplicados de forma persistente y concurrente. | **No terminada; trasladada al Sprint 2. Responsable: Brandon.** |

Las seis implementaciones integradas deben superar la revisión y los checks del PR de cierre. La presencia de pantallas o endpoints de pagos, reservas y notificaciones no acredita la finalización de esas historias. Los criterios originales están en [SPRINT-1.md](docs/sprints/SPRINT-1.md) y los cambios de esta entrega en [CHANGELOG.md](CHANGELOG.md).

## Arranque local con Docker Desktop

Requisitos: Git, Docker Desktop con contenedores Linux y Docker Compose v2. Los comandos siguientes usan PowerShell desde la raíz del repositorio. Los puertos 3000, 5432, 6380 y 8000 deben estar disponibles.

### 1. Preparar la configuración y PostgreSQL

En un checkout nuevo de `release/sprint-1`, copiar el ejemplo:

```powershell
Copy-Item .env.example .env
```

Si ya existe `.env`, conservarlo y revisar sus valores. El Compose principal **no crea PostgreSQL**. Para un entorno local nuevo, levantar una base dedicada:

```powershell
docker run --detach --name condomanager-postgres --publish 5432:5432 --env POSTGRES_USER=condo_user --env POSTGRES_PASSWORD=condo_secret --env POSTGRES_DB=condomanager --volume condomanager_postgres:/var/lib/postgresql/data postgres:16-alpine
docker exec condomanager-postgres pg_isready -U condo_user -d condomanager
```

Continuar cuando `pg_isready` indique que acepta conexiones. En ejecuciones posteriores se reutiliza el contenedor con `docker start condomanager-postgres`.

En `.env`, configurar:

| Variable | Valor para este entorno |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://condo_user:condo_secret@host.docker.internal:5432/condomanager` |
| `DATABASE_URL_SYNC` | `postgresql://condo_user:condo_secret@host.docker.internal:5432/condomanager` |
| `JWT_SECRET` | Una clave local propia para firmar las sesiones. |
| `CONDOMINIO_PILOTO_ID` | Inicialmente vacío; se completa con el UUID creado por CON-2. |
| `CUOTAS_DIA_EMISION` | `1` por defecto; día UTC de inicio de la emisión mensual, entre 1 y 28. |

`host.docker.internal` permite que la API en Docker Desktop alcance el PostgreSQL publicado en el equipo. Las credenciales del ejemplo son únicamente de desarrollo. No se versiona `.env`.

Este corte debe arrancarse sobre una **base nueva** para reproducir sus migraciones. La revisión `20261019_0006` crea `cuotas_mantenimiento` y no adopta una tabla preexistente; no aplicar este arranque directamente sobre un backup de Supabase con esa tabla.

### 2. Levantar la API y el portal

```powershell
docker compose up --build -d redis backend frontend
docker compose ps
docker compose logs --tail 80 backend
Invoke-RestMethod http://localhost:8000/api/v1/health
```

El contenedor backend ejecuta `alembic upgrade head` antes de iniciar la API. Si falla la migración, revisar sus logs antes de continuar.

| Servicio | Dirección local |
|---|---|
| Portal web | <http://localhost:3000> |
| API interactiva / Swagger | <http://localhost:8000/docs> |
| Salud de la API | <http://localhost:8000/api/v1/health> |

Este arranque utiliza Redis, API y frontend. MinIO no es necesario para demostrar el alcance entregado del Sprint 1; el almacenamiento real de vouchers sigue pendiente en CON-22.

### 3. Preparar el contexto de demostración

Las cuentas disponibles en este corte son de demostración; su definición está en [usuarios/service.py](src/modules/usuarios/service.py). Para iniciar la configuración:

| Perfil de desarrollo | Correo | Contraseña de demostración |
|---|---|---|
| Superadministración | `superadmin@condomanager.pe` | `SuperAdmin123!` |
| Junta directiva | `admin@villabonita3.pe` | `Admin123!` |

1. Iniciar sesión como superadministrador y crear un condominio desde el portal o mediante `POST /api/v1/condominios` en Swagger. En Swagger, obtener el token desde `POST /api/v1/auth/login` y usar **Authorize** con ese token.
2. Copiar el UUID devuelto en `CONDOMINIO_PILOTO_ID` dentro de `.env`.
3. Recrear la API para aplicar el contexto de las cuentas demo:

   ```powershell
   docker compose up -d --force-recreate backend
   ```

4. Cerrar la sesión anterior e iniciar una nueva con la cuenta de junta directiva.

El script `scripts/seed_condominio_piloto.py` verifica un dataset generado de 139 departamentos, pero **no inserta registros en PostgreSQL**. El padrón de esta demostración se registra por CON-3.

## Recorrido para verificar la entrega

Con el condominio creado y la sesión de junta actualizada:

1. **CON-3:** registrar un edificio y departamentos activos. Un caso mínimo son dos departamentos con coeficientes `50.0000` cada uno. La [especificación de estructura](specs/02-domains/05-usuarios-rbac/estructura-inmobiliaria.md) incluye el formato CSV y sus validaciones.
2. **CON-9:** crear un presupuesto para un periodo `YYYY-MM`, indicar monto, moneda y vencimiento, y aprobarlo. Por ejemplo, `100.00` PEN para el padrón anterior.
3. **CON-10:** configurar `EQUITATIVA` mediante `PUT /api/v1/condominios/{condominio_id}/distribucion`, con cuerpo `{"metodo":"EQUITATIVA"}`. También existe `POR_ALICUOTA`, que exige coeficientes activos que sumen `100.0000`.
4. **CON-11:** emitir el mismo periodo desde el portal o con `POST /api/v1/cuotas/emitir-lote`, enviando únicamente `condominio_id` y `periodo`. Sin saldos a favor previos, el ejemplo debe producir dos cuotas de `50.00`. Repetir la emisión debe devolver `409 LOTE_YA_EMITIDO`.
5. Consultar PostgreSQL desde otra sesión para comprobar el lote en `lotes_cuotas`, las cuotas en `cuotas_mantenimiento` y el evento en `eventos_lote_outbox`. Reiniciar la API y repetir la consulta para comprobar persistencia.
6. **CON-13:** ejecutar las pruebas de saldos y emisión indicadas abajo. Los departamentos nuevos parten de saldo cero; el caso con crédito requiere una precondición de saldo a favor y queda cubierto por las fixtures de esas pruebas.

Conservar como evidencia los identificadores, respuestas y resultados de pruebas del caso ejecutado. Algunas vistas de este corte mantienen datos simulados o mecanismos de respaldo local; su apariencia por sí sola no demuestra persistencia.

Para comprobar la emisión programada después de preparar el presupuesto y el padrón:

```powershell
docker compose up --build -d cuotas-worker
docker compose logs --tail 80 cuotas-worker
```

El worker usa UTC, busca periodos pendientes al iniciar y diariamente, y reintenta la publicación del outbox. Puede emitir el mes actual desde el día configurado; no necesita estar activo durante la preparación del ejemplo manual. Los detalles están en el [runbook de CON-11](specs/05-operations/deployment-and-runbooks.md#operación-de-con-11-emisión-mensual).

## Pruebas

Para pruebas fuera de Docker, instalar Python 3.12 y Node.js 20. Desde la raíz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest-cov
.\.venv\Scripts\python.exe -m pytest src/tests/unit -q
```

Las pruebas de persistencia requieren PostgreSQL real y una **base exclusiva de pruebas**. Con el contenedor local del arranque anterior, crearla una sola vez:

```powershell
docker exec condomanager-postgres createdb -U condo_user condomanager_test
$env:CON3_TEST_DATABASE_URL = "postgresql+asyncpg://condo_user:condo_secret@localhost:5432/condomanager_test"
$env:CON13_TEST_DATABASE_URL = $env:CON3_TEST_DATABASE_URL
$env:CON11_TEST_DATABASE_URL = $env:CON3_TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m pytest -q --cov --cov-report=term-missing --junitxml=pytest.xml
```

Sin estas variables, parte de las pruebas de integración y BDD se omite; revisar los casos `skipped` antes de registrar el resultado. Las pruebas crean y eliminan sus esquemas dentro de la base indicada. Para revisar solo la emisión y los saldos:

```powershell
.\.venv\Scripts\python.exe -m pytest src/tests/integration/test_emision_db.py src/tests/integration/test_saldos_favor_db.py src/tests/bdd/test_emision_bdd.py -q
```

Frontend, desde `frontend/`:

```powershell
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

Los workflows y las deudas de verificación están descritos en [CI-CD.md](docs/procesos/CI-CD.md). Antes de publicar, revisar los resultados de la ejecución correspondiente al PR de cierre. En este corte, el check de nombres de rama aún no admite `release/`; el equipo debe resolver esa convención para que `release/sprint-1` pase el check.

## Documentación de trabajo

- [Plan y criterios del Sprint 1](docs/sprints/SPRINT-1.md).
- [Backlog de historias](docs/producto/Backlog-Jira-Historias-Usuario-CondoManager.md).
- [Roles del equipo](docs/equipo/ROLES-EQUIPO.md).
- [Índice de especificaciones](specs/README.md) y [contrato OpenAPI](specs/03-contracts/openapi/condomanager.openapi.yaml).
- [Guía de contribución](CONTRIBUTING.md): especificaciones, pruebas y revisión de pares para los cambios.
- [Historial de cambios](CHANGELOG.md).

`develop` concentra el trabajo en curso; `main` recibe entregas revisadas. El tag y las notas de GitHub Release deben identificar el commit final aprobado, con CON-22 y CON-23 registradas como pendientes del Sprint 2.
