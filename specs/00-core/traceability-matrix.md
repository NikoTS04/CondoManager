# Matriz de Trazabilidad Integral (Traceability Matrix)

Esta matriz vincula cada requerimiento de negocio y directiva de automatización con su especificación técnica de dominio, modelo de datos, contrato OpenAPI, escenarios BDD ejecutables, módulo de código fuente y responsable asignado.

---

## Matriz de Trazabilidad de Extremo a Extremo (End-to-End)

| ID Req. | Funcionalidad de Negocio | Especificación de Dominio (L2) | Contrato API (L3) | Criterio BDD Ejecutable (L4) | Módulo en `src/` | Responsable |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-00 / CON-2** | Configuración y aislamiento de condominios | `02-domains/05-usuarios-rbac/spec.md` | `POST /api/v1/condominios`, `GET /api/v1/condominios/{condominio_id}` | `02-domains/05-usuarios-rbac/features/condominios.feature` | `src/modules/condominios/` | **Gerardo** |
| **CUE-01 / CON-9** | Registro, modificación, aprobación y consulta del presupuesto mensual | `02-domains/01-cuotas/spec.md`, `02-processes-and-automations/proc-01-cuotas-mantenimiento.md` | `POST /api/v1/presupuestos`, `PUT /api/v1/presupuestos/{id}`, `POST /api/v1/presupuestos/{id}/aprobar`, `GET /api/v1/condominios/{condominio_id}/presupuestos/{periodo}` | `02-domains/01-cuotas/features/cuotas.feature` | `src/modules/cuotas/presupuestos/` | **Gerardo** |
| **REQ-01** | Emisión mensual de cuotas y alícuotas | `02-domains/01-cuotas/spec.md` | `POST /api/v1/cuotas/emitir-lote` | `02-domains/01-cuotas/features/cuotas.feature` | `src/modules/cuotas/` | **Anderson** |
| **REQ-02** | Reporte de comprobante de pago (Yape/CCI) | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/pagos/reportar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-03** | Bandeja de conciliación y validación de pagos | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/pagos/{id}/conciliar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-04** | Motor automático de mora tras periodo de gracia | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/moras/evaluar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-05** | Notificaciones automáticas de vencimiento | `02-domains/03-notificaciones/spec.md` | `POST /api/v1/notificaciones/despachar` | `02-domains/03-notificaciones/features/notificaciones.feature` | `src/modules/notificaciones/` | **Alejandro** |
| **REQ-06** | Confirmación de pago y reintentos ante fallos | `02-domains/03-notificaciones/spec.md` | Worker Asíncrono / Eventos | `02-domains/03-notificaciones/features/notificaciones.feature` | `src/modules/notificaciones/` | **Alejandro** |
| **REQ-07** | Catálogo y calendario de áreas comunes | `02-domains/04-reservas/spec.md` | `GET /api/v1/areas` | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-08** | Bloqueo de reserva por deuda en mora | `02-domains/04-reservas/spec.md` | `POST /api/v1/reservas` | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-09** | Concurrencia y prevención de doble reserva | `02-domains/04-reservas/spec.md` | Bloqueo Pesimista en DB | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-10** | Directorio de usuarios y perfiles (RBAC) | `02-domains/05-usuarios-rbac/spec.md` | `POST /api/v1/usuarios` | `test_usuarios.py` | `src/modules/usuarios/` | **Junta Directiva** |
| **REQ-11** | Categorización de egresos y facturas | `02-domains/06-egresos-proveedores/spec.md` | `POST /api/v1/egresos` | `test_egresos.py` | `src/modules/egresos/` | **Tesorería** |
| **REQ-12** | Alertas de vencimiento de contratos (30/60 días)| `02-domains/06-egresos-proveedores/spec.md` | Cron Diario `0 1 * * *` | `test_contratos.py` | `src/modules/egresos/` | **Tesorería** |
| **REQ-13** | Mesa de ayuda y tickets de infraestructura | `02-domains/07-tickets-incidencias/spec.md` | `POST /api/v1/tickets` | `test_tickets.py` | `src/modules/tickets/` | **Mantenimiento** |
| **REQ-14** | Dashboard de KPIs y balances mensuales en PDF | `02-domains/08-reportes-kpis/spec.md` | `GET /api/v1/reportes/balance` | `test_reportes.py` | `src/modules/reportes/` | **Junta Directiva** |
| **REQ-15** | Bitácora inmutable de auditoría (7 campos) | `01-architecture/audit-and-traceability.md` | Middleware / Core Hook | `test_audit.py` | `src/core/audit.py` | **Arquitectura Core** |
