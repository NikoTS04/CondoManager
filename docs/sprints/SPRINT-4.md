# Sprint 4 — Operación y monitoreo

**Propuesta de reparto para el equipo · 24/11/2026**

El objetivo es que la Junta pueda operar proveedores, contratos, egresos e incidencias desde el portal y que administración pueda investigar y resolver fallos de los procesos automáticos. El Sprint 3 figura cerrado en Jira. El Sprint 4 está activo del **24/11 al 01/12/2026**. De los 18 tickets, Jira registra responsables para 15. **CON-47, CON-48 y CON-49** siguen sin asignación y el plan propone a Brandon. Las **13 historias suman 67 puntos originales** y las **5 tareas técnicas están por estimar**. [Backlog del Sprint 4](https://tarquisoncco2.atlassian.net/issues/?jql=project%20%3D%20CON%20AND%20sprint%20%3D%2069)

## Refinamiento de tickets en Jira

| Tickets | Ajuste propuesto |
|---|---|
| CON-47 | Estimar el incremento pendiente. Ya existen el bloqueo por área, intervalo y motivo, la exclusión de nuevas reservas y la interfaz. La API responde `409 BLOQUEO_AFECTA_RESERVAS` ante reservas confirmadas solapadas. El refinamiento de Jira define la vista previa, la confirmación administrativa, el cierre urgente y el aviso automático. [Implementación actual](../../src/modules/reservas/bloqueos.py) · [CON-47](https://tarquisoncco2.atlassian.net/browse/CON-47) |
| CON-53 a CON-57, CON-66 y CON-68 | Completar la sección de historia de usuario que está vacía. Usar los actores y objetivos del backlog de producto. Precisar permisos, transiciones válidas y un caso de rechazo verificable por historia. [Backlog de producto](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md) |
| CON-66 y CON-86 | Vincularlos como historia y trabajo técnico. CON-66 entrega la vista y el recorrido de resolución. CON-86 aporta la persistencia, evidencia, historial y ejecución de acciones sobre el proceso de origen. Comparten un contrato, un modelo de datos y el recorrido de aceptación. |
| CON-68, CON-82, CON-83 y CON-84 | CON-68 acepta el resultado visible para administración. CON-82 aporta correlación, CON-83 aporta salud y estado de ejecuciones y CON-84 aporta alertas por fallos definitivos. Vincular las dependencias y reutilizar las comprobaciones y alertas existentes. [Salud](../../src/core/health.py) · [Alertas de notificaciones](../../src/modules/notificaciones/alertas.py) |
| CON-50 y CON-85 | CON-50 define los umbrales y destinatarios de contratos. CON-85 integra la tarea con el planificador. Validar los casos de recuperación y renovación descritos en este plan. [PROC-06](../../specs/02-processes-and-automations/proc-06-egresos-y-proveedores.md) |

Los 18 tickets cubren el objetivo del sprint. Conviene conservar sus claves, vincular los trabajos que entregan el mismo recorrido y estimar el esfuerzo pendiente de CON-47 y CON-68 junto con las cinco tareas técnicas. La clasificación y asignación asistidas por IA/RPA corresponden a la mejora futura `TIC-06`. [Alcance de incidencias](../../specs/02-domains/07-tickets-incidencias/spec.md)

## Reglas propuestas para validar por frente

Los encargados pueden empezar por los bloques con criterios claros. Para cada regla propuesta, confirman el comportamiento con el responsable de negocio cuando corresponda, registran el acuerdo en Jira y lo trasladan a la especificación y sus pruebas.

### Caja, egresos y aprobación de pagos · CON-51/52

**Revisan Anderson y Gerardo con Tesorería.** El condominio contrata servicios externos y paga desde su cuenta operativa. El proceso vigente contempla el sustento bancario. Para el nuevo flujo queda definir cómo se conoce el saldo disponible y cuándo se reconoce cada salida. [PROC-06](../../specs/02-processes-and-automations/proc-06-egresos-y-proveedores.md)

- **Origen del saldo.** Usar un saldo inicial conciliado con el estado de cuenta a una fecha de corte. Desde esa fecha, sumar los ingresos efectivamente cobrados y conciliados, como cuotas pagadas, y restar las salidas confirmadas. Las cuotas emitidas aún pendientes siguen siendo por cobrar. Conciliar periódicamente con el banco y contar cada movimiento una vez. El fondo de moras conserva su destino específico para cobertura presupuestal. [Fondos de mora](../../specs/02-domains/01-cuotas/prorrateo-y-mora-diaria.md)
- **Monto pactado y aumento.** Tesorería registra la obligación con el importe pactado y su sustento. Si el proveedor pide más de lo acordado, Tesorería registra el importe solicitado, la justificación y el sustento adicional. El pago con el importe aumentado queda pendiente hasta que lo apruebe otro integrante autorizado de Junta **aunque el total esté dentro del límite habitual**. Por ejemplo, un servicio pactado en S/ 400 que sube a S/ 450 requiere revisar el aumento, incluso con un límite general de S/ 500.
- **Límite de aprobación.** Un importe igual o inferior al límite sigue el flujo habitual de Tesorería si coincide con lo pactado. Por encima del límite, requiere aprobación adicional. Si el importe cambia después de autorizarse, se evalúa de nuevo sobre el nuevo monto.
- **Cuándo se descuenta.** Registrar el egreso y aprobar el importe son pasos previos. Después del pago en el banco, Tesorería adjunta la constancia, fecha y referencia. La confirmación guarda el movimiento, el saldo anterior y posterior y la auditoría juntos. Un reintento devuelve el resultado guardado sin duplicar la salida. Un rechazo conserva el saldo y registra su motivo.

Tesorería debe validar la cuenta o registro de origen, el saldo y la fecha de corte, el límite real, los aprobadores autorizados y quién confirma la constancia. CON-51 puede avanzar con el registro del egreso y su sustento mientras se cierran esas decisiones de CON-52.

### Proveedores y archivos · CON-48/49

**Revisa Brandon con Anderson, Jerson y Nicolás.** Identificar al proveedor con un RUC normalizado y único por condominio, y usar su registro para vincular contratos, egresos e incidencias. Proponer PDF para contratos y pólizas y reutilizar el almacenamiento privado para comprobantes. Junta administra las versiones de sus documentos, el Auditor consulta dentro de su condominio y cada reemplazo conserva el archivo anterior, fecha y actor. Si se mantiene el perfil Vercel Hobby para la demo, usar 3 MiB por archivo como límite inicial propuesto y comprobar las cargas en ese ambiente. [Dominio de egresos](../../specs/02-domains/06-egresos-proveedores/spec.md) · [Perfil Hobby](../procesos/VERCEL-HOBBY.md)

### Incidencias y correo automático · CON-53 a CON-57

**Revisan Gerardo y Jerson con Brandon y Alejandro.** El residente reporta y consulta su propia incidencia. Junta clasifica, prioriza y asigna un responsable y plazo. Si el ticket es inválido, queda `RECHAZADO` con el motivo visible para el reportante y registrado en el historial. Para este sprint, el proveedor externo figura como responsable a partir del directorio y Junta registra en el portal su progreso, evidencias y costos. El residente ve el estado y las actualizaciones publicadas y puede confirmar la solución o reabrir el caso con motivo. Proponer que los costos y sustentos internos sean visibles para Junta y Auditor dentro de su contexto. [PROC-07](../../specs/02-processes-and-automations/proc-07-tickets-incidencias.md) · [RBAC](../../specs/01-architecture/security-and-rbac.md)

**Disponible en la demo local.** CON-53 incluye el registro y el listado en **Residente → Incidencias → Mis reportes**. El residente puede volver a abrir sus propios reportes y consultar la fecha y el estado. CON-54 permite a Junta clasificar, priorizar y rechazar. En caso de rechazo, el motivo aparece en el listado y en el detalle del residente. [Criterios de aceptación](../../specs/04-acceptance-criteria/incidencias.feature.md) · [Contrato API](../../specs/05-api/api-contracts.md#registro-de-incidencias-con-53)

Al confirmar la asignación, el sistema **encola automáticamente** un correo al residente y otro al contacto del proveedor externo registrado. El correo al proveedor incluye el código del ticket, los datos necesarios para atenderlo y el plazo. El residente recibe el estado y la información de seguimiento. Ambos se envían por la cola existente y llevan una referencia a esa asignación para evitar duplicados. Junta puede ver el resultado del aviso y gestionar un contacto faltante o un fallo de entrega. [Cola y correo](../procesos/MAILJET-PRODUCCION.md)

### Reservas afectadas · CON-47

**Revisan Brandon, Alejandro y Gerardo.** Junta del condominio o SuperAdmin elige un cierre programado o urgente y confirma la lista de titulares, departamentos y horarios afectados. El sistema vuelve a consultar las reservas antes de guardar el bloqueo y las cancelaciones. Se encola un correo por reserva para que el titular elija otro turno. El resumen indica cuántas reservas se cancelaron y el estado de los avisos. [Refinamiento en Jira](https://tarquisoncco2.atlassian.net/browse/CON-47)

### Alertas de contratos y recuperación de jobs · CON-50/85

**Revisan Alejandro y Nicolás.** Mantener la revisión diaria prevista a las 01:00 UTC y generar los avisos de 60 y 30 días por vigencia. Si se perdió la ejecución de 60 días y el job vuelve cuando faltan 59, genera ese aviso una sola vez. Si vuelve cuando faltan 29 y ambos estaban pendientes, genera solo el prioritario de 30 y registra el de 60 como omitido por prioridad. Una renovación inicia su propio calendario y conserva el historial de la vigencia anterior. CON-50 define destinatarios, prioridad y recuperación. CON-85 integra el job con bloqueo de concurrencia, deduplicación y registro de ejecución. [PROC-06](../../specs/02-processes-and-automations/proc-06-egresos-y-proveedores.md) · [Jobs existentes](../../src/core/jobs.py)

### Monitoreo y excepciones · CON-66/68/82/83/84/86

**Revisan Nicolás y Alejandro con Gerardo y Jerson.** Proponer que monitoreo muestre API, PostgreSQL y servicios esenciales según el perfil del ambiente, junto con inicio, fin, duración y resultado de los jobs. Redis puede figurar como deshabilitado en un perfil que prescinde de él. Correlacionar las peticiones, ejecuciones y alertas con una referencia común. Generar una alerta por fallo definitivo después de agotar los reintentos aplicables. [Salud y disponibilidad](../../src/core/health.py) · [Jobs existentes](../../src/core/jobs.py)

Para la primera entrega, la bandeja de CON-66/86 reúne un fallo definitivo de correo y uno de job. Junta consulta causa, operación y evidencia autorizada. Puede corregir el contacto y pedir un nuevo envío si el fallo anterior está confirmado, o cerrar el caso con motivo si ya avisó por otro canal. Una aceptación incierta conserva el flujo de revisión existente. Para un job, ofrecer reintento solo cuando el proceso de origen permita repetirlo con seguridad. Cada decisión guarda actor, motivo y resultado real de la acción. [Backlog transversal](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#trv-04--gestionar-una-bandeja-de-excepciones) · [Política de correo](../../specs/02-domains/03-notificaciones/delivery-policy.md)

**CON-66.** En **Junta → Excepciones**, Junta resuelve los fallos de correo de su condominio y SuperAdmin atiende los jobs globales. SuperAdmin puede pedir información a un responsable, cerrar con motivo o poner en cola un reintento del job de notificaciones para el siguiente ciclo. [Escenarios de aceptación](../../specs/04-acceptance-criteria/excepciones.feature.md)

## Reparto propuesto

| Jira | Entrega | Responsable | Revisión principal | Puntos Jira |
|---|---|---|---|---:|
| [CON-47](https://tarquisoncco2.atlassian.net/browse/CON-47) | Completar el tratamiento de reservas afectadas y el aviso de mantenimiento sobre los bloqueos existentes. | Brandon | Alejandro | 5 |
| [CON-48](https://tarquisoncco2.atlassian.net/browse/CON-48) | Directorio contextual con RUC único por condominio y enlaces al historial de contratos, egresos e incidencias. | Brandon | Anderson | 5 |
| [CON-49](https://tarquisoncco2.atlassian.net/browse/CON-49) | Contratos y pólizas privados con vigencia, permisos e historial de versiones. | Brandon | Nicolás | 5 |
| [CON-50](https://tarquisoncco2.atlassian.net/browse/CON-50) | Alertas contractuales de 60 y 30 días con prioridad, destinatarios y deduplicación. | Alejandro | Nicolás | 5 |
| [CON-51](https://tarquisoncco2.atlassian.net/browse/CON-51) | Registro de egresos con categoría, monto decimal, fecha, sustento y proveedor cuando corresponda. | Anderson | Brandon | 5 |
| [CON-52](https://tarquisoncco2.atlassian.net/browse/CON-52) | Aprobación y registro auditable del pago con límite configurable y control de afectación de caja. | Anderson | Gerardo | 8 |
| [CON-53](https://tarquisoncco2.atlassian.net/browse/CON-53) | Formulario de residente que crea un ticket `REGISTRADO` con ID y aviso a administración. | Gerardo | Jerson | 5 |
| [CON-54](https://tarquisoncco2.atlassian.net/browse/CON-54) | Clasificación y prioridad por Junta, urgentes destacados y rechazo con motivo. | Gerardo | Jerson | 3 |
| [CON-55](https://tarquisoncco2.atlassian.net/browse/CON-55) | Asignación con responsable y plazo, transición a `ASIGNADO` y avisos. | Jerson | Gerardo | 3 |
| [CON-56](https://tarquisoncco2.atlassian.net/browse/CON-56) | Seguimiento y resolución con comentarios, evidencias, repuestos, costos e historial. | Jerson | Anderson | 5 |
| [CON-57](https://tarquisoncco2.atlassian.net/browse/CON-57) | Confirmación, calificación y cierre por el residente o reapertura con motivo. | Jerson | Gerardo | 5 |
| [CON-66](https://tarquisoncco2.atlassian.net/browse/CON-66) | Bandeja administrativa común con evidencia, decisiones y resultado visible. | Gerardo | Jerson | 8 |
| [CON-68](https://tarquisoncco2.atlassian.net/browse/CON-68) | Vista de salud y alertas visibles, con componente, operación y referencia de diagnóstico. | Alejandro | Nicolás | 5 |
| [CON-82](https://tarquisoncco2.atlassian.net/browse/CON-82) | Logs estructurados y correlación entre API y ejecución en segundo plano. | Nicolás (Tarqui) | Gerardo | Por estimar |
| [CON-83](https://tarquisoncco2.atlassian.net/browse/CON-83) | Salud por perfil y registro consultable de inicio, fin, duración y resultado de jobs. | Nicolás (Tarqui) | Alejandro | Por estimar |
| [CON-84](https://tarquisoncco2.atlassian.net/browse/CON-84) | Generación y deduplicación de alertas de fallos definitivos con referencia al origen. | Alejandro | Nicolás | Por estimar |
| [CON-85](https://tarquisoncco2.atlassian.net/browse/CON-85) | Orquestación de jobs y workers con locks, idempotencia, recuperación y derivación de fallos finales. | Nicolás (Tarqui) | Alejandro | Por estimar |
| [CON-86](https://tarquisoncco2.atlassian.net/browse/CON-86) | Persistencia de excepciones y ejecución autorizada, trazable y reproducible de sus resoluciones. | Jerson | Gerardo | Por estimar |

| Integrante | Carga con puntos existentes | Primer incremento |
|---|---:|---|
| Brandon | 15 | CON-48 y su contrato de proveedor. En paralelo, llevar el refinamiento de CON-47 a la especificación y sus escenarios. |
| Anderson | 13 | CON-51 con categoría, sustento y asociación a proveedor. Refinar CON-52 con Tesorería. |
| Alejandro | 10 + 1 tarea | Contrato de alertas y eventos de los nuevos flujos. Reusar alertas existentes para CON-84. |
| Gerardo | 16 | CON-53 y CON-54 sobre un modelo de ticket compartido con Jerson. Boceto del contrato de CON-66. |
| Jerson | 13 + 1 tarea | Máquina de estados y permisos con Gerardo. Preparar CON-55 sobre ese contrato. |
| Nicolás (Tarqui) | 3 tareas por estimar | CON-82 y la estructura común de ejecuciones para CON-83. Coordinar el orden de migraciones. |

Estimar la carga de Nicolás y los incrementos compartidos de Alejandro y Jerson antes de comprometer fechas. Brandon aporta el contrato de archivos para egresos e incidencias. Alejandro aporta los contratos de avisos para CON-47, CON-53 y CON-55. La persona que implementa cada ticket entrega sus pruebas y otra persona revisa el PR.

## Orden de implementación

| Etapa | Trabajo que puede avanzar en paralelo | Condición para integrar |
|---|---|---|
| Base | Brandon inicia CON-48. Gerardo y Jerson acuerdan la máquina de incidencias y empiezan CON-53/54. Nicolás empieza CON-82/83 sobre los jobs existentes. Gerardo y Jerson fijan el contrato CON-66/86. Anderson prepara CON-51 contra el contrato de proveedor y adjuntos. | Contratos y casos de aceptación acordados. Coordinar las revisiones de Alembic desde la cabeza vigente para integrar con una sola cabeza. |
| Recorridos | CON-49 y CON-51 consumen CON-48. CON-55 consume CON-53/54 y el directorio para responsables externos. CON-56 y CON-57 se encadenan a la asignación. Brandon completa CON-47 y Alejandro conecta avisos con la cola existente. | Persistencia, permisos y datos de demo por flujo. Coordinar las rutas y cambios compartidos del portal de Junta antes de integrar. |
| Automatización y resolución | CON-52 consume el egreso persistido y el contrato de caja. CON-50 consume contratos e integra su job con CON-85. CON-68 consume CON-83/84. CON-66/86 conectan fallos definitivos de notificaciones y jobs con una resolución trazable. | Jobs idempotentes, recuperación tras fallos y ensayo de una resolución desde el origen hasta el resultado visible. |
| Aceptación | Validar con dos condominios de prueba, PostgreSQL y el portal. Registrar la evidencia por ticket y el commit y ambiente utilizados. | Checks aplicables en verde, revisión de otro integrante y criterio de aceptación reproducible. [CI/CD](../procesos/CI-CD.md) |

La base revisada fue `origin/develop` en `d7c2372`. OpenAPI y Contrato API todavía fallan en ese corte. Registrar la corrección como trabajo separado de mantenimiento y recuperar una base verde para revisar los nuevos PR. La definición de contratos y las ramas independientes pueden avanzar mientras tanto. [Check de OpenAPI](https://github.com/NikoTS04/CondoManager/actions/runs/45468384629/job/138709342398) · [Check de Contrato API](https://github.com/NikoTS04/CondoManager/actions/runs/45468384629/job/138709343305)

## Recorridos mínimos de demostración

| Recorrido | Evidencia para aceptar |
|---|---|
| Mantenimiento | Programar un bloqueo futuro y confirmar un caso urgente con una reserva en curso. Verificar la lista previa, la exclusión de nuevas reservas, el resumen de cancelaciones y avisos, la deduplicación y el aislamiento por condominio. |
| Proveedor y contrato | Crear un proveedor, rechazar el RUC duplicado dentro del mismo condominio y consultar sus vínculos. Guardar un contrato, reemplazar una póliza y recuperar la versión anterior con autorización. Probar la recuperación de alertas a los 59 y 29 días y el nuevo calendario tras una renovación. |
| Egreso y aprobación | Registrar un egreso con sustento. Probar importes por debajo, en y por encima del límite, y un aumento sobre lo pactado que quede por debajo del límite. Verificar el saldo antes y después de confirmar el pago, saldo intacto al rechazar y una sola afectación frente a un reintento. |
| Incidencia | Reportar, clasificar, asignar, avanzar y resolver. Verificar el correo automático al residente y al responsable, incluso si se reintenta la asignación. Probar cierre, reapertura, permisos e historial de adjuntos. |
| Fallo operativo | Ejecutar un job con una referencia de correlación. Provocar un fallo temporal y uno definitivo, demostrar reintento y deduplicación, abrir la excepción desde el portal, aplicar una decisión permitida y confirmar el estado final del proceso original. |

Para cada cambio, actualizar primero la especificación y sus escenarios. Si cambia un contrato público, actualizar OpenAPI y los eventos afectados. Usar `Decimal` para importes y conservar los siete campos de auditoría en mutaciones financieras u operativas, además del actor y el contexto. Verificar permisos entre condominios en rutas, archivos y resoluciones. [Guía de contribución](../../CONTRIBUTING.md) · [Contratos API](../../specs/05-api/api-contracts.md) · [Catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md)
