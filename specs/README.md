# CondoManager - Especificaciones Técnicas (Spec-Driven Development)

Bienvenido a la documentación técnica oficial de **CondoManager**, diseñada bajo los principios de **Desarrollo Guiado por Especificaciones (Spec-Driven Development - SDD)**.

En este repositorio, las especificaciones técnicas representan la **fuente única de verdad (Single Source of Truth)** para el diseño arquitectónico, decisiones técnicas, reglas de negocio, autómatas reactivos, contratos de API y criterios de aceptación.

---

## 1. Filosofía de SDD en CondoManager

1. **La especificación precede al código:** Ninguna funcionalidad o cambio de regla de negocio se implementa sin actualizar previamente su documento de especificación.
2. **Ciclo de automatización estandarizado:** Todo proceso automatizado responde a:
   $$\text{Evento} \longrightarrow \text{Evaluación de Reglas} \longrightarrow \text{Decisión} \longrightarrow \text{Acción} \longrightarrow \text{Verificación}$$
3. **Escalabilidad Multi-Edificio:** Diseñado para escalar a cualquier condominio o complejo habitacional con cualquier número de torres, pisos y departamentos.
4. **Trazabilidad Inmutable:** Cada cambio de estado financiero o administrativo deja una huella de auditoría inmutable de 7 campos obligatorios y hash SHA-256 encadenado.
5. **Contratos Desacoplados:** Frontend y Backend interactúan a través de contratos OpenAPI definidos y congelados previamente en las especificaciones.

---

## 2. Mapa Completo de Especificaciones

```
specs/
├── README.md                                    # Índice maestro y guía metodológica (este archivo)
├── traceability-matrix.md                       # Matriz de trazabilidad integral (Req -> Spec -> Código -> QA)
├── 00-adr/                                      # Architecture Decision Records (Registros de Decisiones)
│   └── ADR-001-seleccion-stack-tecnologico.md   # Justificación: Python FastAPI + PostgreSQL + Next.js
├── 01-architecture/                             # Arquitectura transversal y directrices globales
│   ├── system-overview.md                       # Visión del sistema, alcance escalable y principios
│   ├── tech-stack.md                            # Stack tecnológico consolidado y dependencias
│   ├── automation-engine.md                     # Motor de eventos, colas y temporizadores
│   ├── security-and-rbac.md                     # Matriz de roles (Admin, Propietario, Inquilino, Auditor)
│   ├── audit-and-traceability.md                # Bitácora inmutable y control de notas de crédito
│   └── resilience-and-exceptions.md             # Idempotencia, reintentos y Human-in-the-loop
├── 02-processes-and-automations/                # Especificación detallada de procesos de negocio
│   ├── proc-01-cuotas-mantenimiento.md          # Emisión periódica de cuotas (Resp: Anderson)
│   ├── proc-02-pagos-y-morosidad.md             # Validación de pagos y motor de mora (Resp: Tarqui)
│   ├── proc-03-notificaciones.md                # Comunicaciones multicanal y alertas (Resp: Alejandro)
│   ├── proc-04-reservas-areas-comunes.md        # Reservas y bloqueo por morosidad (Resp: Brandon)
│   ├── proc-05-gestion-usuarios.md              # Altas de usuarios, roles y departamentos
│   ├── proc-06-egresos-y-proveedores.md         # Clasificación de gastos y contratos
│   ├── proc-07-tickets-incidencias.md           # Mesa de ayuda de mantenimiento
│   └── proc-08-reportes-kpis.md                 # Balances contables y dashboard de recaudación
├── 03-data-models/                              # Modelado conceptual y esquemas de base de datos
│   ├── domain-entities.md                       # Entidades de dominio y modelo relacional
│   └── state-machines.md                        # Máquinas de estado de Cuotas, Pagos, Reservas
├── 04-acceptance-criteria/                      # Criterios de aceptación (BDD / Gherkin)
│   ├── cuotas-y-moras.feature.md                # Escenarios de prueba de cuotas y penalidades
│   ├── reservas-areas.feature.md                # Escenarios de prueba de reservas y solvencia
│   └── notificaciones.feature.md                # Escenarios de prueba de envíos y reintentos
└── 05-api/                                      # Contratos de API REST e Interfaces
    └── api-contracts.md                         # Endpoints, payloads JSON y códigos de error estándar
```

---

## 3. Matriz de Responsabilidades del Equipo

| Módulo | Documento | Responsable | Entidades Clave | Endpoint Principal |
| :--- | :--- | :---: | :--- | :--- |
| **Cuotas de Mantenimiento** | `proc-01-cuotas-mantenimiento.md` | **Anderson** | `Presupuesto`, `CuotaMantenimiento` | `POST /api/v1/cuotas/emitir-lote` |
| **Pagos y Morosidad** | `proc-02-pagos-y-morosidad.md` | **Tarqui** | `ComprobantePago`, `ImputacionPago` | `POST /api/v1/pagos/reportar` |
| **Notificaciones** | `proc-03-notificaciones.md` | **Alejandro** | `NotificacionLog` | `POST /api/v1/notificaciones/despachar` |
| **Reservas de Áreas Comunes** | `proc-04-reservas-areas-comunes.md` | **Brandon** | `AreaComun`, `ReservaArea` | `POST /api/v1/reservas` |
| **Usuarios y Accesos** | `proc-05-gestion-usuarios.md` | *Junta* | `Usuario`, `UsuarioDepartamento` | `POST /api/v1/usuarios` |
| **Egresos y Proveedores** | `proc-06-egresos-y-proveedores.md` | *Tesorería*| `Proveedor`, `ContratoProveedor` | `POST /api/v1/egresos` |
| **Mesa de Ayuda (Tickets)** | `proc-07-tickets-incidencias.md` | *Mantenimiento*| `TicketIncidencia` | `POST /api/v1/tickets` |
| **Reportería y Balances** | `proc-08-reportes-kpis.md` | *Junta* | `BalanceMensual`, `AuditoriaLog` | `GET /api/v1/reportes/balance` |

---

## 4. Flujo de Trabajo y Ramas

Para conocer la estrategia de ramas (`feat/PROC-XX`), el estándar de mensajes de commit y la lista de verificación para Pull Requests, consulta la guía oficial en [CONTRIBUTING.md](../CONTRIBUTING.md).

