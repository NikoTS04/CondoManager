# Matriz de Trazabilidad Integral (Traceability Matrix)

Esta matriz vincula cada requerimiento de negocio y directiva de automatización con su especificación técnica de dominio, modelo de datos, contrato OpenAPI, escenarios BDD ejecutables, módulo de código fuente y responsable asignado.

---

## Matriz de Trazabilidad de Extremo a Extremo (End-to-End)

### Extensión financiera objetivo (pendiente de implementación)

| Código documental | Regla | Dominio / decisión | Contrato | Aceptación |
|---|---|---|---|---|
| FIN-PRORRATEO | Catálogo, reparto por pisos y 139 unidades, cierre de centavos | `02-domains/01-cuotas/prorrateo-y-mora-diaria.md`, ADR-003 | `05-api/prorrateo-mora-reportes.md` | `04-acceptance-criteria/prorrateo-mora-reportes.feature.md` |
| FIN-MORA-DIARIA | Importe editable default 1 por día/cuota, gracia 0 y fecha bancaria | Mismo dominio, PROC-02/04/05 | Mismo contrato, configuración y devengos | Mismo archivo, escenarios de mora |
| FIN-FONDOS-MORA | Moras cobradas financian gastos sin doble uso | Mismo dominio, PROC-06 | Mismo contrato, fondos y aplicaciones | Mismo archivo, escenarios de cobertura |
| FIN-REPORTE | Llenado, aprobación, PDF/DOCX y visor privado | Mismo dominio, PROC-08/02 | Mismo contrato, reportes y evidencia | Mismo archivo, escenarios de exportación y permisos |

Son códigos de documentación, no tickets asignados ni pruebas ejecutables ya conectadas.


| ID Req. | Funcionalidad de Negocio | Especificación de Dominio (L2) | Contrato API (L3) | Criterio BDD Ejecutable (L4) | Módulo en `src/` | Responsable |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **RES-01 / CON-39** | Catálogo SQL de áreas y condiciones de uso | `02-domains/04-reservas/catalogo-areas.md` | `/api/v1/condominios/{cid}/areas[/{aid}[/estado]]`, `/areas` | `02-domains/04-reservas/features/catalogo_areas.feature` → `src/tests/bdd/test_catalogo_areas_bdd.py` | `src/modules/reservas/areas/`, `frontend/src/features/junta/AreasSection.tsx` | **Jerson** |
| **USR-04 / CON-05** | Tenencia persistente y acceso por departamento real | `02-domains/05-usuarios-rbac/vinculos-departamentos.md` | `/api/v1/condominios/{cid}/usuarios/{uid}/departamentos[/{did}]`, `/cuotas/departamentos` | `02-domains/05-usuarios-rbac/features/vinculos_departamentos.feature` → `src/tests/bdd/test_vinculos_bdd.py` | `src/modules/usuarios/`, `frontend/src/features/junta/VinculosUsuarioSection.tsx` | **Jerson** |
| **REQ-00 / CON-2** | Configuración, selección y aislamiento de condominios | `02-domains/05-usuarios-rbac/spec.md` | `GET /api/v1/condominios`, `POST /api/v1/condominios`, `GET /api/v1/condominios/{condominio_id}` | `02-domains/05-usuarios-rbac/features/condominios.feature` | `src/modules/condominios/` | **Gerardo** |
| **USR-02 / CON-3** | Registro, actividad e importación CSV de edificios y departamentos | `02-domains/05-usuarios-rbac/estructura-inmobiliaria.md` | `/api/v1/condominios/{condominio_id}/edificios`, `/departamentos`, `/importaciones/*` | `02-domains/05-usuarios-rbac/features/estructura.feature` | `src/modules/condominios/estructura/` | **Jerson** |
| **USR-03 / CON-04** | Alta inactiva, login persistente y estado administrado por SuperAdmin | `02-domains/05-usuarios-rbac/alta-administrativa.md` | `/api/v1/condominios/{condominio_id}/usuarios`, `/usuarios/{id}/estado`, `/auth/login`, `/auth/me` | `02-domains/05-usuarios-rbac/features/alta_usuarios.feature` | `src/modules/usuarios/`, `frontend/src/features/junta/UsuariosSection.tsx` | **Jerson** |
| **USR-05 / CON-06** | Asignación, cambio y revocación persistente de roles | `02-domains/05-usuarios-rbac/roles-y-permisos.md` | `GET/PUT/DELETE /api/v1/condominios/{condominio_id}/usuarios/{usuario_id}/rol` | `02-domains/05-usuarios-rbac/features/roles_permisos.feature` → `src/tests/bdd/test_roles_permisos_bdd.py`; `src/tests/integration/test_roles_permisos_db.py` | `src/modules/usuarios/`, `frontend/src/features/junta/RolUsuarioEditor.tsx` | **Jerson** |
| **CUE-01 / CON-9** | Registro, modificación, aprobación y consulta del presupuesto mensual | `02-domains/01-cuotas/spec.md`, `02-processes-and-automations/proc-01-cuotas-mantenimiento.md` | `POST /api/v1/presupuestos`, `PUT /api/v1/presupuestos/{id}`, `POST /api/v1/presupuestos/{id}/aprobar`, `GET /api/v1/condominios/{condominio_id}/presupuestos/{periodo}` | `02-domains/01-cuotas/features/cuotas.feature` | `src/modules/cuotas/presupuestos/` | **Gerardo** |
| **REQ-01 / CUE-03 / CON-11** | Emisión mensual persistente, cierre exacto, idempotencia y outbox | `02-domains/01-cuotas/spec.md` | `POST /api/v1/cuotas/emitir-lote` | `02-domains/01-cuotas/features/emision.feature` → `src/tests/bdd/test_emision_bdd.py`; integración y concurrencia en `src/tests/integration/test_emision_db.py` | `src/modules/cuotas/emision.py`, `worker.py` | **Nicolás (Tarqui)** |
| **REQ-02** | Reporte de comprobante de pago (Yape/CCI) | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/pagos/reportar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-03** | Bandeja de conciliación y validación de pagos | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/pagos/{id}/conciliar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-04** | Motor automático de mora tras periodo de gracia | `02-domains/02-pagos-y-moras/spec.md` | `POST /api/v1/moras/evaluar` | `02-domains/02-pagos-y-moras/features/pagos_y_moras.feature` | `src/modules/pagos/` | **Tarqui** |
| **REQ-05** | Notificaciones automáticas de vencimiento | `02-domains/03-notificaciones/spec.md` | `POST /api/v1/notificaciones/despachar` | `02-domains/03-notificaciones/features/notificaciones.feature` | `src/modules/notificaciones/` | **Alejandro** |
| **REQ-06** | Confirmación de pago y reintentos ante fallos | `02-domains/03-notificaciones/spec.md` | Worker Asíncrono / Eventos | `02-domains/03-notificaciones/features/notificaciones.feature` | `src/modules/notificaciones/` | **Alejandro** |
| **NOT-01 / NOT-03 / NOT-05 / NOT-06 · CON-32 / CON-34 / CON-36 / CON-37** | Avisos de cuotas, resultados de pago y reservas desde el outbox real; reintentos, alertas administrativas y su atención | `02-domains/03-notificaciones/spec.md`, `02-domains/03-notificaciones/delivery-policy.md`, `03-contracts/database/data-dictionary.md` | `GET /api/v1/notificaciones/alertas`, `POST /api/v1/notificaciones/alertas/{alerta_id}/atender`, `POST /api/v1/notificaciones/reenviar/{log_id}` | `02-domains/03-notificaciones/features/notificaciones.feature` → `src/tests/bdd/test_notificaciones_bdd.py`; `src/tests/integration/test_notificaciones_emision_db.py`, `test_notificaciones_pagos_db.py`, `test_alertas_notificaciones_db.py` | `src/modules/notificaciones/`, `frontend/src/features/junta/ComunicadosSection.tsx`; entrega: `docs/sprints/CON-32-34-36-37-notificaciones.md` | **Alejandro** |
| **REQ-07** | Catálogo y calendario de áreas comunes | `02-domains/04-reservas/spec.md` | `GET /api/v1/areas` | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-08** | Bloqueo de reserva por deuda en mora | `02-domains/04-reservas/spec.md` | `POST /api/v1/reservas` | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-09** | Concurrencia y prevención de doble reserva | `02-domains/04-reservas/spec.md` | Bloqueo Pesimista en DB | `02-domains/04-reservas/features/reservas.feature` | `src/modules/reservas/` | **Brandon** |
| **REQ-10** | Directorio de usuarios y perfiles (RBAC) | `02-domains/05-usuarios-rbac/spec.md` | `POST /api/v1/usuarios` | `test_usuarios.py` | `src/modules/usuarios/` | **Junta Directiva** |
| **REQ-11** | Categorización de egresos y facturas | `02-domains/06-egresos-proveedores/spec.md` | `POST /api/v1/egresos` | `test_egresos.py` | `src/modules/egresos/` | **Tesorería** |
| **REQ-12** | Alertas de vencimiento de contratos (30/60 días)| `02-domains/06-egresos-proveedores/spec.md` | Cron Diario `0 1 * * *` | `test_contratos.py` | `src/modules/egresos/` | **Tesorería** |
| **REQ-13** | Mesa de ayuda y tickets de infraestructura | `02-domains/07-tickets-incidencias/spec.md` | `POST /api/v1/tickets` | `test_tickets.py` | `src/modules/tickets/` | **Mantenimiento** |
| **REQ-14** | Dashboard de KPIs y balances mensuales en PDF | `02-domains/08-reportes-kpis/spec.md` | `GET /api/v1/reportes/balance` | `test_reportes.py` | `src/modules/reportes/` | **Junta Directiva** |
| **REQ-15** | Bitácora inmutable de auditoría (7 campos) | `01-architecture/audit-and-traceability.md` | Middleware / Core Hook | `test_audit.py` | `src/core/audit.py` | **Arquitectura Core** |
