# CondoManager

Sistema de gestión de cuotas de mantenimiento, pagos y reservas para condominios. El equipo trabaja con especificaciones en `specs/`, API en FastAPI y un portal web en Next.js.

Despliegue objetivo: [Vercel Hobby + Supabase](docs/procesos/VERCEL-HOBBY.md).
Configuración y código preparados para ensayo; **no acredita un despliegue remoto**.

## Entrega del Sprint 2

> **Código al 18/11/2026:** la base revisada es `22b8f3b`, que integra identidad
> del PR #40. Ver [estado actual y prioridades](docs/sprints/ESTADO-ACTUAL.md).
> Las secciones del Sprint 2 conservan su corte histórico; no son el inventario
> completo de esta rama. Notificaciones reales: proveedor por decidir.

La consolidación local añade filtros/paginación de conciliación y readiness de
PostgreSQL/Redis, elimina memoria productiva de reservas y retira el simulador
`POST /moras/evaluar` con 410. El worker diario SQL mantiene su funcionamiento.
Ver límites y comprobaciones en el inventario enlazado.

El candidato del [PR #25 (`develop` → `main`)](https://github.com/NikoTS04/CondoManager/pull/25) parte de `f49dc55`: incluye el Sprint 2 integrado en el PR #27 (`52b4512`) y la ampliación financiera del PR #28. Esta última incorpora gracia por responsable, prorrateo detallado, mora diaria y fondos por edificio, con migraciones hasta `20261025_0020`. La aprobación, el merge y cualquier publicación conservan su registro propio en GitHub.

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

La [validación del candidato actual](docs/sprints/SPRINT-2-VALIDACION-PR25.md) distingue las nuevas ejecuciones de los resultados históricos de CON-75. La [guía financiera](specs/05-api/prorrateo-mora-reportes.md) explica el alcance prospectivo y los límites de la ampliación. El [Sprint 1](docs/sprints/SPRINT-1.md) se conserva como antecedente; CON-22 y CON-23 se completan e integran en el Sprint 2.

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

El backend ejecuta `alembic upgrade head` antes de iniciar la API. La cabeza del código es `20261113_0021` (identidad): revisar respaldo, revisión y compatibilidad antes de arrancar contra una base existente. El despliegue histórico se recuperó y actualizó a 0020 el 26 de octubre tras respaldo, dos restauraciones de ensayo y validación de datos originales; ver [resultado y límites](docs/sprints/reconciliacion-esquema-20261026.md). Ese antecedente no acredita despliegue de 0021. El reparador [legacy](docs/sprints/reconciliacion-esquema-legacy.md) no adopta estas revisiones financieras. Los fondos se reconocen prospectivamente desde cobros de mora conciliados; no se importa caja histórica.

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

- Vouchers privados locales en Docker; el perfil Hobby usa Supabase Storage privado. Descargas autenticadas en ambos casos; archivos previos no se migran solos. Hobby limita subida y descarga remota a 3 MiB.
- Notificaciones con transporte `SIMULADO`: acredita `ENVIADO`, no entrega física por correo o WhatsApp.
- Invitación, activación por enlace y relevos implementados; recepción real pendiente del proveedor. El alta manual histórica conserva su contrato.
- Una tarifa de reserva no acredita un cobro. Una cancelación con ajuste `PENDIENTE` no acredita devolución ejecutada.
- El rediseño visual y el despliegue automático a producción quedan fuera de esta entrega.

## Documentación y evidencia

- [Entrega consolidada y preparación del merge](docs/sprints/CON-75-entrega-sprint-2.md).
- [Uso de pagos y solvencia](docs/sprints/SPRINT-2-ANDERSON-USO.md), [convergencia de contratos](docs/sprints/CON-72-convergencia.md) y [notificaciones](docs/sprints/CON-32-34-36-37-notificaciones.md).
- [CI/CD](docs/procesos/CI-CD.md), [guía de contribución](CONTRIBUTING.md) y [especificaciones](specs/README.md).

Los comandos y resultados del corte actual se conservan en la [validación del PR #25](docs/sprints/SPRINT-2-VALIDACION-PR25.md); las entregas técnicas anteriores mantienen sus propios cortes. `main` recibe la entrega mediante PR revisado desde `develop`, con los checks aplicables y la aprobación de otro integrante.
