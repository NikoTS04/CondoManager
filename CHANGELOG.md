# Changelog

Cambios relevantes de CondoManager, organizados por entrega. Se registran capacidades y correcciones que afectan al equipo o al uso del sistema, con referencias a sus historias de usuario.

## [Unreleased]

### Candidato de entrega del Sprint 2

Base del candidato: `develop` en `f49dc55` (merge del PR #28), que incluye el Sprint 2 del corte `52b4512` y su ampliación financiera posterior. Entrega mediante [PR #25](https://github.com/NikoTS04/CondoManager/pull/25), sin asignar una nueva versión ni declarar publicación. Alcance en [CON-75](docs/sprints/CON-75-entrega-sprint-2.md) y evidencia actual en [validación del candidato](docs/sprints/SPRINT-2-VALIDACION-PR25.md).

#### Agregado

- **CON-04/05/06:** usuarios persistentes, habilitación manual por SuperAdmin, vínculos por unidad, roles contextuales, auditoría y revocación de sesiones.
- **CON-22/23/70:** reporte multipart con voucher privado local, descarga autenticada, deduplicación durable, revisión y efectos financieros persistentes. Completa la continuidad de pagos trasladada del Sprint 1.
- **CON-39/40/41/42/43/46:** catálogo y calendario SQL con bloqueos, solvencia desde deuda real, exclusión concurrente, reservas y cancelaciones persistentes, auditoría y outbox.
- **CON-32/34/36/37:** avisos de cuotas, recepción/revisión de pagos y reservas, cola durable, consumo idempotente, reintentos y alertas administrativas. Transporte simulado identificado.
- **CON-72/73/74:** contratos adoptados por API y frontend, subsanación de vouchers observados, errores públicos coherentes y persistencia integrada de reservas y comunicaciones.
- **CON-75:** matriz de 20 elementos, guiones y evidencia reportada por el equipo, límites y preparación del merge. Esta consolidación documental no repite pruebas.
- **Ampliación financiera posterior al cierre original:** configuración versionada de mora diaria y gracia por responsable, presupuesto por conceptos, prorrateo jerárquico y documentos PDF/DOCX privados. Conciliación por fecha bancaria con movimientos compensatorios y fondos por edificio basados en moras efectivamente cobradas. Alcance prospectivo detallado en `specs/05-api/prorrateo-mora-reportes.md`; no importa caja histórica.

#### Corregido e integrado

- Grafo Alembic unificado: cabeza del cierre original `20261021_0015`, ampliada hasta `20261025_0020`; restauración de contexto de reservas, bloqueos operativos, auditoría y eventos de confirmación tras integrar las ramas.
- Reconciliación documentada del esquema legacy, conservando los registros originales y adoptando el esquema canónico.
- Healthchecks de vida de workers para el arranque de Docker Compose.
- README, índice de documentos y notas de entrega actualizados al Sprint 2; los resultados históricos conservan su corte y procedencia.
- Compatibilidad de las pruebas BDD: pytest limitado a versiones anteriores a 9.1 mientras pytest-bdd utilice la API de fixtures retirada. Se mantiene la cobertura mínima del 80 %.
- OpenAPI: arrays de condiciones con `items` explícito y descripción de respuesta 422 correctamente citada en YAML; no se relajan las reglas de validación.
- Workflow de contratos CON-72 con la variable de PostgreSQL que resuelven sus fixtures, evitando omisiones de integración.
- Conciliación de pagos legacy: las imputaciones y cobros se persisten antes de los movimientos del fondo que los referencian, dentro de la misma transacción. Se evita un error 500 de clave foránea al aprobar desde una aplicación recién iniciada; el reintento conserva la idempotencia.
- Formato Ruff de los archivos que introducían deuda respecto de `main`, con comprobación de AST conservado; análisis y cachés `graphify-out` retirados del versionamiento.

#### Límites de la entrega

- Vouchers locales privados durante este periodo; S3/MinIO diferidos.
- Notificaciones `SIMULADO`: `ENVIADO` no acredita entrega externa. Invitaciones y verificación por correo diferidas.
- Ajuste de cancelación `PENDIENTE` registra una solicitud, no una devolución ejecutada.
- Rediseño, proveedor externo, despliegue automático y saneamiento de deuda histórica de lint/drift fuera del alcance de este corte.
- La aprobación del PR y sus checks se registran en GitHub; no se declaran realizados por esta actualización documental.

## Antecedente: candidato del Sprint 1

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

En el corte del Sprint 1 ambas historias conservaron su avance, pero **no se consideraron terminadas ni se incluyeron como funcionalidades entregadas**. Su integración posterior se registra en el candidato del Sprint 2 anterior. La recepción de un comprobante en revisión tampoco implica aprobación del pago ni cancelación de la deuda.

### Limitaciones de esta entrega

- Existen componentes de pagos, reservas y notificaciones que utilizan datos en memoria o simulados; su presencia no acredita la entrega de esas historias ni su persistencia.
- La autenticación utiliza cuentas de demostración; la gestión real de altas, vínculos y roles queda fuera del alcance entregado de este corte.
- La migración `20261019_0006` requiere que `cuotas_mantenimiento` no exista al aplicarse. La adopción de esa tabla desde una base preexistente debe resolverse antes de desplegar sobre ese entorno.
- El script de datos piloto verifica el dataset generado, sin insertar el padrón en PostgreSQL. El arranque reproducible y las comprobaciones se detallan en el [README](README.md).
- La publicación está pendiente de los checks y la revisión del PR de cierre. Las deudas de CI se mantienen en [CI-CD.md](docs/procesos/CI-CD.md); no se declara que estén resueltas por esta documentación.

Al publicar `v0.1.0`, mover las notas del candidato a una sección de esa versión con la fecha real de publicación y el enlace al tag aprobado. Mantener `Unreleased` para los cambios de la siguiente entrega.
