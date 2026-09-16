# ADR-001: Selección del Stack Tecnológico (Backend, Base de Datos y Frontend)

## Estado
**Aceptado** (Fecha: 2026-09-16)

## Contexto
El sistema CondoManager gestiona la contabilidad de condominios, emisión de cuotas de mantenimiento, cálculo automático de penalidades por mora, reservas de áreas comunes y conciliación de pagos bancarios (Yape/CCI) para comunidades de residentes. 

Se requiere un stack tecnológico que garantice:
1. Precisión matemática absoluta en cálculos monetarios (cero errores de aproximación decimal por coma flotante).
2. Trazabilidad e inmutabilidad de registros contables (libro mayor y bitácora de auditoría).
3. Concurrencia segura para reservas y prevención de duplicidad de comprobantes bancarios.
4. Desarrollo ágil y modular para un equipo distribuido (Anderson, Tarqui, Alejandro, Brandon).

## Opciones Evaluadas

### Opción 1: Node.js (TypeScript) + Express / NestJS + MongoDB
- *Ventajas:* Un solo lenguaje (TypeScript) en todo el stack.
- *Desventajas:* MongoDB no es nativamente relacional ni idóneo para libros mayores contables con estricta integridad referencial. El manejo de montos en JavaScript requiere librerías como `decimal.js` o `bignumber.js`, las cuales si se omiten accidentalmente en algún punto de la cadena de cálculo generan errores de precisión en el IEEE 754 (`0.1 + 0.2 != 0.3`).

### Opción 2: Python 3.11+ (FastAPI + Pydantic v2) + PostgreSQL 16 + Redis + Next.js (TypeScript)
- *Ventajas:*
  - Python incluye `decimal.Decimal` en la biblioteca estándar, garantizando precisión contable estricta en el núcleo del sistema.
  - FastAPI valida y serializa datos automáticamente con Pydantic v2 y genera contratos OpenAPI 3.0 automáticos, acelerando la metodología SDD.
  - PostgreSQL proporciona transacciones ACID, tipos `NUMERIC(12, 2)`, campos `JSONB` indexables para auditoría y bloqueos pesimistas (`SELECT FOR UPDATE`) para reservas.
  - Next.js con TypeScript proporciona interfaces web optimizadas tanto para móviles (residentes) como para escritorio (administración).
- *Desventajas:* Requiere gestionar dos entornos de ejecución (Python para backend y Node/TypeScript para frontend).

## Decisión
Se adopta la **Opción 2**:
- **Backend:** Python 3.11+ con FastAPI y Pydantic v2.
- **Base de Datos:** PostgreSQL 16 con SQLAlchemy 2.0 Async y Alembic.
- **Colas / Tareas Asíncronas:** Redis 7 con ARQ / APScheduler.
- **Frontend:** Next.js 14 con TypeScript, TailwindCSS y Shadcn UI.

## Consecuencias
- **Positivas:**
  - Garantía de cero pérdida de centavos en la liquidación de cuotas y saldos de 139+ departamentos.
  - Generación instantánea de especificaciones OpenAPI a partir del código, sincronizándose de forma transparente con los contratos SDD.
  - Bloqueo atómico confiable en reservas concurrentes de parrillas y salones.
- **Negativas / Mitigaciones:**
  - Los desarrolladores deben familiarizarse con `Decimal` de Python y con async/await en SQLAlchemy. Se establecen utilidades compartidas en `src/shared/decimal_types.py` para estandarizar el redondeo.
