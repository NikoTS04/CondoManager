# Matriz de Trazabilidad Integral (Traceability Matrix)

Esta matriz garantiza la cobertura total del ciclo de vida del software en **CondoManager**, vinculando cada requerimiento de negocio y directiva de automatización con su especificación técnica, modelo de datos, contrato API, criterios de prueba BDD, módulo de código fuente y responsable del equipo.

---

## Matriz de Trazabilidad de Extremo a Extremo (End-to-End)

| ID Req. Negocio | Funcionalidad / Directiva de Automatización | Especificación SDD | Modelo de Datos | Contrato API | Criterio BDD | Módulo en `src/` | Responsable |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **REQ-01** | Emisión mensual de cuotas, alícuotas y estados | `proc-01-cuotas-mantenimiento.md` | `cuotas_mantenimiento` | `POST /api/v1/cuotas/emitir` | `cuotas-y-moras.feature.md` (Esc. 1) | `src/modules/cuotas/` | **Anderson** |
| **REQ-02** | Reporte de comprobante de pago (Yape/CCI) | `proc-02-pagos-y-morosidad.md` | `comprobantes_pago` | `POST /api/v1/pagos/reportar` | `cuotas-y-moras.feature.md` (Esc. 3) | `src/modules/pagos/` | **Tarqui** |
| **REQ-03** | Bandeja de conciliación y validación de pagos | `proc-02-pagos-y-morosidad.md` | `imputaciones_pago` | `POST /api/v1/pagos/{id}/conciliar`| `cuotas-y-moras.feature.md` (Esc. 4) | `src/modules/pagos/` | **Tarqui** |
| **REQ-04** | Motor automático de mora y corte tras gracia | `proc-02-pagos-y-morosidad.md` | `cuotas_mantenimiento` | `POST /api/v1/moras/evaluar` (Cron) | `cuotas-y-moras.feature.md` (Esc. 2) | `src/modules/pagos/` | **Tarqui** |
| **REQ-05** | Notificaciones automáticas de cuotas y vencimiento | `proc-03-notificaciones.md` | `notificaciones_logs` | `POST /api/v1/notificaciones/despachar` | `notificaciones.feature.md` (Esc. 1) | `src/modules/notificaciones/`| **Alejandro** |
| **REQ-06** | Confirmación de pago y reintentos ante fallos | `proc-03-notificaciones.md` | `notificaciones_logs` | Worker asíncrono (Event-Driven) | `notificaciones.feature.md` (Esc. 2, 3) | `src/modules/notificaciones/`| **Alejandro** |
| **REQ-07** | Catálogo y calendario de áreas comunes | `proc-04-reservas-areas-comunes.md` | `areas_comunes`, `reservas` | `GET /api/v1/areas` | `reservas-areas.feature.md` (Esc. 2) | `src/modules/reservas/` | **Brandon** |
| **REQ-08** | Bloqueo automático de reserva por deuda en mora | `proc-04-reservas-areas-comunes.md` | `reservas`, `cuotas_mantenimiento`| `POST /api/v1/reservas` | `reservas-areas.feature.md` (Esc. 1) | `src/modules/reservas/` | **Brandon** |
| **REQ-09** | Concurrencia y prevención de doble reserva | `proc-04-reservas-areas-comunes.md` | Bloqueo pesimista en DB | `POST /api/v1/reservas` | `reservas-areas.feature.md` (Esc. 4) | `src/modules/reservas/` | **Brandon** |
| **REQ-10** | Directorio y perfiles de usuarios (Admin/Residente) | `proc-05-gestion-usuarios.md` | `usuarios`, `usuario_departamentos`| `POST /api/v1/usuarios` | Manual / Unit test | `src/modules/usuarios/` | **Junta** |
| **REQ-11** | Clasificación de egresos y facturas | `proc-06-egresos-y-proveedores.md` | `gastos_egresos`, `proveedores` | `POST /api/v1/egresos` | Manual / Unit test | `src/modules/egresos/` | **Tesorería** |
| **REQ-12** | Repositorio de contratos y alertas a 30/60 días | `proc-06-egresos-y-proveedores.md` | `contratos_proveedor` | Cron Job diario | Unit test | `src/modules/egresos/` | **Tesorería** |
| **REQ-13** | Mesa de ayuda y tickets de infraestructura | `proc-07-tickets-incidencias.md` | `tickets_incidencias` | `POST /api/v1/tickets` | Manual / Unit test | `src/modules/tickets/` | **Mantenimiento** |
| **REQ-14** | Dashboard de KPIs financieros y balance en PDF | `proc-08-reportes-kpis.md` | Consultas agregadas en DB | `GET /api/v1/reportes/balance` | Unit test | `src/modules/reportes/` | **Junta** |
| **REQ-15** | Bitácora inmutable de auditoría (7 campos) | `audit-and-traceability.md` | `auditoria_logs` | Middleware / Hook de auditoría | Test de integridad SHA-256 | `src/core/audit.py` | **Core** |
