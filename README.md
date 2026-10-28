# CondoManager

Sistema de gestión de cuotas de mantenimiento, pagos y reservas para condominios. El equipo trabaja con especificaciones en `specs/`, API en FastAPI y un portal web en Next.js.

## Entrega del Sprint 2

`develop` integra usuarios, pagos, reservas y notificaciones del Sprint 2 hasta el merge del PR #27 (`52b4512`). Esta documentación prepara su entrega mediante PR de `develop` a `main`; no declara que el merge, el tag o una publicación ya se hayan realizado.

- [Alcance y criterios del Sprint 2](docs/sprints/SPRINT-2.md).
- [Entrega consolidada CON-75: 20 elementos, evidencia y límites](docs/sprints/CON-75-entrega-sprint-2.md).
- [Historial de cambios](CHANGELOG.md).

| Alcance integrado | Historias / entregas |
|---|---|
| Alta con habilitación manual, vínculos por departamento y roles revocables | CON-04, CON-05, CON-06 |
| Voucher privado, deduplicación, revisión persistente y solvencia | CON-22, CON-23, CON-42, CON-70 |
| Catálogo, calendario SQL, creación concurrente y cancelación | CON-39, CON-40, CON-41, CON-43, CON-46 |
| Avisos desde operaciones confirmadas, reintentos y alertas | CON-32, CON-34, CON-36, CON-37 |
| Contratos, persistencia, interfaz y documentación de entrega | CON-72, CON-73, CON-74, CON-75 |

Las pruebas previas reportadas por el equipo se referencian en la entrega consolidada. La preparación documental no vuelve a ejecutarlas ni sustituye la aprobación del PR. El [Sprint 1](docs/sprints/SPRINT-1.md) se conserva como antecedente; CON-22 y CON-23 se completan e integran en este sprint.

## Arranque local con Docker Desktop

Requisitos: Git, Docker Desktop con contenedores Linux y Docker Compose v2. Ejecutar los comandos PowerShell desde la raíz del repositorio. El Compose principal requiere un PostgreSQL accesible y no lo crea automáticamente.

### 1. Configuración

En un checkout nuevo, copiar `.env.example` a `.env`. Si ya existe `.env`, conservarlo y revisar sus valores.

```powershell
Copy-Item .env.example .env
```

Para un entorno local nuevo sin PostgreSQL, crear una base dedicada:

```powershell
docker run --detach --name condomanager-postgres --publish 5432:5432 --env POSTGRES_USER=condo_user --env POSTGRES_PASSWORD=condo_secret --env POSTGRES_DB=condomanager --volume condomanager_postgres:/var/lib/postgresql/data postgres:16-alpine
docker exec condomanager-postgres pg_isready -U condo_user -d condomanager
```

En ejecuciones posteriores, reutilizarla con `docker start condomanager-postgres`. Para esta alternativa, configurar:

| Variable en `.env` | Valor / uso |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://condo_user:condo_secret@host.docker.internal:5432/condomanager` |
| `DATABASE_URL_SYNC` | `postgresql://condo_user:condo_secret@host.docker.internal:5432/condomanager` |
| `JWT_SECRET` | Clave propia para firmar sesiones. |
| `CONDOMINIO_PILOTO_ID` | UUID del contexto demo; vacío utiliza el UUID piloto predeterminado. |
| `DEMO_MODE` | `true` habilita el listado de perfiles demo; el login consulta PostgreSQL. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` para el navegador local. |
| `NEXT_PUBLIC_DEMO_MODE` | `false` para login manual. |

El Compose configura Redis internamente y publica su puerto local en 6380. Las variables `NEXT_PUBLIC_*` se fijan al compilar el frontend. Las credenciales del ejemplo son de desarrollo; `.env` y los vouchers no se versionan.

### 2. API y portal

```powershell
docker compose up -d --build --wait --wait-timeout 180 redis backend frontend
docker compose ps
```

El backend ejecuta `alembic upgrade head` antes de iniciar la API. La cabeza de esta rama es `20261025_0020`: revisar respaldo, revisión y compatibilidad antes de arrancar contra una base existente. El despliegue se recuperó y actualizó a 0020 el 26 de octubre tras respaldo, dos restauraciones de ensayo y validación de datos originales; ver [resultado y límites](docs/sprints/reconciliacion-esquema-20261026.md). El reparador [legacy](docs/sprints/reconciliacion-esquema-legacy.md) no adopta estas revisiones financieras. Los fondos se reconocen prospectivamente desde cobros de mora conciliados; no se importa caja histórica.

| Servicio | Dirección |
|---|---|
| Portal | <http://localhost:3000> |
| Swagger | <http://localhost:8000/docs> |
| Salud | <http://localhost:8000/api/v1/health> |

### 3. Usuarios y datos

Para una instalación sin cuentas, provisionar el SuperAdmin global mediante el CLI interactivo y crear el condominio desde la aplicación:

```powershell
docker compose exec backend python -m scripts.crear_superadmin
```

Para una **base exclusiva de demostración**, la alternativa es cargar el padrón, las cuentas y las áreas persistentes:

```powershell
docker compose exec backend python -m scripts.seed_usuarios_demo
docker compose exec backend python -m scripts.seed_areas_demo
```

El seed conserva las cuentas y áreas existentes. Los perfiles demo están definidos en [usuarios/demo.py](src/modules/usuarios/demo.py): SuperAdmin, Junta, Auditor y residentes. `scripts.seed_condominio_piloto` solo genera y comprueba el dataset; la inserción del padrón la realiza `scripts.seed_usuarios_demo`.

Para preparar la deuda de ejemplo de la unidad 402, ejecutar únicamente en esa base demo:

```powershell
docker compose exec backend python -m scripts.seed_pagos_sprint2_demo --confirmar-datos-demo
```

La solvencia se calcula desde cuotas SQL: una etiqueta demo o un voucher en revisión no cancelan la deuda.

### 4. Workers

Después de preparar los datos y presupuestos que correspondan al entorno:

```powershell
docker compose up -d --build --wait --wait-timeout 180 cuotas-worker pagos-worker notificaciones-worker
```

El worker de cuotas puede emitir periodos pendientes desde el día UTC configurado en `CUOTAS_DIA_EMISION`. El de pagos publica outboxes, mantiene vouchers y recupera moras diarias al arrancar y a las 00:05 de Lima. El de notificaciones consume cuotas, pagos, moras v2 y reservas, y procesa reintentos y alertas. Instalar migración y consumidor compatible antes de activar el productor/worker diario. Ver [alcance financiero y límites](specs/05-api/prorrateo-mora-reportes.md).

## Límites del prototipo

- Vouchers privados en `uploads/vouchers/`, compartidos por backend y worker de pagos mediante volumen. MinIO/S3 queda diferido; descargar requiere autenticación.
- Notificaciones con transporte `SIMULADO`: acredita `ENVIADO`, no entrega física por correo o WhatsApp.
- Alta con contraseña inicial e intervención de SuperAdmin; invitaciones y verificación por correo diferidas.
- Una tarifa de reserva no acredita un cobro. Una cancelación con ajuste `PENDIENTE` no acredita devolución ejecutada.
- El rediseño visual y el despliegue automático a producción quedan fuera de esta entrega.

## Documentación y evidencia

- [Entrega consolidada y preparación del merge](docs/sprints/CON-75-entrega-sprint-2.md).
- [Uso de pagos y solvencia](docs/sprints/SPRINT-2-ANDERSON-USO.md), [convergencia de contratos](docs/sprints/CON-72-convergencia.md) y [notificaciones](docs/sprints/CON-32-34-36-37-notificaciones.md).
- [CI/CD](docs/procesos/CI-CD.md), [guía de contribución](CONTRIBUTING.md) y [especificaciones](specs/README.md).

Los comandos para repetir pruebas se conservan en las entregas técnicas enlazadas. Para este cierre documental se reutilizan los resultados reportados por el equipo, sin una nueva ejecución local. `main` recibe la entrega mediante PR revisado desde `develop`.
