# Changelog

Cambios relevantes de CondoManager, organizados por entrega. Se registran capacidades y correcciones que afectan al equipo o al uso del sistema, con referencias a sus historias de usuario.

## [Unreleased]

### Candidato de entrega del Sprint 1

Base de implementación: [`ce09564`](https://github.com/NikoTS04/CondoManager/commit/ce09564817d0f73e4375dfaa4a94a03d7ec968d0), merge del PR #9 de emisión de cuotas. Preparación en `release/sprint-1` para la versión propuesta `v0.1.0`. La fecha de publicación, el tag y la Release se registrarán cuando se apruebe y publique la entrega; esta sección no declara una versión ya liberada.

### Agregado

- **CON-2 — Configuración de condominios:** alta, consulta y selección de condominio con moneda, reglas de mora y vencimiento.
- **CON-3 — Estructura inmobiliaria:** registro persistente de edificios y departamentos, activación/desactivación e importación CSV con previsualización y validación por fila.
- **CON-9 — Presupuesto mensual:** creación, modificación y aprobación del presupuesto por condominio y periodo, con autorización y auditoría.
- **CON-10 — Distribución de cuotas:** configuración equitativa o por alícuota, validación de departamentos activos y cálculos con precisión decimal.
- **CON-11 — Emisión de cuotas:** lote transaccional desde presupuesto aprobado y distribución vigente, cierre de centavos y protección contra una segunda emisión del mismo periodo. Incluye ejecución manual autenticada, worker programado, auditoría y outbox de eventos.
- **CON-13 — Saldos a favor:** aplicación del crédito disponible a las cuotas emitidas, con registro de las aplicaciones y protección frente a aplicaciones repetidas.
- Migraciones y pruebas automatizadas del flujo de configuración, estructura, presupuesto, distribución, emisión y saldos; workflows de backend, frontend, especificaciones, seguridad y Docker.
- README raíz con arranque local sobre una base nueva, contexto de usuarios de demostración, recorrido de verificación y comandos de pruebas.

### Cambiado

- Organización del frontend en componentes y secciones para los portales de junta y residentes.
- Contratos OpenAPI, especificaciones de dominio, modelo de datos y escenarios BDD actualizados para las implementaciones integradas del Sprint 1.

### Pendiente del Sprint 1 y trasladado al Sprint 2

| Historia | Responsable | Trabajo pendiente para su cierre |
|---|---|---|
| **CON-22 — Reportar un comprobante de pago** | **Anderson** | Completar carga y almacenamiento real del voucher, persistencia del comprobante e integración con autorización y deduplicación. |
| **CON-23 — Evitar comprobantes duplicados** | **Brandon** | Completar deduplicación durable en PostgreSQL, restricción única y pruebas de reintentos y concurrencia junto con CON-22. |

Ambas historias conservan el avance existente, pero **no se consideran terminadas ni se incluyen como funcionalidades entregadas**. La recepción de un comprobante en revisión tampoco implica aprobación del pago ni cancelación de la deuda.

### Limitaciones de esta entrega

- Existen componentes de pagos, reservas y notificaciones que utilizan datos en memoria o simulados; su presencia no acredita la entrega de esas historias ni su persistencia.
- La autenticación utiliza cuentas de demostración; la gestión real de altas, vínculos y roles queda fuera del alcance entregado de este corte.
- La migración `20261019_0006` requiere que `cuotas_mantenimiento` no exista al aplicarse. La adopción de esa tabla desde una base preexistente debe resolverse antes de desplegar sobre ese entorno.
- El script de datos piloto verifica el dataset generado, sin insertar el padrón en PostgreSQL. El arranque reproducible y las comprobaciones se detallan en el [README](README.md).
- La publicación está pendiente de los checks y la revisión del PR de cierre. Las deudas de CI se mantienen en [CI-CD.md](docs/procesos/CI-CD.md); no se declara que estén resueltas por esta documentación.

Al publicar `v0.1.0`, mover las notas del candidato a una sección de esa versión con la fecha real de publicación y el enlace al tag aprobado. Mantener `Unreleased` para los cambios de la siguiente entrega.
