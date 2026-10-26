# CondoManager - Especificaciones Técnicas (Spec-Driven Development de Nivel Empresarial)

## Avance de implementación: prorrateo detallado (0018)

Catálogo contextual, llenado por conceptos, versionado del borrador, aprobación
con snapshot y emisión jerárquica implementados. Reporte por edificio con
previsualización y descarga PDF/DOCX de la misma versión, incluido BORRADOR y
anexo administrativo de cargos/centavos. El residente no recibe anexos ajenos.
El catálogo se registra explícitamente desde la interfaz; no se sembraron gastos
ni fondos históricos. La migración 0018 no se ha aplicado a la base de la aplicación.
Motor diario/reconstrucción bancaria y cobertura con fondos de moras siguen
pendientes; no se habilitan por la existencia del reporte.

Bienvenido a la documentación técnica oficial de **CondoManager**, estructurada bajo una disciplina rigurosa de **Desarrollo Guiado por Especificaciones (Spec-Driven Development - SDD)**.

En este repositorio, las especificaciones técnicas representan la **fuente única de verdad (Single Source of Truth)**. Ningún código se implementa sin un contrato y especificación previa aprobada.

---

## 1. Filosofía y Guardarraíles de SDD en CondoManager

### Ampliación financiera 2026-10-24 (especificada, aún no implementada)
Avance parcial: configuración de mora y visor privado implementados en la rama
de trabajo; el resto de la ampliación financiera sigue pendiente. Ver
[estado de la primera entrega](05-api/prorrateo-mora-reportes.md#avance-de-implementación--primera-entrega).
Las migraciones 0016/0017 deben aplicarse explícitamente al entorno de destino
antes de usar esta versión. Emisión MONTO_DIARIO bloqueada hasta integrar el motor contable.

Segunda entrega: responsable por unidad, gracia individual y snapshot de política
para nuevas cuotas implementados (migración 0017). Verificados en una instancia
PostgreSQL temporal, incluida concurrencia y conservación de snapshots. No se han
aplicado estas migraciones a la base de la aplicación. El motor diario continúa
bloqueado; fondos/prorrateo y exportaciones todavía no están implementados.

- [Prorrateo, catálogo, mora diaria y reportes](02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
- [ADR-003: reparto por pisos](01-architecture/adr/ADR-003-prorrateo-por-pisos.md).
- [Contratos objetivo de API/persistencia](05-api/prorrateo-mora-reportes.md).
- [Aceptación documental pendiente de automatización](04-acceptance-criteria/prorrateo-mora-reportes.feature.md).

Vence el día 10 en Lima; gracia default 0 con excepciones por responsable de pago;
mora editable default 1.00 PEN diaria **por cuota mensual**. Reparto común por pisos
(14/48, 14/48, 10/48, 10/48); edificio 03 entre 139 unidades. Fondos de moras
cobradas financian gastos con trazabilidad. Llenado y exportación PDF/DOCX y visor
privado de evidencia. Documentos de integración anteriores son antecedentes donde
contradigan esta ampliación; no es una migración ni una capacidad ya desplegada.


1. **La especificación precede al código (Spec-First):** Todo cambio en una regla de negocio requiere actualizar primero su especificación en `specs/02-domains/` y sus escenarios BDD correspondientes.
2. **Ciclo de Automatización Estandarizado:** Todo proceso responde a:
   $$\text{Evento} \longrightarrow \text{Evaluación de Reglas} \longrightarrow \text{Decisión} \longrightarrow \text{Acción} \longrightarrow \text{Verificación}$$
3. **Escalabilidad Multi-Edificio:** Diseñado para cualquier condominio con cualquier número de torres, departamentos y esquemas de alícuotas (con **Villa Bonita 3 - 139 departamentos** como piloto inicial).
4. **Precisión Contable Decimal Absoluta (ADR-002):** Prohibición terminante de coma flotante (`float`) en cualquier cálculo financiero.
5. **Auditoría Inmutable (7 Campos):** Todo cambio financiero o de estado registra obligatoriamente los 7 campos inmutables y encadenamiento criptográfico SHA-256.
6. **Invariante de Solvencia:** La morosidad activa bloquea automáticamente el derecho de reserva de áreas comunes.

---

## 2. Mapa Completo de Navegación del Repositorio SDD

```
specs/
├── README.md                                    # Índice maestro y mapa del sistema (este archivo)
│
├── 00-core/                                     # Gobernanza y Fundamentos
│   ├── ubiquitous-language.md                   # Glosario Ubicuo de Dominio (definiciones formales)
│   ├── sdd-methodology-guide.md                 # Guía metodológica del ciclo SDD (L0 a L4)
│   └── traceability-matrix.md                   # Matriz de trazabilidad integral End-to-End
│
├── 01-architecture/                             # Arquitectura de Sistema y Políticas
│   ├── system-overview.md                       # Visión general y escalabilidad multi-edificio
│   ├── tech-stack.md                            # Stack tecnológico consolidado y dependencias
│   ├── automation-engine.md                     # Pipeline Evento-Regla-Decisión-Acción-Verificación
│   ├── security-and-rbac.md                     # Matriz de roles (Admin, Propietario, Inquilino, Auditor)
│   ├── audit-and-traceability.md                # Bitácora inmutable con 7 campos y hashes encadenados
│   ├── concurrency-and-locking.md               # Bloqueos pesimistas (SELECT FOR UPDATE) y carreras
│   ├── idempotency-and-deduplication.md         # Algoritmos de hashes únicos para vouchers bancarios
│   ├── resilience-and-exceptions.md             # Reintentos con backoff y Human-in-the-Loop
│   └── adr/                                     # Architecture Decision Records
│       ├── ADR-001-tech-stack-selection.md      # Selección de Python/FastAPI/Postgres/Next.js
│       └── ADR-002-decimal-accounting.md        # Política de precisión decimal estricta (cero floats)
│
├── 02-domains/                                  # Paquetes Autocontenidos por Dominio de Negocio
│   ├── 01-cuotas/                               # Dominio: Emisión y Cuotas (Anderson)
│   │   ├── spec.md                              # Fórmulas, alícuotas y prorrateos
│   │   ├── state-machine.md                     # Ciclo de vida: EMITIDA -> PENDIENTE -> PAGADA / VENCIDA
│   │   └── features/cuotas.feature              # Criterios BDD ejecutables en Gherkin
│   ├── 02-pagos-y-moras/                        # Dominio: Conciliación y Moras (Tarqui)
│   │   ├── spec.md                              # Vouchers Yape/CCI, bandeja y motor de moras
│   │   ├── state-machine.md                     # Ciclo de vida del comprobante bancario
│   │   └── features/pagos_y_moras.feature       # Criterios BDD ejecutables
│   ├── 03-notificaciones/                       # Dominio: Comunicaciones y Alertas (Alejandro)
│   │   ├── spec.md                              # Matriz de eventos y plantillas multicanal
│   │   ├── delivery-policy.md                   # Estrategia de reintentos exponenciales
│   │   └── features/notificaciones.feature      # Criterios BDD ejecutables
│   ├── 04-reservas/                             # Dominio: Áreas Comunes y Solvencia (Brandon)
│   │   ├── spec.md                              # Catálogo, aforos e invariante de solvencia
│   │   ├── state-machine.md                     # Ciclo de vida de la reserva
│   │   └── features/reservas.feature            # Criterios BDD ejecutables
│   ├── 05-usuarios-rbac/spec.md                 # Condominios, identidad y asignación departamento-residente
│   ├── 06-egresos-proveedores/spec.md           # Clasificación de gastos y alertas a 30/60 días
│   ├── 07-tickets-incidencias/spec.md           # Mesa de ayuda de mantenimiento en áreas comunes
│   └── 08-reportes-kpis/spec.md                 # Métricas de morosidad y balances mensuales en PDF
│
├── 03-contracts/                                # Contratos Técnicos Ejecutables (L3)
│   ├── openapi/
│   │   └── condomanager.openapi.yaml            # Especificación OpenAPI 3.1 formal completa
│   ├── database/
│   │   ├── data-dictionary.md                   # Diccionario de datos columna por columna
│   │   └── schema.sql                           # Script DDL formal de referencia en PostgreSQL 16
│   └── events/
│       ├── domain-events-catalog.md             # Catálogo de eventos asíncronos en Redis
│       └── schemas/                             # Esquemas JSONSchema de payloads
│           ├── cuota-emitida.schema.json
│           ├── pago-conciliado.schema.json
│           ├── mora-aplicada.schema.json
│           └── reserva-confirmada.schema.json
│
├── 04-verification/                             # Estrategia de Calidad y Verificación (L4)
│   ├── test-strategy.md                         # Pirámide de pruebas (Unit, Integration, BDD)
│   └── compliance-checklist.md                  # Checklist de revisión de Pull Requests
│
└── 05-operations/                               # Operaciones y Datos Piloto
    ├── seed-data-spec.md                        # Dataset piloto Villa Bonita 3 (139 departamentos)
    └── deployment-and-runbooks.md               # Procedimientos de arranque y runbooks
```

---

## 3. Asignación de Dominios por Integrante del Equipo

| Módulo / Dominio | Responsable Principal | Directorio de Especificación | Módulo de Código |
| :--- | :---: | :--- | :--- |
| **Cuotas y Alícuotas** | **Anderson** | [`specs/02-domains/01-cuotas/`](./02-domains/01-cuotas/) | `src/modules/cuotas/` |
| **Pagos, Vouchers y Moras** | **Tarqui** | [`specs/02-domains/02-pagos-y-moras/`](./02-domains/02-pagos-y-moras/) | `src/modules/pagos/` |
| **Notificaciones y Alertas** | **Alejandro** | [`specs/02-domains/03-notificaciones/`](./02-domains/03-notificaciones/) | `src/modules/notificaciones/` |
| **Reservas y Solvencia** | **Brandon** | [`specs/02-domains/04-reservas/`](./02-domains/04-reservas/) | `src/modules/reservas/` |
| **Condominios, Usuarios y Roles (RBAC)** | *Junta Directiva* | [`specs/02-domains/05-usuarios-rbac/`](./02-domains/05-usuarios-rbac/) | `src/modules/condominios/`, `src/modules/usuarios/` |
| **Egresos y Proveedores** | *Tesorería* | [`specs/02-domains/06-egresos-proveedores/`](./02-domains/06-egresos-proveedores/) | `src/modules/egresos/` |
| **Mesa de Ayuda (Tickets)** | *Mantenimiento* | [`specs/02-domains/07-tickets-incidencias/`](./02-domains/07-tickets-incidencias/) | `src/modules/tickets/` |
| **Reportería y Balances** | *Junta Directiva* | [`specs/02-domains/08-reportes-kpis/`](./02-domains/08-reportes-kpis/) | `src/modules/reportes/` |

---

## 4. Guía de Flujo de Trabajo en Git

Para la creación de ramas (`feat/PROC-XX`), el estándar de mensajes de commit semánticos y la lista de verificación para Pull Requests, consulta [CONTRIBUTING.md](../CONTRIBUTING.md).
