# Sprint 2 — Usuarios, pagos, notificaciones y reservas integradas

## Objetivo

Entregar un prototipo integrado en el que los usuarios accedan según su rol y sus departamentos vinculados, reporten comprobantes sin duplicarlos, consulten y reserven áreas comunes según su solvencia y reciban comunicaciones trazables. Los datos y las operaciones del flujo deben persistirse y poder comprobarse después de reiniciar los servicios.

El Sprint 2 contiene **20 elementos: 15 historias de usuario y 5 entregas técnicas**. Los puntos nuevos, las fechas y la capacidad del sprint quedan por definir durante la planificación del equipo.

## Alcance y asignación

| Jira | Historia / entrega | ID funcional | Puntos | Responsable | Dependencias |
|---|---|---|---:|---|---|
| **CON-04** | Crear usuario y habilitar su acceso | USR-03 | Por estimar | **Jerson** | CON-2 y contratos de identidad de CON-72 |
| **CON-05** | Vincular usuarios con departamentos | USR-04 | Por estimar | **Jerson** | CON-3 y CON-04 |
| **CON-06** | Asignar roles y permisos | USR-05 | Por estimar | **Jerson** | CON-2 y CON-04; contrato de identidad vigente |
| **CON-22** | Reportar un comprobante de pago | PAG-01 | 5 | **Anderson** | CON-05 y CON-06; contratos de CON-23, CON-70 y CON-72 |
| **CON-23** | Evitar comprobantes duplicados | PAG-02 | 5 | **Brandon** | Contratos de CON-22, CON-70 y CON-72 |
| **CON-32** | Notificar la emisión de una cuota | NOT-01 | Por estimar | **Alejandro** | CON-05 y CON-11; CON-72 y CON-73 |
| **CON-34** | Comunicar el resultado de un pago | NOT-03 | Por estimar | **Alejandro** | CON-05 y CON-22; resultado persistente de revisión en CON-70; CON-72 y CON-73 |
| **CON-36** | Notificar reservas y otras operaciones | NOT-05 | Por estimar | **Alejandro** | Eventos de CON-41 y CON-46; CON-72 y CON-73; invitaciones de CON-04 diferidas |
| **CON-37** | Reintentar notificaciones fallidas | NOT-06 | Por estimar | **Alejandro** | Contratos de notificaciones de CON-32, CON-34 y CON-36; CON-73 |
| **CON-39** | Administrar el catálogo de áreas comunes | RES-01 | Por estimar | **Jerson** | CON-2 y CON-06; contrato de persistencia de CON-73 |
| **CON-40** | Consultar disponibilidad | RES-02 | Por estimar | **Gerardo** | CON-39; contrato de reservas persistentes de CON-73 |
| **CON-41** | Reservar siendo un departamento solvente | RES-03 | Por estimar | **Brandon** | CON-05, CON-06, CON-40, CON-42, CON-43 y CON-73 |
| **CON-42** | Bloquear reservas por deuda vencida | RES-04 | Por estimar | **Anderson** | Cuotas y deuda persistentes de CON-70; contrato de creación de CON-41 |
| **CON-43** | Evitar reservas simultáneas | RES-05 | Por estimar | **Brandon** | CON-40; contratos de reserva y transacción de CON-41 y CON-73 |
| **CON-46** | Cancelar una reserva | RES-08 | Por estimar | **Gerardo** | CON-41; contratos de cancelación y eventos de CON-72 y CON-73 |
| **CON-70** | Persistir el flujo inicial de cuotas y pagos | Transversal | Por estimar | **Anderson** | Base de CON-3, CON-9, CON-10, CON-11 y CON-13; contratos de CON-22, CON-23 y CON-72 |
| **CON-72** | Consolidar contratos API y reglas de eventos | Transversal | Por estimar | **Gerardo** | Especificaciones vigentes y acuerdos entre las historias del sprint |
| **CON-73** | Persistir áreas, reservas y notificaciones | Transversal | Por estimar | **Nicolás (Tarqui)** | CON-2, CON-3 y CON-72; contratos de catálogo, reservas y notificaciones |
| **CON-74** | Integrar frontend y backend del prototipo | Transversal | Por estimar | **Nicolás (Tarqui)** | CON-72 y contratos funcionales; integración final con CON-70 y CON-73 |
| **CON-75** | Preparar errores y evidencia del prototipo | Transversal | Por estimar | **Gerardo** | CON-72; evidencias de CON-70, CON-73, CON-74 y de las historias funcionales |

- CON-04, CON-05, CON-06 y CON-39 se asignan expresamente a **Jerson**.
- CON-22 conserva a **Anderson** y CON-23 a **Brandon**, según el [Sprint 1](SPRINT-1.md). Las demás asignaciones corresponden al reparto acordado para el Sprint 2.
- Los 5 puntos de CON-22 y los 5 de CON-23 son las estimaciones previas. Deben revisarse contra el trabajo pendiente; no representan una nueva estimación ni el total del Sprint 2.
- Las correspondencias funcionales siguen los títulos del [backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md). Las cinco entregas transversales mantienen las claves indicadas para este sprint, sin inventar historias funcionales adicionales.
- CON-22 y CON-23 se incluyen como **continuidad del Sprint 1**: se retoma el avance disponible y se completa su integración, almacenamiento y protección durable frente a duplicados.
- A diferencia del alcance exclusivamente funcional del Sprint 1, este sprint incorpora expresamente las cinco entregas técnicas solicitadas para cerrar el prototipo.

### Resumen por integrante

| Integrante | Historias de usuario | Entregas técnicas | Foco de trabajo |
|---|---|---|---|
| **Jerson** | CON-04, CON-05, CON-06 y CON-39 | — | Identidad, permisos y catálogo de áreas. |
| **Anderson** | CON-22 y CON-42 | CON-70 | Comprobantes, persistencia financiera y consulta de deuda. |
| **Brandon** | CON-23, CON-41 y CON-43 | — | Deduplicación de pagos y creación segura de reservas. |
| **Alejandro** | CON-32, CON-34, CON-36 y CON-37 | — | Motor común de notificaciones, plantillas y reintentos. |
| **Gerardo** | CON-40 y CON-46 | CON-72 y CON-75 | Disponibilidad, cancelación, coordinación de contratos y evidencia. |
| **Nicolás (Tarqui)** | — | CON-73 y CON-74 | Persistencia de reservas y notificaciones e integración del prototipo. |

El reparto agrupa lógica relacionada y conserva la continuidad del trabajo pendiente. El número de tickets no equivale a la carga: CON-73 y CON-74 abarcan varios módulos. Las estimaciones y el avance real de CON-22 y CON-23 deben revisarse antes de comprometer la capacidad del sprint.

## Dependencias y trabajo en paralelo

Las flechas resumen las dependencias de integración; la columna **Dependencias** detalla los requisitos de cada entrega. Un contrato acordado permite desarrollar y probar en paralelo, aunque la aceptación final exige integrar las implementaciones reales.

```text
Base del Sprint 1: condominio, departamentos, presupuesto, distribución y cuotas
  |
  +--> CON-04 --> CON-05 / CON-06 --> acceso contextual a pagos y reservas
  |
  +--> CON-22 / CON-23 <--> CON-70 --> CON-42 --+
  |                                          |
  +--> CON-39 --> CON-40 ---------------------+--> CON-41 --> CON-46
                     CON-43 -----------------+

CON-41 integra acceso, disponibilidad (CON-40), solvencia (CON-42),
exclusión de horarios (CON-43) y persistencia (CON-73).

CON-11 ------------------> CON-32 --+
CON-22 / CON-70 ----------> CON-34 --+--> CON-37
CON-41 / CON-46 ----------> CON-36 --+

CON-72: contratos API y eventos acordados desde el inicio para todas las líneas
CON-73: persistencia de catálogo, reservas y notificaciones durante su desarrollo
CON-37: recuperación de los envíos fallidos de CON-32 / CON-34 / CON-36
CON-74: integración progresiva de la interfaz con las API
CON-75: pruebas de errores y evidencia durante todo el sprint
```

- **Identidad y acceso:** CON-04 utiliza habilitación manual por SuperAdmin; el administrador establece la contraseña inicial. La invitación y verificación por correo quedan para una evolución posterior. Los vínculos necesitan departamentos existentes y un rol administrativo no exige una relación de tenencia.
- **Pagos:** reporte y deduplicación se desarrollan sobre un contrato compartido y se integran con CON-70. La protección concurrente debe probarse en PostgreSQL, no únicamente en un diccionario local.
- **Reservas:** disponibilidad, solvencia y exclusión de horarios forman parte de una misma operación transaccional al integrarse. CON-42 y CON-43 pueden desarrollar y probar sus reglas antes del cierre de CON-41.
- **Notificaciones:** las plantillas, los adaptadores y los reintentos pueden probarse con eventos de contrato. El cierre exige consumir eventos de operaciones confirmadas y guardar su estado de entrega.
- **Contratos y persistencia:** las referencias a contratos permiten trabajo en paralelo; no obligan a esperar el cierre completo de otra historia. Los contratos se acuerdan primero y la integración persistente se verifica al final.
- **Resultado de pagos:** CON-34 necesita un productor real del resultado de revisión. CON-72 debe identificar su contrato y CON-70 persistir el resultado utilizado por el prototipo. Emitir manualmente un evento de prueba no demuestra esa integración.
- **Base disponible:** se reutilizan el flujo persistente de cuotas y el contrato de cuatro roles ya documentados. El alta de usuarios reales y la persistencia de pagos, reservas y notificaciones tienen sus propios criterios de cierre en este sprint.

### Coordinación y orden de implementación

1. **Contratos mínimos al inicio:** Gerardo coordina CON-72 con cada responsable para acordar identidad, carga de voucher, deduplicación, solvencia, horarios, cancelación y eventos. Los acuerdos se incorporan progresivamente; no es necesario cerrar todo CON-72 antes de comenzar las historias.
2. **Persistencia desde el comienzo:** Anderson inicia CON-70 sobre la base financiera existente y Nicolás inicia CON-73 con los contratos de Jerson, Brandon, Gerardo y Alejandro. Se acuerda quién modifica cada migración, repositorio y restricción para evitar cambios incompatibles.
3. **Cierre conjunto de los pendientes:** Anderson y Brandon integran CON-22 y CON-23 con CON-70. Brandon prioriza ese cierre antes de concentrarse en CON-41 y CON-43; Anderson prepara en paralelo el cálculo de deuda de CON-42, que Brandon integra dentro de la operación de reserva.
4. **Reservas en paralelo:** Gerardo desarrolla CON-40 y prepara CON-46 contra los contratos acordados. Brandon implementa CON-41 y CON-43, coordinando con Gerardo los intervalos y las transiciones de estado. La cancelación se verifica finalmente sobre reservas reales persistidas.
5. **Notificaciones con un motor común:** Alejandro desarrolla las plantillas y los reintentos con eventos de contrato y el repositorio de CON-73. Para cerrar CON-34, Anderson debe integrar una operación real de revisión que produzca el resultado persistido y su evento; Alejandro consume ese resultado sin sustituirlo por datos simulados.
6. **Integración y evidencia continuas:** Nicolás coordina CON-74 y Gerardo coordina CON-75 durante todo el sprint. Cada responsable entrega el frontend aplicable, las pruebas y la evidencia de sus propias historias; ambos coordinadores integran los recorridos y reúnen los resultados con apoyo de Alejandro en QA. Las pantallas, las pruebas y las correcciones no se acumulan para una sola persona al final.

## Reglas comunes del sprint

- **Roles canónicos:** `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR` y `RESIDENTE`. Propietario, copropietario e inquilino se determinan por `usuario_departamentos.tipo_relacion`, no por roles adicionales.
- **Autorización:** toda operación protegida valida rol, condominio y, cuando corresponda, vínculo activo con el departamento identificado por UUID. `AUDITOR` tiene acceso de consulta y recibe rechazo al intentar escribir.
- **Sesiones:** altas, activaciones y cambios de permisos deben integrarse con la autenticación. Se define y verifica cómo deja de tener acceso una sesión cuyo rol o vínculo fue revocado.
- **Persistencia:** las pruebas de aceptación consultan los registros desde una nueva sesión después del commit y comprueban su conservación tras reiniciar los servicios pertinentes.
- **Importes:** cálculos con `Decimal` y tipos SQL de precisión fija; redondeo contable documentado, sin `float`.
- **Eventos:** una operación no comunica éxito antes de confirmar su transacción. La publicación y el consumo deben tolerar reentregas sin duplicar efectos.
- **Notificaciones:** distinguir registro persistido, envío aceptado por el proveedor y entrega confirmada. Un transporte simulado se identifica como tal en la evidencia.
- **Reglas temporales:** los contratos deben precisar zona horaria, horarios permitidos y límites de cancelación. Para este sprint se toma como base la política vigente de **al menos 24 horas** para cancelaciones voluntarias y se prueba exactamente esa frontera.

## CON-04 — Crear usuario

**Historia:** Como administrador autorizado, quiero registrar usuarios con contraseña inicial y que un SuperAdmin habilite su acceso desde la aplicación.

**Debe incluir:**

- Registro persistente de identidad, nombres, documento y correo, con validación y reglas de unicidad documentadas.
- Alta restringida a usuarios autorizados y al contexto de condominio permitido.
- Contraseña inicial establecida por el administrador y almacenada únicamente mediante hash.
- Cuenta inactiva por defecto en API, ORM y PostgreSQL; estado editable exclusivamente por SuperAdmin desde la aplicación.
- Login persistente y rechazo de cuentas inactivas; desactivar invalida sesiones anteriores y reactivar exige un nuevo login.
- Auditoría atómica del alta y de los cambios reales de estado; rechazo controlado de datos duplicados.
- Invitaciones y verificación por correo previstas para una evolución posterior, independientes del estado administrativo.

**Se considera terminada cuando:** un administrador registra una cuenta inactiva, un SuperAdmin la habilita o deshabilita desde la aplicación y solo una cuenta activa accede con sus credenciales persistidas; los intentos inválidos se rechazan y los cambios quedan auditados. Contrato: [alta administrativa](../../specs/02-domains/05-usuarios-rbac/alta-administrativa.md).

**Trazabilidad:** [USR-03 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#usr-03--crear-e-invitar-usuarios), [dominio de usuarios](../../specs/02-domains/05-usuarios-rbac/spec.md), [PROC-05](../../specs/02-processes-and-automations/proc-05-gestion-usuarios.md), [contrato de identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [seguridad y RBAC](../../specs/01-architecture/security-and-rbac.md).

## CON-05 — Vincular usuarios con departamentos

Contrato: [vínculos persistentes](../../specs/02-domains/05-usuarios-rbac/vinculos-departamentos.md).
Gestión administrativa por contexto, titular previo a inquilinos/copropietarios,
protección del último titular y renovación de sesión en cambios reales. El portal
y la validación de unidades de pagos/reservas utilizan el padrón SQL.
Guion y resultados: [entrega CON-05](CON-05-vinculos-departamentos.md).

**Historia:** Como administrador, quiero vincular propietarios, copropietarios e inquilinos con sus departamentos, para delimitar la información y las operaciones que pueden realizar.

**Debe incluir:**

- Vínculos persistentes entre usuarios y departamentos existentes del contexto autorizado.
- Relaciones `PROPIETARIO_TITULAR`, `COPROPIETARIO` e `INQUILINO`, con estado activo del vínculo.
- Un mismo usuario con varias unidades y distintas relaciones de tenencia según el departamento.
- Protección frente a duplicados del par usuario-departamento y validación de que la unidad tenga un propietario titular conforme al backlog.
- Desactivación del vínculo sin eliminar el historial de pagos, cuotas, reservas o auditoría de la unidad.
- Devolución de UUID, número, relación y estado del vínculo en el contexto de sesión.
- Pruebas de acceso permitido a unidades propias y rechazo a unidades ajenas o con vínculo inactivo, incluida la revocación de sesiones.

**Se considera terminada cuando:** los vínculos se conservan en PostgreSQL, la sesión representa correctamente varias unidades y un usuario solo puede operar sobre los departamentos que tiene autorizados.

**Trazabilidad:** [USR-04 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#usr-04--vincular-usuarios-con-departamentos), [contrato de identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [PROC-05](../../specs/02-processes-and-automations/proc-05-gestion-usuarios.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [criterios de autenticación](../../specs/04-acceptance-criteria/auth-and-rbac.feature.md).

## CON-06 — Asignar roles y permisos

Contrato implementable: [roles y permisos](../../specs/02-domains/05-usuarios-rbac/roles-y-permisos.md).
Gestión por SuperAdmin y Junta según autoridad; revocación lógica de asignaciones,
auditoría atómica y renovación obligatoria de sesiones. SuperAdmin global sigue
provisionado por CLI. BDD: `roles_permisos.feature`.
Guion y resultados: [entrega CON-06](CON-06-roles-permisos.md).

**Historia:** Como administrador autorizado, quiero asignar roles y permisos, para controlar las funciones y los datos que utiliza cada usuario.

**Debe incluir:**

- Asignaciones persistentes de los cuatro roles canónicos, respetando las restricciones del SQL y el contexto de condominio.
- Separación entre el rol de autorización y la relación de tenencia por departamento.
- Validación en backend para consulta y escritura; ocultar un botón no sustituye la autorización.
- Protección contra autoasignación o elevación de privilegios. Un administrador de condominio no puede conceder privilegios globales ni administrar otro condominio.
- Resolución documentada de la asignación persistida por condominio frente al contexto global de sesión de `SUPERADMIN`.
- Sesiones coherentes con el perfil persistido y renovación o invalidación cuando cambian los permisos.
- Auditoría de asignaciones y pruebas de aislamiento, solo lectura de `AUDITOR` y alcance de `RESIDENTE`.

**Se considera terminada cuando:** el rol asignado se refleja en el login, JWT, API e interfaz; un cambio o revocación se aplica de forma verificable y las solicitudes fuera del permiso o condominio se rechazan.

**Trazabilidad:** [USR-05 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#usr-05--asignar-roles-y-permisos), [seguridad y RBAC](../../specs/01-architecture/security-and-rbac.md), [contrato de identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [dominio de usuarios](../../specs/02-domains/05-usuarios-rbac/spec.md), [criterios de autenticación](../../specs/04-acceptance-criteria/auth-and-rbac.feature.md).

## CON-22 — Reportar un comprobante de pago

**Historia:** Como residente, quiero registrar los datos y la evidencia de mi pago, para que la junta pueda validarlo.

**Debe incluir:**

- Departamento autorizado, banco, número de operación, fecha, monto y voucher obligatorio.
- Carga de PNG, JPG o PDF mediante un contrato de subida de archivo acordado en CON-72, con tamaño máximo documentado y validación efectiva del contenido.
- Almacenamiento del archivo en el servicio de objetos y persistencia de una referencia recuperable por los usuarios autorizados.
- Creación del comprobante en `EN_REVISION`, integrado con la deduplicación de CON-23.
- Ninguna modificación de saldos o solvencia por el solo hecho de reportar el comprobante.
- Respuesta `202 Accepted` para una recepción nueva, con identificador persistido, estado y mensaje coherentes con la interfaz.
- Manejo de fallos entre almacenamiento y base de datos, evitando informar éxito sobre un reporte incompleto.

**Se considera terminada cuando:** un residente puede enviar un voucher válido, recuperar su comprobante después de reiniciar la aplicación y consultar su estado; las entradas inválidas o no autorizadas se rechazan sin afectar saldos.

**Trazabilidad:** [alcance previo del Sprint 1](SPRINT-1.md#con-22--reportar-un-comprobante-de-pago), [dominio de pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [PROC-02](../../specs/02-processes-and-automations/proc-02-pagos-y-morosidad.md), [contratos API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml).

## CON-23 — Evitar comprobantes duplicados

**Historia:** Como tesorero, quiero detectar comprobantes repetidos, para impedir la duplicación o reutilización de un pago.

**Debe incluir:**

- Hash determinista `SHA256(condominio_id|banco|numero_operacion|fecha_operacion|monto)`.
- Normalización canónica de banco, operación, fecha y monto decimal con dos posiciones.
- Restricción única durable sobre `idempotency_hash`, también efectiva ante solicitudes concurrentes.
- Reutilización del comprobante propio en revisión, sin crear otro registro, con la respuesta de evaluación definida por la política canónica.
- Conflicto controlado para un comprobante ya conciliado y rechazo de su reutilización en una unidad distinta, sin divulgar datos de otra unidad.
- Alineación del código HTTP y del cuerpo de las respuestas entre API, interfaz y especificaciones mediante CON-72.
- Pruebas con entradas equivalentes, reintentos posteriores a un reinicio y carreras entre sesiones independientes.

**Se considera terminada cuando:** todos los reintentos equivalentes producen un único comprobante persistido y la respuesta diferencia evaluación, conciliación y reutilización no permitida.

**Trazabilidad:** [alcance previo del Sprint 1](SPRINT-1.md#con-23--evitar-comprobantes-duplicados), [política canónica de idempotencia](../../specs/01-architecture/idempotency-and-deduplication.md), [dominio de pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [BDD de pagos](../../specs/02-domains/02-pagos-y-moras/features/pagos_y_moras.feature), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md).

## CON-32 — Notificar la emisión de una cuota

**Historia:** Como residente, quiero recibir el aviso de una nueva cuota, para conocer el monto y la fecha límite de pago.

**Debe incluir:**

- Consumo del evento de cuotas emitidas después del commit del lote de CON-11.
- Resolución de destinatarios a partir de los vínculos y contactos autorizados de cada departamento.
- Plantilla con periodo, departamento, monto, vencimiento y medios de pago.
- Identificación de la cuota, del evento de origen y del canal en el registro persistente de notificación.
- Deduplicación de la entrega lógica ante reentregas del mismo evento, sin alterar los importes emitidos.
- Registro del resultado y derivación a CON-37 cuando el proveedor presenta un fallo temporal.

**Se considera terminada cuando:** emitir un lote confirmado produce los avisos correspondientes, se pueden consultar sus resultados persistidos y reentregar el evento no crea notificaciones lógicas duplicadas.

**Trazabilidad:** [NOT-01 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#not-01--notificar-la-emisión-de-una-cuota), [dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [PROC-03](../../specs/02-processes-and-automations/proc-03-notificaciones.md), [catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md), [entrega de CON-11](SPRINT-1.md#entrega-técnica-con-11--nicolás).

## CON-34 — Comunicar el resultado de un pago

**Historia:** Como residente, quiero recibir el resultado de la revisión de mi comprobante, para saber si fue aprobado, observado o rechazado.

**Debe incluir:**

- Confirmación inicial de recepción del comprobante y comunicaciones diferenciadas por resultado de revisión.
- Lectura del resultado persistido de la operación de origen, nunca de un saldo inventado por la plantilla.
- En aprobación, monto aplicado y saldo resultante; en rechazo u observación, motivo e instrucciones de subsanación.
- Vínculo entre comprobante, departamento, evento, destinatario y registro de notificación.
- Publicación posterior a la confirmación de la operación financiera y ausencia de avisos de éxito si la transacción se revierte.
- Idempotencia de consumo, persistencia de resultados y tratamiento de fallos mediante CON-37.

**Se considera terminada cuando:** el flujo de recepción y revisión utilizado por el prototipo genera la comunicación correcta desde datos persistidos, los reintentos no duplican avisos y la evidencia permite relacionar el resultado con su comprobante.

**Trazabilidad:** [NOT-03 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#not-03--comunicar-el-resultado-de-un-pago), [PROC-02](../../specs/02-processes-and-automations/proc-02-pagos-y-morosidad.md), [dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [máquina de estados de pagos](../../specs/02-domains/02-pagos-y-moras/state-machine.md), [catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md).

## CON-36 — Notificar reservas y otras operaciones

**Historia:** Como usuario, quiero recibir confirmaciones de reservas, cancelaciones, invitaciones y otras operaciones relevantes, para disponer de evidencia de lo ocurrido.

**Debe incluir:**

- Confirmación de reserva con área, fecha, horario, costo y normas de uso.
- Aviso de cancelación con liberación del horario e información del ajuste económico cuando corresponda.
- Plantillas diferenciadas para las operaciones incluidas en el contrato; la invitación de CON-04 se difiere junto con la verificación por correo.
- Registro de destinatario, canal, operación de origen, estado e intentos.
- Consumo idempotente de eventos confirmados y protección de la información privada de otros residentes.
- Integración con la persistencia de CON-73 y los reintentos de CON-37.

**Se considera terminada cuando:** las operaciones del prototipo generan la plantilla correspondiente para el destinatario autorizado y su registro sigue disponible aunque el envío falle o se reinicie el worker.

**Trazabilidad:** [NOT-05 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#not-05--notificar-reservas-y-otras-operaciones), [dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [PROC-03](../../specs/02-processes-and-automations/proc-03-notificaciones.md), [PROC-04](../../specs/02-processes-and-automations/proc-04-reservas-areas-comunes.md), [PROC-05](../../specs/02-processes-and-automations/proc-05-gestion-usuarios.md).

## CON-37 — Reintentar notificaciones fallidas

**Historia:** Como administrador, quiero que los envíos fallidos se reintenten automáticamente, para recuperar comunicaciones afectadas por interrupciones temporales.

**Debe incluir:**

- Clasificación entre fallos temporales y definitivos del proveedor.
- Un intento inicial y hasta tres reintentos con esperas de 2, 10 y 30 minutos, según la política de entrega; el primer reintento incorpora el jitter documentado.
- Persistencia de intentos, próximo reintento, detalle del error e identificador del proveedor cuando exista.
- Recuperación de tareas pendientes después de reiniciar el worker y coordinación entre workers para evitar procesar simultáneamente el mismo envío.
- Ausencia de nuevos envíos para una notificación ya `ENTREGADO`.
- Estado `FALLIDO_PERMANENTE` y alerta administrativa al agotar intentos o detectar un error definitivo.

**Se considera terminada cuando:** una prueba controlada demuestra recuperación de un fallo temporal, ausencia de duplicados y tratamiento visible del fallo definitivo, conservando la evidencia entre reinicios.

**Trazabilidad:** [NOT-06 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#not-06--reintentar-notificaciones-fallidas), [política de entrega y reintentos](../../specs/02-domains/03-notificaciones/delivery-policy.md), [BDD de notificaciones](../../specs/02-domains/03-notificaciones/features/notificaciones.feature), [resiliencia y excepciones](../../specs/01-architecture/resilience-and-exceptions.md).

## CON-39 — Administrar el catálogo de áreas comunes

**Historia:** Como administrador, quiero configurar las áreas comunes, para publicar sus condiciones de uso y reserva.

**Debe incluir:**

- Registro y modificación de nombre, descripción, aforo, horarios permitidos, costo y estado activo.
- Identificación persistente del área y su pertenencia a un condominio.
- Validaciones de aforo, intervalos horarios y costos no negativos con precisión decimal.
- Escritura restringida a la administración autorizada y consulta conforme a la matriz de permisos.
- Desactivación que impida nuevas reservas, conservando las reservas y auditorías históricas.
- Consulta de las áreas activas y sus reglas desde el portal de residentes.
- Contrato y migraciones de los atributos requeridos coordinados con CON-72 y CON-73.

**Se considera terminada cuando:** un administrador puede crear, consultar, modificar y desactivar áreas persistentes de su condominio; un residente consulta el catálogo permitido y no puede reservar un área inactiva.

**Trazabilidad:** [RES-01 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-01--administrar-el-catálogo-de-áreas-comunes), [dominio de reservas](../../specs/02-domains/04-reservas/spec.md), [PROC-04](../../specs/02-processes-and-automations/proc-04-reservas-areas-comunes.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [seguridad y RBAC](../../specs/01-architecture/security-and-rbac.md).

## CON-40 — Consultar disponibilidad

**Historia:** Como residente, quiero consultar fechas y horarios disponibles, para escoger una opción antes de solicitar la reserva.

**Debe incluir:**

- Consulta por área y fecha dentro del condominio autorizado.
- Lectura de reservas confirmadas y bloqueos existentes desde la base de datos.
- Aplicación de los horarios de uso y del estado activo del área.
- Intervalos ocupados o disponibles sin nombres, contactos ni datos privados de los residentes que reservaron.
- Refresco de disponibilidad después de confirmar o cancelar una reserva.
- Contrato explícito de zona horaria y de intervalos, incluyendo el tratamiento de horarios contiguos.

**Se considera terminada cuando:** dos sesiones consultan la misma disponibilidad persistente, una reserva o cancelación modifica el resultado y la consulta no expone datos de unidades ajenas.

**Trazabilidad:** [RES-02 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-02--consultar-disponibilidad), [dominio de reservas](../../specs/02-domains/04-reservas/spec.md), [contrato de identidad y recursos](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml).

## CON-41 — Reservar siendo un departamento solvente

**Historia:** Como residente al día, quiero reservar un área disponible, para utilizar los espacios comunes del condominio.

**Debe incluir:**

- Validación del usuario, su vínculo activo y la pertenencia de la unidad y el área al condominio.
- Consulta de solvencia desde las cuotas y obligaciones persistidas, integrada con CON-42.
- Validación de área activa, fecha y horario permitidos y ausencia de solapamientos mediante CON-43.
- Creación atómica de la reserva `CONFIRMADA`, con identificador persistente, costo aplicable y registro de auditoría.
- Confirmación `201 Created` únicamente después de completar la transacción.
- Solicitud de comunicación a CON-36 mediante el evento acordado en CON-72.
- Rechazo de departamentos desconocidos, inactivos o no autorizados, sin tratarlos por defecto como solventes.

**Se considera terminada cuando:** una unidad autorizada y solvente obtiene una única reserva persistida para un horario válido, mientras que los intentos inválidos se rechazan sin ocupar el turno ni emitir una confirmación exitosa.

**Trazabilidad:** [RES-03 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-03--reservar-siendo-un-departamento-solvente), [dominio de reservas](../../specs/02-domains/04-reservas/spec.md), [PROC-04](../../specs/02-processes-and-automations/proc-04-reservas-areas-comunes.md), [BDD de reservas](../../specs/02-domains/04-reservas/features/reservas.feature), [auditoría](../../specs/01-architecture/audit-and-traceability.md).

## CON-42 — Bloquear reservas por deuda vencida

**Historia:** Como junta directiva, quiero impedir reservas de departamentos con deuda vencida en mora, para aplicar la política de solvencia de manera consistente.

**Debe incluir:**

- Cálculo de deuda vencida exigible desde los registros persistidos de la unidad.
- Evaluación de la solvencia antes de confirmar u ocupar un horario de reserva.
- Rechazo `403` con `DEUDA_MORA_ACTIVA` y un mensaje claro sobre el motivo y saldo vencido autorizado para consulta.
- Ninguna reserva ni notificación de confirmación cuando se aplica el bloqueo.
- Recuperación del permiso cuando una operación confirmada deja a la unidad sin deuda vencida en mora.
- Evaluación independiente por departamento: una unidad morosa no bloquea las otras unidades solventes del mismo usuario.
- Pruebas que distingan un comprobante reportado en revisión de un pago efectivamente aplicado.

**Se considera terminada cuando:** una unidad con deuda en mora no puede reservar, el horario permanece libre tras el rechazo y la cancelación efectiva de la deuda habilita un nuevo intento sin intervención manual sobre el permiso.

**Trazabilidad:** [RES-04 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-04--bloquear-reservas-por-deuda-vencida), [invariante de solvencia](../../specs/02-domains/04-reservas/spec.md), [PROC-02](../../specs/02-processes-and-automations/proc-02-pagos-y-morosidad.md), [BDD de reservas](../../specs/02-domains/04-reservas/features/reservas.feature).

## CON-43 — Evitar reservas simultáneas

**Historia:** Como residente, quiero que un horario solo pueda asignarse una vez, para evitar conflictos con otros usuarios.

**Debe incluir:**

- Exclusión de intervalos solapados de reservas confirmadas para una misma área y fecha.
- Protección transaccional válida incluso cuando todavía no existe ninguna reserva sobre el intervalo; consultar y bloquear solo filas existentes no basta para ese caso.
- Coordinación mediante PostgreSQL que funcione entre sesiones y procesos independientes.
- Respuesta `409` con conflicto controlado para los intentos que pierden la carrera, sin crear reservas duplicadas.
- Pruebas de intervalos idénticos, parcialmente solapados y contiguos según el contrato.
- Prueba de diez solicitudes concurrentes al mismo intervalo con una respuesta `201` y nueve `409`.

**Se considera terminada cuando:** las pruebas concurrentes demuestran una sola reserva persistida y una respuesta controlada para las demás solicitudes, sin depender de un bloqueo exclusivo de la memoria de un worker.

**Trazabilidad:** [RES-05 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-05--evitar-reservas-simultáneas), [concurrencia y bloqueos](../../specs/01-architecture/concurrency-and-locking.md), [estrategia de pruebas](../../specs/04-verification/test-strategy.md), [BDD de reservas](../../specs/02-domains/04-reservas/features/reservas.feature).

## CON-46 — Cancelar una reserva

**Historia:** Como residente, quiero cancelar una reserva dentro del plazo permitido, para liberar el horario cuando ya no vaya a utilizarlo.

**Debe incluir:**

- Validación de la pertenencia de la reserva al departamento y condominio autorizados.
- Anticipación mínima de 24 horas para cancelación voluntaria, con pruebas antes, exactamente en el límite y después del límite.
- Cancelación administrativa solo cuando el rol y el contexto lo permiten; el campo `es_admin` enviado por el cliente no concede privilegios.
- Transición persistente a `CANCELADA`, sin borrar el historial y con liberación inmediata del horario.
- Manejo controlado de cancelaciones repetidas, estados no cancelables y carreras con nuevas solicitudes.
- Auditoría y comunicación de la cancelación mediante CON-36.
- Ajuste compensatorio cuando exista un cobro reembolsable, conforme a la política económica acordada y trazable a la reserva.

**Se considera terminada cuando:** un usuario autorizado puede cancelar dentro del plazo o mediante una intervención administrativa válida, el horario vuelve a estar disponible y quedan persistidos el cambio y cualquier ajuste aplicable.

**Trazabilidad:** [RES-08 del backlog](../producto/Backlog-Jira-Historias-Usuario-CondoManager.md#res-08--cancelar-una-reserva), [máquina de estados](../../specs/02-domains/04-reservas/state-machine.md), [política vigente de permisos](../../specs/01-architecture/security-and-rbac.md), [PROC-04](../../specs/02-processes-and-automations/proc-04-reservas-areas-comunes.md).

## CON-70 — Persistir el flujo inicial de cuotas y pagos

**Objetivo técnico:** disponer de una base durable y coherente para el flujo de cuotas, reporte de pagos y consulta de resultados del prototipo.

**Debe incluir:**

- Reutilización del presupuesto, distribución, lotes, cuotas y aplicaciones de saldo a favor persistidos en el Sprint 1.
- Persistencia de comprobantes, referencia del voucher, estado de revisión y claves de idempotencia de CON-22 y CON-23.
- Integridad entre condominio, departamento, cuota y comprobante, con claves foráneas, restricciones y precisión decimal.
- Persistencia del resultado de revisión utilizado por CON-34 y trazabilidad de sus efectos financieros cuando corresponda al flujo integrado.
- Transacciones que agrupen los cambios relacionados, su auditoría y los eventos que deben publicarse después del commit.
- Migraciones reproducibles que validen las tablas preexistentes y conserven sus datos al adoptar el esquema actual.
- Pruebas de rollback, consulta desde una nueva sesión, recuperación tras reinicio e idempotencia concurrente.

**Se considera terminada cuando:** el recorrido de cuotas y pagos del prototipo puede reconstruirse desde PostgreSQL y almacenamiento de objetos, sin depender del estado de un proceso en memoria ni producir registros duplicados al reintentar.

**Trazabilidad:** [Sprint 1](SPRINT-1.md), [dominio de cuotas](../../specs/02-domains/01-cuotas/spec.md), [dominio de pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [precisión decimal](../../specs/01-architecture/adr/ADR-002-decimal-accounting.md), [idempotencia](../../specs/01-architecture/idempotency-and-deduplication.md).

## CON-72 — Consolidar contratos API y reglas de eventos

**Objetivo técnico:** establecer un contrato único entre módulos, interfaz, persistencia y comunicaciones para integrar el prototipo sin interpretaciones incompatibles.

**Base de implementación:** [contratos del Sprint 2 / CON-72](../../specs/05-api/sprint-2-contratos.md), adoptados para que cada responsable implemente su HU. Incluyen OpenAPI, esquemas, permisos, estados y procedimiento de cambios. El [diagnóstico histórico](../../specs/05-api/con-72-diagnostico-y-propuesta.md) conserva las diferencias de la base anterior.

**Estado de verificación:** por instrucción de Gerardo, esta entrega define contratos sin crear pruebas de software ni ejecutar aplicación, scripts o tests. La adopción por los módulos, validación automatizada y revisión de pares quedan pendientes; no se marca CON-72 como verificada ni terminada por publicar estos archivos.

**Debe incluir:**

- Alineación entre OpenAPI, DTO, ejemplos, documentación y consumo del frontend.
- Contratos de alta y habilitación administrativa de usuarios, vínculos, asignación de roles, comprobantes, catálogo, disponibilidad, reservas y cancelación.
- Decisión explícita del contrato de carga del voucher y de las respuestas para comprobantes nuevos, duplicados en revisión y ya conciliados.
- Catálogo de eventos con productor, consumidor, versión, identificador, contexto y campos requeridos para cuotas, pagos y reservas; invitaciones de CON-04 diferidas.
- Reglas de publicación posterior al commit, reentrega, deduplicación, reintento y conservación de errores.
- Contrato de errores y autorización, zona horaria, límites temporales, estados y representación decimal.
- Resolución de discrepancias documentales: cuatro roles frente a perfiles de tenencia, frontera de cancelación y respuestas de idempotencia.
- Validación automatizada de esquemas, ejemplos y compatibilidad de contratos entre servicios.

**Se considera terminada cuando:** los módulos y la interfaz comparten contratos verificables, cada evento tiene un origen y destino definidos y las diferencias identificadas quedan resueltas en las especificaciones canónicas.

**Trazabilidad:** [contratos API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml), [catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md), [esquemas de eventos](../../specs/03-contracts/events/schemas/), [contrato de identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [matriz de trazabilidad](../../specs/00-core/traceability-matrix.md).

## CON-73 — Persistir áreas, reservas y notificaciones

**Objetivo técnico:** sustituir el almacenamiento temporal de estos módulos por repositorios persistentes que sostengan las reglas del sprint.

**Debe incluir:**

- Migraciones y repositorios de áreas comunes, horarios y reglas necesarias, reservas y registros de notificaciones.
- Relaciones con condominio, departamento, usuario y operación de origen según el modelo acordado.
- Estados de reserva y notificación, intentos, próximo reintento y referencias del proveedor conservados en PostgreSQL.
- Restricciones e índices para consultas de disponibilidad, deduplicación y exclusión concurrente de horarios.
- Persistencia de eventos pendientes o mecanismo equivalente que permita recuperarlos tras interrupciones.
- Adopción y validación de tablas existentes, preservando registros y dependencias del esquema actual.
- Pruebas desde sesiones independientes, reinicios y workers concurrentes, incluyendo reversión transaccional ante fallos.

**Se considera terminada cuando:** las áreas, reservas, comunicaciones y reintentos sobreviven al reinicio de la aplicación y las reglas de disponibilidad e idempotencia se mantienen entre procesos distintos.

**Trazabilidad:** [dominio de reservas](../../specs/02-domains/04-reservas/spec.md), [dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [concurrencia](../../specs/01-architecture/concurrency-and-locking.md), [política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md), [operación y recuperación](../../specs/05-operations/deployment-and-runbooks.md).

## CON-74 — Integrar frontend y backend del prototipo

**Objetivo técnico:** permitir que los recorridos de usuarios, pagos, reservas y comunicaciones funcionen desde la interfaz sobre las API acordadas y los datos persistidos.

**Debe incluir:**

- Configuración de URL de API, autenticación y contexto de condominio para los entornos del prototipo.
- Uso de los cuatro roles, etiquetas de tenencia por unidad y restauración de sesión validada contra el backend.
- Pantallas y acciones para altas, vínculos y permisos según autorización; catálogo administrativo y consulta de áreas por residentes.
- Reporte de voucher con carga real de archivo, consulta del comprobante y manejo de duplicados.
- Disponibilidad, creación y cancelación de reservas, con explicación de mora, conflicto de horario o falta de permisos.
- Consulta de comunicaciones y estados de entrega para los usuarios autorizados.
- Estados de carga, vacío, error y reintento; los fallos de red o autorización no se sustituyen por éxitos simulados.
- Pruebas del recorrido desde navegador y comprobación de que los registros mostrados proceden de la API y persisten tras recargar o reiniciar.

**Se considera terminada cuando:** los perfiles autorizados completan los recorridos del sprint desde la interfaz, el backend aplica los permisos y el resultado puede comprobarse en una sesión posterior.

**Trazabilidad:** [diseño del frontend](../../frontend/DESIGN.md), [contratos API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml), [contrato de identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [seguridad y RBAC](../../specs/01-architecture/security-and-rbac.md), [runbooks](../../specs/05-operations/deployment-and-runbooks.md).

## CON-75 — Preparar errores y evidencia del prototipo

**Objetivo técnico:** demostrar de forma reproducible el funcionamiento del prototipo y su respuesta controlada ante errores e interrupciones.

**Debe incluir:**

- Casos de validación, autenticación, rol insuficiente, unidad ajena, cruce de condominios y vínculo revocado.
- Casos de voucher duplicado, archivo inválido, fallo de almacenamiento, rollback y consulta posterior al commit.
- Casos de mora, área inactiva, conflicto concurrente de reservas y cancelación fuera del plazo.
- Fallo temporal y definitivo del proveedor, recuperación de reintentos y distinción entre registro guardado y mensaje entregado.
- Mensajes coherentes con el contrato, identificadores de operación o correlación y logs sin contraseñas, tokens ni contenido sensible del voucher.
- Datos de prueba y guion de demostración con precondiciones, pasos, resultados esperados y referencia a cada historia.
- Evidencia de pruebas automatizadas, persistencia entre sesiones, reinicio de servicios y concurrencia; capturas o respuestas HTTP como apoyo.
- Instrucciones de arranque y recuperación del entorno, más un registro de incidencias o limitaciones identificadas durante la verificación.

**Se considera terminada cuando:** otro integrante puede ejecutar el guion, reproducir los resultados esperados y localizar evidencia de los casos correctos y de error sin depender de datos ocultos en memoria.

**Trazabilidad:** [estrategia de pruebas](../../specs/04-verification/test-strategy.md), [resiliencia y excepciones](../../specs/01-architecture/resilience-and-exceptions.md), [auditoría](../../specs/01-architecture/audit-and-traceability.md), [datos piloto](../../specs/05-operations/seed-data-spec.md), [operación y recuperación](../../specs/05-operations/deployment-and-runbooks.md), [verificaciones CI/CD](../procesos/CI-CD.md).

## Definición de Terminado del Sprint

Una historia o entrega técnica se considera terminada cuando:

1. Cumple los criterios de aceptación descritos en su sección y conserva la trazabilidad con el backlog y los contratos.
2. Persiste los datos requeridos y demuestra su recuperación desde una nueva sesión y después de reiniciar los servicios pertinentes.
3. Respeta autorización por rol, condominio y vínculo activo, con pruebas de rechazo e invalidación de accesos cuando corresponde.
4. Garantiza transacciones, idempotencia y concurrencia en PostgreSQL para las operaciones que lo requieren.
5. Mantiene importes con precisión decimal y registra auditoría inmutable de las operaciones relevantes con los siete campos mínimos documentados.
6. Publica eventos de operaciones confirmadas y puede recuperar notificaciones pendientes sin duplicar sus efectos.
7. Tiene especificaciones, OpenAPI, esquemas de eventos y documentación de datos actualizados de forma consistente.
8. Incluye las pruebas unitarias, de integración, BDD y de interfaz aplicables, junto con resultados de los checks correspondientes del proyecto.
9. Forma parte de un recorrido demostrable con datos identificables, resultados verificables y errores controlados en CON-75.
10. Pasa la revisión de otro integrante y cuenta con validación funcional de la entrega.

Los responsables quedan definidos en este documento. Las estimaciones pendientes, las fechas, la capacidad disponible y los acuerdos de contrato deben registrarse durante la planificación antes de comprometer la capacidad final del sprint.
