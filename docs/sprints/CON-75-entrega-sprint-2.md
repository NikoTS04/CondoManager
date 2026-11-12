# CON-75 — Entrega consolidada del Sprint 2

Consolidación original: 21/10/2026. Actualización del candidato: 28/10/2026. Coordinación: Gerardo.
Base actual: `develop` en `f49dc55` (PR #28), que incorpora el corte original del PR #27 (`52b4512`). Destino de entrega: [PR #25 de `develop` a `main`](https://github.com/NikoTS04/CondoManager/pull/25).

## Corte actual: Sprint 2 y ampliación financiera

La matriz de 20 elementos conserva el alcance original del sprint. El candidato incluye además política de mora diaria, gracia por responsable, presupuesto por conceptos, prorrateo detallado y PDF/DOCX, conciliación por fecha bancaria y fondos por edificio, con cabeza `20261025_0020`. Sus contratos y límites están en [la guía financiera](../../specs/05-api/prorrateo-mora-reportes.md).

Las correcciones de compatibilidad BDD, OpenAPI, formato y ejecución SQL de contratos, junto con los resultados del candidato, se registran en [SPRINT-2-VALIDACION-PR25.md](SPRINT-2-VALIDACION-PR25.md). La evidencia histórica siguiente no sustituye esa ejecución ni la aprobación del PR final. El correo real, invitaciones, devolución ejecutada y despliegue automático siguen fuera del alcance entregado.

## Alcance y criterio de este corte

Se reúne la implementación de las 15 historias y las 5 entregas técnicas de
[SPRINT-2.md](SPRINT-2.md), sus guiones y la evidencia previamente reportada por
los responsables. Por decisión de entrega se reutilizan esos resultados y no se
repiten pruebas en esta actualización documental. Los números siguientes son
resultados de sus respectivos cortes; no se suman ni se presentan como una nueva
ejecución sobre el commit final del merge.

El estado **integrado** identifica código incorporado en `develop`. La aceptación
del PR y el merge a `main` se registran en GitHub; este documento no los sustituye.

## Matriz de los 20 elementos

| Ticket | Responsable | Entrega integrada / documento de referencia |
|---|---|---|
| CON-04 | Jerson | Alta inactiva, contraseña con hash, habilitación por SuperAdmin y revocación de sesiones. [Contrato y flujo](../../specs/02-domains/05-usuarios-rbac/alta-administrativa.md). |
| CON-05 | Jerson | Vínculos SQL, relaciones por unidad, protección del último titular y sesiones revocables. [Entrega](CON-05-vinculos-departamentos.md). |
| CON-06 | Jerson | Cuatro roles, gestión contextual y autorización en backend. [Entrega](CON-06-roles-permisos.md). |
| CON-22 | Anderson | Voucher obligatorio privado, recepción EN_REVISION y descarga autenticada. [Uso](SPRINT-2-ANDERSON-USO.md) y [convergencia multipart](CON-72-convergencia.md). |
| CON-23 | Brandon | Hash canónico, unicidad durable y respuestas idempotentes. [Entrega](CON-23-41-43-brandon-entrega.md) y [contrato integrado](CON-72-convergencia.md). |
| CON-32 | Alejandro | Avisos de cuotas desde el outbox real y destinatarios SQL. [Entrega](CON-32-34-36-37-notificaciones.md). |
| CON-34 | Alejandro | Recepción y resultados de revisión desde operaciones persistidas. [Entrega](CON-32-34-36-37-notificaciones.md). |
| CON-36 | Alejandro | Avisos de confirmación y cancelación desde eventos de reservas. [Entrega](CON-32-34-36-37-notificaciones.md). |
| CON-37 | Alejandro | Reintentos persistentes, recuperación, alertas y atención administrativa. [Entrega](CON-32-34-36-37-notificaciones.md). |
| CON-39 | Jerson | Catálogo contextual SQL con horarios, aforo, costo y estado. [Entrega](CON-39-catalogo-areas.md). |
| CON-40 | Gerardo | Calendario con reservas y bloqueos SQL, UTC/Lima y refresco de interfaz. [Entrega](CON-40-disponibilidad.md). |
| CON-41 | Brandon | Reserva confirmada con acceso, solvencia, auditoría y outbox transaccionales. [Entrega](CON-23-41-43-brandon-entrega.md). |
| CON-42 | Anderson | Bloqueo por deuda vencida SQL, independiente por unidad. [Uso](SPRINT-2-ANDERSON-USO.md). |
| CON-43 | Brandon | Exclusión entre sesiones mediante locks SQL y conflicto controlado. [Entrega](CON-23-41-43-brandon-entrega.md). |
| CON-46 | Gerardo | Cancelación persistente, frontera de 24 horas, respuesta idempotente y ajuste trazable. [Entrega](CON-46-cancelacion-reservas.md). |
| CON-70 | Anderson | Comprobantes, revisiones, aplicaciones financieras, archivos y eventos durables. [Evidencia](SPRINT-2-ANDERSON-VERIFICACION.md). |
| CON-72 | Gerardo | Contratos adoptados en API, eventos e interfaz; multipart, subsanación y errores públicos. [Convergencia](CON-72-convergencia.md). |
| CON-73 | Nicolás (Tarqui) | Áreas, reservas, bloqueos, notificaciones, intentos y eventos persistentes. [Entrega](CON-73-CON-74-integracion.md). |
| CON-74 | Nicolás (Tarqui) | Portales conectados a API, sesión validada, archivos reales y estados de operación. [Integración](CON-73-CON-74-integracion.md) y [convergencia](CON-72-convergencia.md). |
| CON-75 | Gerardo | Este índice de evidencia, guiones, errores, límites y preparación de la entrega. |

## Evidencia reportada por el equipo

La [entrega de notificaciones](CON-32-34-36-37-notificaciones.md#resultados-de-las-pruebas)
registra el corte del 21/10/2026 sobre `ff77e08`, reproducido localmente según los
jobs de CI. Es la referencia consolidada más reciente; no acredita por sí sola el
estado de los checks del futuro PR a `main`.

| Verificación reportada | Resultado / referencia |
|---|---|
| Backend completo | 533 aprobadas, 0 omitidas; cobertura 91,40 %. |
| Integración PostgreSQL | 276 aprobadas; ciclo de migraciones con cabeza única `20261021_0015`. |
| Contrato API | Schemathesis: 56 aprobadas. CON-72: 24 aprobadas con base de pruebas; el job con solo `CON73_TEST_DATABASE_URL` reporta 1 aprobada y 23 omitidas. |
| Frontend | 22 pruebas JavaScript aprobadas; tipos, ESLint y build correctos. |
| SDD / OpenAPI | Verificador SDD y Spectral sin errores bloqueantes reportados. |
| Docker | Build y smoke reportados correctos, con API, web y workers sanos. |
| Secretos | Gitleaks sin filtraciones reportadas en ese corte. |

Antecedentes específicos, conservados con su fecha y alcance:

- [Anderson](SPRINT-2-ANDERSON-VERIFICACION.md): archivos, concurrencia financiera,
  rollback, permisos, nueva sesión, reinicio de API y relay de eventos.
- [CON-72](CON-72-convergencia.md): contratos, subsanación, revisión y descarga;
  recorrido Chromium de reporte a aviso. Las capturas temporales de ese entorno
  dejaron de estar disponibles y no se adjuntan como evidencia nueva.
- [CON-73/74](CON-73-CON-74-integracion.md): Chromium de reserva/cancelación,
  recuperación del mismo UUID después de reinicios, diez solicitudes concurrentes,
  frontera temporal, workers, errores y reintentos.
- [Reconciliación legacy](reconciliacion-esquema-legacy.md): respaldo, ensayo,
  conservación de las 28 tablas originales, adopción a `20261021_0015` y backend
  sano en el despliegue documentado. Esa reparación no inició workers ni reprodujo
  eventos históricos.

## Guion de entrega y casos de error

Las instrucciones de arranque están en el [README](../../README.md). Estos pasos
organizan la demostración disponible; no se declaran ejecutados de nuevo en esta
preparación documental. Usar datos de demostración identificables y conservar los
UUID de usuario, unidad, comprobante, reserva y notificación del recorrido.

| Recorrido | Precondición y resultado esperado | Guion |
|---|---|---|
| Acceso | SuperAdmin y condominio activo. Crear cuenta inactiva, habilitarla, asignar rol y unidad; desactivar o revocar invalida la sesión anterior. | [Alta](../../specs/02-domains/05-usuarios-rbac/alta-administrativa.md), [roles](CON-06-roles-permisos.md), [vínculos](CON-05-vinculos-departamentos.md). |
| Pagos | Residente vinculado, voucher válido y cuota demo. Reportar, repetir, observar/subsanar y aprobar; conservar el mismo comprobante y consultar el resultado. Un reporte en revisión no aplica fondos. | [Pagos](SPRINT-2-ANDERSON-USO.md), [CON-72](CON-72-convergencia.md). |
| Reservas | Área activa, unidad solvente y turno futuro. Consultar, reservar y cancelar con al menos 24 horas; el turno se libera y el historial persiste. | [Calendario](CON-40-disponibilidad.md), [cancelación](CON-46-cancelacion-reservas.md). |
| Comunicaciones | Worker activo y destinatarios con vínculos SQL. Las operaciones generan avisos; `+falla1` y `+rebote` demuestran reintento y alerta en el transporte simulado. | [Notificaciones](CON-32-34-36-37-notificaciones.md). |
| Autorización y validación | Sesión ausente/revocada, Auditor intentando escribir, unidad ajena o archivo inválido producen errores controlados, sin efectos parciales. | [Evidencia financiera](SPRINT-2-ANDERSON-VERIFICACION.md), [contratos](CON-72-convergencia.md). |
| Mora, conflicto y plazo | Deuda vencida bloquea la reserva; solapamiento responde 409; cancelación voluntaria fuera de plazo se rechaza. | [Solvencia](SPRINT-2-ANDERSON-USO.md), [reservas](CON-23-41-43-brandon-entrega.md), [CON-46](CON-46-cancelacion-reservas.md). |

## Alcance temporal y límites conocidos

- **Notificaciones:** transporte `SIMULADO`, con aceptación `ENVIADO`; no se
  acredita `ENTREGADO` por correo o WhatsApp. Proveedor externo y confirmación de
  entrega diferidos; proveedor sin configuración genera alerta.
- **Vouchers:** almacenamiento privado local en `uploads/vouchers/`, máximo de
  5 MiB, PNG/JPEG/PDF validados y recuperación autenticada. S3/MinIO diferidos.
- **Identidad:** contraseña inicial del administrador y habilitación manual de
  SuperAdmin; invitaciones y verificación por correo diferidas.
- **Cancelación:** sin cobro efectivo, `NO_APLICA`. Con cobro reembolsable se
  registra la solicitud de ajuste `PENDIENTE`; no equivale a devolución ejecutada
  ni incorpora su asiento financiero a esta operación.
- **Operación:** no hay gestión pública de bloqueos ni rediseño visual en este
  corte. El CD conserva su destino de despliegue pendiente y el diagnóstico de
  drift/lint heredado sigue documentado en [CI/CD](../procesos/CI-CD.md).

## Preparación documental original del merge — 21/10/2026

Los pasos y la descripción de esta sección son el antecedente del corte original. Para el alcance y evidencia actuales se utiliza la validación del candidato enlazada al inicio; no se presenta la descripción histórica siguiente como el cuerpo vigente del PR #25.

Integrar esta actualización documental en `develop` y abrir el PR hacia `main`
con título sugerido `feat: entregar sprint 2 de usuarios pagos reservas y notificaciones`.
La convención de ramas existente admite expresamente `develop` → `main`.

La descripción del PR debe enlazar este documento y el alcance del sprint,
referenciar los resultados del equipo con su corte y declarar que esta
actualización no repite pruebas. Mantener los checks configurados y la aprobación
de un integrante: el documento de notificaciones conserva una revisión específica
pendiente de los responsables de CON-40/41/43/73 sobre la restauración integrada.
No se registra esa revisión como realizada sin una aprobación identificable.

No se asigna una versión ni se declara un tag o una Release publicados. La
preparación documental no modifica código, base de datos, configuración privada,
workflows, ni realiza el merge. La fecha de publicación y el commit final se
registran cuando el equipo apruebe la entrega.

### Descripción preparada para el PR

```markdown
## Entrega

Integra el Sprint 2: alta y habilitación de usuarios, vínculos y roles;
vouchers privados, deduplicación y revisión financiera; catálogo, solvencia,
reservas concurrentes y cancelación; notificaciones persistentes y alertas.
Completa la continuidad de CON-22/23 del Sprint 1 y las entregas CON-70/72/73/74/75.

Trazabilidad: docs/sprints/SPRINT-2.md y docs/sprints/CON-75-entrega-sprint-2.md.
La matriz conserva los 20 elementos y sus responsables.

## Evidencia

Se reutilizan las ejecuciones reportadas por el equipo en el cierre de
notificaciones (corte ff77e08): 533 pruebas backend, cobertura 91,40 %, 276
integraciones PostgreSQL y 22 pruebas JavaScript. Se documentan contratos,
migraciones, build y smoke. Esta actualización documental no repite pruebas;
los checks de este PR mantienen sus resultados propios.

## Límites y operación

Vouchers privados locales; transporte de notificaciones SIMULADO; habilitación
manual por SuperAdmin. Un ajuste PENDIENTE no acredita devolución ejecutada.
El README incluye arranque y workers; la reconciliación legacy conserva su
procedimiento y respaldo documentados. La aprobación de revisión se registra
en GitHub; no se declara un tag o una Release publicados.
```
