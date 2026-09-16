# Especificación del Stack Tecnológico Consolidado (Tech Stack)

## 1. Visión y Justificación Tecnológica

La selección del stack tecnológico para **CondoManager** responde directamente a los requisitos críticos identificados en las especificaciones del sistema:
1. **Rigor y Precisión Contable:** Prohibición absoluta de imprecisiones por coma flotante en cuotas, moras y libro mayor.
2. **Alta Concurrencia y Reactividad:** Manejo asíncrono de eventos (notificaciones masivas, subida de comprobantes y bloqueo en tiempo real de áreas comunes).
3. **Escalabilidad Multi-Edificio:** Arquitectura modular y multi-inquilino (*multi-tenant*) con aislamiento lógico.
4. **Experiencia de Usuario Híbrida:** Portal móvil accesible para residentes (Yape y reservas desde smartphones) y dashboard denso en datos para la Junta Directiva en computadoras de escritorio.

---

## 2. Definición del Stack por Capas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CAPA DE PRESENTACIÓN (UI)                          │
│   Next.js 14 (App Router) + TypeScript + TailwindCSS + Shadcn UI + Lucide   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / REST / JSON
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAPA DE SERVICIOS (API)                           │
│     Python 3.11+ + FastAPI + Pydantic v2 + Dependency Injection (Clean)     │
└──────────────┬───────────────────────────────────────────────┬──────────────┘
               │                                               │
               ▼                                               ▼
┌─────────────────────────────┐                 ┌─────────────────────────────┐
│    BASE DE DATOS (ACID)     │                 │   COLA Y TAREAS ASÍNCRONAS  │
│        PostgreSQL 16        │                 │        Redis 7 + ARQ        │
│  - SQLAlchemy 2.0 Async     │                 │  - Notificaciones en fondo  │
│  - Alembic (Migraciones)    │                 │  - Reintentos exponenciales │
│  - Tipos NUMERIC(12,2)      │                 │  - Cron Jobs (APScheduler)  │
│  - Bloqueo Pesimista        │                 │  - Motor de Moras nocturno  │
└──────────────┬──────────────┘                 └─────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALMACENAMIENTO DE ARCHIVOS (S3)                        │
│                 MinIO (Desarrollo) / AWS S3 (Producción)                    │
│      - Vouchers Yape/CCI | Contratos en PDF | Evidencias de Tickets         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detalle Técnico de Componentes

### 3.1 Backend Core: Python 3.11+ con FastAPI
- **¿Por qué Python para CondoManager?**
  - **Manejo Nativo de `decimal.Decimal`:** A diferencia de lenguajes donde la precisión decimal requiere librerías externas o wrappers complejos, Python cuenta con soporte contable de primer nivel según el estándar IEEE 754 / General Decimal Arithmetic Specification.
  - **FastAPI + Pydantic v2:** Genera automáticamente la documentación OpenAPI 3.0 / Swagger en tiempo real, alineándose 100% con la metodología SDD. La validación de tipos y rangos de datos ocurre antes de que la petición toque la lógica de negocio.
  - **Asincronismo Nativo (`async/await`):** Permite procesar cientos de solicitudes de consulta de estados de cuenta simultáneamente con bajo consumo de memoria.

### 3.2 Capa de Persistencia: PostgreSQL 16
- **Tipos de Datos Estrictos:**
  - `NUMERIC(12, 2)` para todo campo monetario (cuotas, egresos, saldos, moras).
  - `UUIDv4` para identificadores primarios globales (previene colisiones y ataques de enumeración secuencial).
  - `JSONB` para los campos `estado_anterior` y `estado_posterior` en `auditoria_logs`.
- **Integridad Concurrente:**
  - Uso de `SELECT FOR UPDATE` en el módulo de reservas (Brandon) para evitar colisiones de horarios entre vecinos.
  - Claves compuestas únicas para evitar duplicidad de comprobantes bancarios (Tarqui).
- **ORM & Migraciones:**
  - **SQLAlchemy 2.0 Async:** Mapeo de entidades con tipado estricto.
  - **Alembic:** Versionamiento riguroso del esquema de base de datos en Git.

### 3.3 Motor de Eventos, Tareas en Segundo Plano y Cron Jobs: Redis 7 + ARQ / Celery
- **ARQ / Celery con Redis:**
  - Despacho asíncrono e inmediato de notificaciones (Alejandro) para que la respuesta de la API no se degrade ante demoras de servidores de correo o APIs de WhatsApp.
  - Manejo de reintentos exponenciales automáticos con persistencia ante reinicios del servidor.
- **APScheduler:**
  - Disparador de eventos temporales:
    - *Día 1 del mes (00:00 UTC):* Emisión masiva de cuotas (Anderson).
    - *Día 23 del mes (00:01 UTC):* Evaluación de moras y corte de gracia (Tarqui).
    - *Diario (01:00 UTC):* Alertas de contratos a 30/60 días (Tesorería).

### 3.4 Frontend: Next.js 14 + TypeScript + TailwindCSS + Shadcn UI
- **¿Por qué Next.js + TypeScript?**
  - **Seguridad de Tipos:** Los DTOs del backend generados por Pydantic pueden exportarse directamente como tipos TypeScript, garantizando que el frontend jamás envíe estructuras de datos inválidas.
  - **Diseño Responsive Móvil/Escritorio:**
    - *Vista Residente (Mobile-First):* Subida de capturas de Yape con un toque, consulta rápida de estado de cuenta y reserva de parrilla.
    - *Vista Junta / Administrador (Desktop-First):* Bandeja de conciliación a dos columnas (extracto bancario vs comprobante) y tablas con filtros avanzados de morosidad.

### 3.5 Almacenamiento de Objetos (Storage): MinIO / S3
- Almacenamiento seguro de activos estáticos con URLs firmadas con expiración (Pre-signed URLs):
  - Comprobantes de pago (PNG, JPG, PDF).
  - Contratos marco de proveedores y pólizas (PDF).
  - Fotos de incidencias y averías (JPEG).

---

## 4. Matriz de Dependencias Consolidadas

| Componente | Paquete / Herramienta | Versión Mínima | Función en CondoManager |
| :--- | :--- | :--- | :--- |
| **Runtime Backend** | Python | `>= 3.11` | Entorno de ejecución principal |
| **Web Framework** | `fastapi` | `>= 0.110.0` | Enrutamiento HTTP, validación y OpenAPI |
| **Validación de Datos** | `pydantic` | `>= 2.6.0` | Esquemas y contratos de entrada/salida |
| **Acceso a Datos** | `sqlalchemy` + `asyncpg` | `>= 2.0.28` | ORM asíncrono para PostgreSQL |
| **Migraciones DB** | `alembic` | `>= 1.13.1` | Evolución y versionamiento de tablas |
| **Cache y Colas** | `redis` + `arq` | `>= 5.0.3` | Mensajería asíncrona y broker |
| **Planificador Cron** | `apscheduler` | `>= 3.10.4` | Tareas programadas de corte y mora |
| **Seguridad JWT** | `python-jose` + `passlib` | `>= 3.3.0` | Tokens de autenticación y hash bcrypt |
| **Runtime Frontend** | Node.js + TypeScript | `>= 20.x` / `>= 5.x` | Entorno frontend y verificación estática |
| **Frontend Framework** | `next` + `react` | `>= 14.x` | Portal web para residentes y administración |
| **Estilos y Componentes**| `tailwindcss` + `shadcn/ui`| `>= 3.4.x` | Sistema de diseño uniforme y accesible |
