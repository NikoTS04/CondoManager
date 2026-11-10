# Revisión de preparación del Sprint 3 — Usuarios y seguridad

Revisión inicial: 28/10/2026, America/Lima. Código inspeccionado: `develop`, `f49dc55` (merge del PR #28). Actualización para publicación: **30/10/2026**, sobre `develop` en `befae2d`. Fuente Jira: proyecto CON, tablero 34, sprint 68. Esta revisión no modifica tickets, asignaciones, estados ni código funcional.

## Cambios comprobados antes de publicar — 30/10/2026

- Los documentos `SPRINT-3.md` y `SPRINT-3-REVISION.md` seguían locales y sin versionar; no existían en `develop` remoto ni había otro PR documental abierto para publicarlos.
- El [PR #29](https://github.com/NikoTS04/CondoManager/pull/29) ya incorporó las correcciones de entrega a `develop` (`befae2d`). El [PR #25](https://github.com/NikoTS04/CondoManager/pull/25) se fusionó el 30/10/2026 y llevó el Sprint 2 a `main` (`8b09a35`). Entre la base inicial y `develop` se integraron compatibilidad BDD, OpenAPI, ejecución SQL de CON-72, formato y documentación, y la corrección transaccional de fondos; no incrementos funcionales del Sprint 3.
- La validación final del código de esas correcciones aprobó **651 pruebas backend y 92,15 % de cobertura en GitHub**, **326 integraciones PostgreSQL** y contratos **68 + 24 sin omisiones**. Docker y los recorridos Chromium de pagos/reservas también se verificaron, incluida persistencia tras reiniciar API y workers. Fuentes: [resultado backend del PR #29](https://github.com/NikoTS04/CondoManager/actions/runs/40807414402/job/123229560625) y [validación del Sprint 2](SPRINT-2-VALIDACION-PR25.md). Es evidencia de la base integrada, no aceptación de nuevas funciones del Sprint 3 ni del ambiente compartido.
- Jira conserva los mismos 14 tickets. [CON-7](https://tarquisoncco2.atlassian.net/browse/CON-7) y [CON-76](https://tarquisoncco2.atlassian.net/browse/CON-76) están `En curso` con Jerson. Los otros 12 están `Por hacer`; 12 de los 14 ya tienen responsable conforme al plan. [CON-24](https://tarquisoncco2.atlassian.net/browse/CON-24) y [CON-79](https://tarquisoncco2.atlassian.net/browse/CON-79) siguen sin asignar; Brandon continúa como propuesta para ambos. Las descripciones vigentes de CON-7/76 conservan los criterios contrastados en el plan.
- Se contrastaron cambios Git y estado/asignación de los 14 tickets; no se reprogramó el sprint, no se revisaron nuevamente todas sus estimaciones ni se ejecutó una nueva suite funcional manual durante esta actualización documental. Las discrepancias de alcance y el reparto propuesto conservan su validación pendiente con el equipo.

Las secciones históricas siguientes conservan su fecha y entorno. Su ejecución inicial sin PostgreSQL no representa el estado final del código corregido.

## Dictamen

**Sí existe una base suficiente para avanzar con el Sprint 3. El backlog necesita refinamiento antes de repartirlo como trabajo nuevo. No se acredita el cumplimiento íntegro de los criterios originales de los sprints anteriores.**

La aplicación ya tiene identidad SQL, JWT, cuatro roles contextuales, revocación de sesiones, vínculos por departamento, cuotas/pagos persistentes, conciliación, reservas y comunicaciones durables. Parte de lo que Jira presenta como pendiente del Sprint 3 se adelantó al integrar el Sprint 2 y la ampliación financiera posterior.

Los pendientes más claros son correo real, recordatorios programados, estado de cuenta con movimientos por periodo, comunicación de cambios de acceso, filtros de conciliación y retirada de compatibilidad en memoria. El entorno compartido requiere una validación actual, aunque existe evidencia documental de despliegue y recuperación.

Se inspeccionaron la estructura del proyecto, documentación de alcance, especificaciones de identidad, finanzas, reservas y notificaciones, contratos, migraciones, rutas/servicios/repositorios relacionados, portales y pruebas. No es una auditoría exhaustiva de seguridad ni una certificación del despliegue actual.

## Estado de Jira consultado — 28/10/2026 (histórico)

- `S1 — Finanzas y datos`: cerrado; 12 tickets asociados, todos `Listo`. Incluye tareas técnicas además de las 8 historias de `SPRINT-1.md`.
- `S2 — Reservas y avisos`: cerrado; 20 tickets asociados, todos `Listo`, coincidentes con la consolidación de `SPRINT-2.md`.
- `S3 — Usuarios y seguridad`: activo, inicio registrado 21/10/2026 y fin registrado 28/10/2026. Objetivo: autenticación, roles, correo real y eliminación de simulaciones.
- S3 contiene **14 tickets: 8 historias y 6 tareas técnicas**, todos `Por hacer` y **sin asignar**.
- Las historias suman **41 puntos**; las seis tareas técnicas no tienen estimación de puntos en los campos consultados. Los 41 puntos no representan el esfuerzo total restante: incluyen funcionalidades adelantadas.
- Las etiquetas históricas de CON-70/72 todavía dicen `sprint-1`, aunque también se integraron y documentaron en S2. La pertenencia se comprobó por el campo Sprint, no solo por etiquetas. Las asociaciones históricas entre sprints se solapan; sus cantidades no deben sumarse como tickets distintos.

[Consulta del Sprint 3](https://tarquisoncco2.atlassian.net/issues/?jql=project%20%3D%20CON%20AND%20sprint%20%3D%2068).

## Contraste de los sprints 1 y 2

En esta tabla de la inspección inicial, «implementado» significa que existe código y cobertura pertinente; las pruebas PostgreSQL no se reprodujeron durante aquella revisión. La ejecución posterior sobre la base corregida está identificada al inicio.

| Tickets | Evidencia en el proyecto | Evaluación |
|---|---|---|
| CON-2 | `condominios/`, autorización de SuperAdmin y pruebas HTTP/BDD | Base implementada para alta, consulta y contexto. |
| CON-3 | `condominios/estructura/`, importación CSV y pruebas de persistencia/concurrencia | Implementado. Jira dice duplicado dentro del «edificio o condominio»; la especificación y el código usan edificio. Precisar que dos edificios pueden tener departamento 101, identificados por UUID. |
| CON-9 | `cuotas/presupuestos/`, aprobación y presupuesto persistente | Implementado; ampliado con conceptos, prorrateo y fondos en el corte posterior. |
| CON-10 | `cuotas/distribucion/`, Decimal, validación de alícuotas y cierre de centavos | Implementado, con rutas y pruebas. |
| CON-11 | `cuotas/emision.py`, worker, lote, auditoría y outbox | Implementado: presupuesto aprobado, transacción e idempotencia. |
| CON-13 | `cuotas/saldos/`, integración con emisión | Implementado para cobertura total/parcial y trazabilidad del consumo de crédito. |
| CON-22/23 | `pagos/persistencia.py`, storage, claves únicas e integración | El trabajo inicialmente planificado en S1 se completa en S2. Hay reporte EN_REVISION, evidencia privada y deduplicación persistente. |
| CON-69/71 | Alembic, Compose, scripts de seed, guías y workflows | Hay implementación y evidencia histórica. Docker no estuvo disponible en la revisión inicial; la validación posterior de entrega sí comprobó arranque y migraciones en un entorno efímero. El ambiente compartido sigue requiriendo evidencia propia en CON-81. |
| CON-4 | `usuarios/service.py`, contrato `alta-administrativa.md` y portal administrativo | **Brecha con Jira:** se entrega contraseña inicial administrativa y habilitación manual por SuperAdmin. Jira exige token, invitación y contraseña establecida por el usuario. Está `Listo` sin esos criterios originales completos. |
| CON-5 | Vínculos SQL, titular requerido, revocación lógica y `auth_revision` | Base implementada. Es el punto de partida de CON-7. |
| CON-6 | `core/roles.py`, seguridad, autorización contextual y editor de roles | **Contradicción documental:** Jira enumera Propietario/Inquilino como roles; el contrato implementa SUPERADMIN, ADMIN_JUNTA, AUDITOR y RESIDENTE. La tenencia pertenece al vínculo. |
| CON-32/34/36/37 | Outbox, consumidor, cola SQL, intentos, reintentos y alertas | Integración implementada con transporte SIMULADO. No prueba recepción de correos reales. CON-36 conserva invitaciones en Jira, pero fueron diferidas en S2. |
| CON-39/40 | Catálogo SQL, reglas, disponibilidad por área/fecha y lectura de bloqueos | Implementado. La gestión pública de bloqueos de mantenimiento sigue siendo alcance posterior, diferente de consultar sus efectos. |
| CON-41/42/43 | Creación SQL, locks, solvencia por cuotas y outbox | Implementado como base persistente; subsiste copia de compatibilidad en memoria usada por rutas. Es trabajo concreto de CON-80. |
| CON-46 | Cancelación persistente, plazo de 24 h, auditoría y evento | Implementado con límite declarado: ajuste reembolsable PENDIENTE no equivale a una devolución contable ejecutada. Alinear el criterio de Jira con ese alcance. |
| CON-70/73 | Repositorios, migraciones y pruebas de sesiones independientes | Persistencia sustancialmente integrada. No corresponde volver a construir estos módulos desde cero en CON-80. |
| CON-72/74/75 | Contratos, portal conectado y guiones de entrega | Integrados. El PR #29 reconcilió README, Sprint 2 y CON-75 con el corte financiero y corrigió la ejecución SQL de contratos. Las discrepancias restantes de los criterios de Jira se refinan en este sprint. |

Fuentes: [Sprint 1](SPRINT-1.md), [Sprint 2](SPRINT-2.md), [entrega CON-75](CON-75-entrega-sprint-2.md), [alta administrativa](../../specs/02-domains/05-usuarios-rbac/alta-administrativa.md), [seguridad vigente](../../specs/01-architecture/security-and-rbac.md), [recuperación del 26 de octubre](reconciliacion-esquema-20261026.md).

## Trabajo real por ticket del Sprint 3

Los siguientes son criterios de refinamiento propuestos para repartir responsabilidades; no son cambios ya aplicados en Jira.

| Ticket / puntos | Qué existe | Qué falta o debe aclararse antes de aceptarlo |
|---|---|---|
| [CON-7](https://tarquisoncco2.atlassian.net/browse/CON-7) · 5 | Cambio/revocación de roles y vínculos, historial y sesiones invalidadas | Completar recorrido de cambio de residente/Junta y comunicación a afectados. Precisar quién puede relevar a la Junta: hoy solo SuperAdmin gestiona ADMIN_JUNTA. Conservar pagos/cuotas/reservas históricas y la designación de responsable de pago. Probar revocación con token anterior y nuevo login. |
| [CON-14](https://tarquisoncco2.atlassian.net/browse/CON-14) · 5 | Resumen de deuda vencida, crédito y lista de comprobantes | Crear consulta y pantalla con cargos, abonos, moras, crédito y deuda exigible por periodo; enlazar movimientos y correcciones conservadas. El resumen actual no satisface el detalle histórico. No usar el PDF de prorrateo como sustituto del estado de cuenta. |
| [CON-24](https://tarquisoncco2.atlassian.net/browse/CON-24) · 5 | Listado contextual de comprobantes, voucher y acciones de revisión | Añadir filtros por fecha, departamento, banco y estado. Definir rango de fechas, combinaciones y paginación. Acordar si AUDITOR puede ver la bandeja completa en lectura: el proyecto ya lo permite, mientras Jira solo menciona permiso de conciliación. |
| [CON-25](https://tarquisoncco2.atlassian.net/browse/CON-25) · 8 | Aprobación, prelación por componentes, imputaciones, crédito, locks, auditoría y evento | Validar el flujo existente con PostgreSQL y la reconstrucción por fecha bancaria; no implementar otro motor. Probar repetición/concurrencia, rollback y que imputaciones más crédito cuadren con el pago. Conservar snapshots financieros y fondos de mora ya comprometidos. |
| [CON-26](https://tarquisoncco2.atlassian.net/browse/CON-26) · 5 | OBSERVADO/RECHAZADO, motivo obligatorio, sin imputación del comprobante y subsanación del observado | Validar el recorrido y conectar correo real de CON-78. Precisar que «sin afectar saldos» se refiere a no acreditar el pago rechazado: la nueva mora diaria puede recuperar devengos pausados al revisar. Conservar ese comportamiento o documentar la decisión. |
| [CON-27](https://tarquisoncco2.atlassian.net/browse/CON-27) · 5 | Abono parcial, saldo pendiente y bloqueo por deuda vencida | Resolver estado: Jira exige PAGO_PARCIAL, pero el código prioriza EN_MORA cuando sigue existiendo mora. Precisar estado de cuota frente a condición financiera del departamento y alinear máquina de estados, API y pruebas. No perder el bloqueo de reservas al corregir la nomenclatura. |
| [CON-28](https://tarquisoncco2.atlassian.net/browse/CON-28) · 3 | Cancelación de obligaciones y remanente en `saldo_a_favor` | Validar excedente e idempotencia existentes y mostrar origen/importe del crédito en CON-14. La generación del crédito y su consumo en CON-13 son operaciones distintas. |
| [CON-33](https://tarquisoncco2.atlassian.net/browse/CON-33) · 5 | Plantilla NOTIF_RECORDATORIO_PREVIO | Falta productor programado: selección SQL de cuotas próximas a vencer con saldo, configuración de anticipación/canales y deduplicación por cuota/fecha/canal/destinatario. Revalidar deuda al enviar; una cuota pagada entre encolado y despacho no debe recibir recordatorio de deuda. Usar calendario de Lima y la gracia aplicable. |
| [CON-76](https://tarquisoncco2.atlassian.net/browse/CON-76) · sin puntos | Login SQL, JWT, revocación, cuatro roles, protección de rutas y vistas | Refinarlo como completar/endurecer autenticación existente. Decidir si incluye activación por enlace para cerrar la brecha de CON-4: token de un uso, expiración, contraseña y correo. Si se conserva habilitación manual, corregir el criterio. Falta registro explícito de accesos denegados; los handlers responden sin dejar un registro de seguridad propio. Corregir además la duración JWT: configuración declara 60 min, emisión usa constante de 24 h. |
| [CON-77](https://tarquisoncco2.atlassian.net/browse/CON-77) · sin puntos | Validación por condominio, rol y vínculo, consultas SQL y pruebas negativas | Completar matriz de endpoints actuales, incluidas condiciones de pago, exports, fondos y ledger agregados después de S2. Probar dos condominios reales, IDs cruzados y roles revocados. Definir alcance de SuperAdmin global. No concluir aislamiento completo solo por existencia de RLS o por pruebas con dobles. |
| [CON-78](https://tarquisoncco2.atlassian.net/browse/CON-78) · sin puntos | Cola SQL, plantillas, intentos, backoff, alertas y recuperación | Implementar adaptador SMTP/API y configuración segura. El worker rechaza hoy PROVEEDOR con PROVEEDOR_NO_CONFIGURADO. Resolver idempotencia/aceptación incierta, rebotes temporales/permanentes y confirmación de entrega si la soporta el proveedor. Distinguir aceptado/ENVIADO de ENTREGADO. Demostración real con contactos autorizados. |
| [CON-79](https://tarquisoncco2.atlassian.net/browse/CON-79) · sin puntos | Vouchers privados locales, PNG/JPEG/PDF validados hasta 5 MiB, referencias SQL, historial y descarga autenticada | Decidir si la alternativa local persistente ya satisface el ticket o se exige almacenamiento de objetos. Jira permite «alternativa equivalente»: S3 no es requisito automático. Precisar qué documentos adicionales se incluyen, retención, respaldo, reemplazo y eliminación auditable. Si se migra, conservar referencias y evidencias antiguas. |
| [CON-80](https://tarquisoncco2.atlassian.net/browse/CON-80) · sin puntos | Cuotas, pagos, catálogo, reservas y notificaciones tienen persistencia | Retirar RESERVAS_REGISTRADAS de rutas productivas y la combinación SQL/piloto/adopción desde memoria. Mover adaptadores a pruebas. Con esquema requerido ausente, responder error operativo, sin calendario vacío o fuente piloto. Probar con dos procesos y reinicios. No confundir caché derivada con una segunda fuente de operaciones. |
| [CON-81](https://tarquisoncco2.atlassian.net/browse/CON-81) · sin puntos | Guías, migraciones y evidencia de despliegue, respaldo/restauración y actualización a 0020 | Identificar el ambiente compartido vigente y demostrar salud real, revisión de esquema, seed idempotente y recuperación. `/health` devuelve un estado estático: no comprueba PostgreSQL. La reparación legacy del 26/10 no sustituye probar instalación limpia ni es una migración reutilizable sobre cualquier base. |

Evidencia principal de implementación:

- [Identidad, roles y vínculos](../../src/modules/usuarios/service.py), [JWT y validación de sesión](../../src/core/security.py), [autorización contextual](../../src/core/authorization.py).
- [Conciliación persistente](../../src/modules/pagos/persistencia.py), [prelación](../../src/modules/pagos/contabilidad.py), [reconstrucción diaria](../../src/modules/pagos/mora_diaria.py).
- [Resumen de cuenta](../../frontend/src/features/residente/ResumenCuenta.tsx), [bandeja actual](../../frontend/src/features/junta/ConciliacionSection.tsx).
- [Worker de comunicaciones](../../src/modules/notificaciones/worker.py), [destinatarios](../../src/modules/notificaciones/repository.py), [modelo de notificaciones](../../src/modules/notificaciones/models.py), [plantillas](../../src/modules/notificaciones/templates.py).
- [Storage privado](../../src/modules/pagos/storage.py), [rutas de reservas](../../src/modules/reservas/router.py), [combinación de fuentes de disponibilidad](../../src/modules/reservas/disponibilidad.py).

## Dependencias y coherencia que deben quedar explícitas

1. **Activación e invitación:** acordar juntos CON-4, CON-36, CON-76 y CON-78. Configurar SMTP por sí solo no crea un flujo de activación.
2. **Destinatarios de identidad:** la cola actual requiere `departamento_id` y el worker solo acepta destinatarios con cuenta/rol/vínculo activos. Una invitación a cuenta inactiva sin unidad, o un aviso a la Junta saliente tras revocarla, necesita un contrato propio. No basta con añadir una plantilla o desactivar globalmente la revalidación de destinatarios operativos.
3. **Finanzas:** CON-25/26/27/28 comparten `PagosPersistentesService.revisar` y la reconstrucción diaria. Conviene un responsable de integración o una secuencia de PR, para no modificar simultáneamente la misma transacción desde implementaciones incompatibles.
4. **Estado de cuenta:** CON-14 presenta el resultado de CON-25/27/28. Su contrato puede acordarse al principio y la validación final hacerse con esos casos.
5. **Correo y programación:** CON-33 produce recordatorios; CON-78 transporta mensajes. Pueden desarrollarse con un contrato compartido, pero la aceptación de envío real necesita ambos.
6. **Persistencia y aislamiento:** CON-80 debe conservar los locks y la precedencia SQL de las reservas; CON-77 debe probarlos en el ambiente de CON-81.
7. **Alcance del sprint:** además de usuarios/seguridad hay conciliación y finanzas. El contenido es coherente con consolidar el producto, pero el título no refleja todo el trabajo. Precisar el objetivo y reestimar el trabajo restante, incluidas las seis tareas técnicas.

## Documentación que requiere reconciliación

- `README.md`, `SPRINT-2.md` y CON-75 **ya fueron actualizados en el PR #29** para distinguir el corte original `52b4512`, la ampliación financiera y su validación. Ese pendiente documental de la revisión inicial queda resuelto; los resultados de cada corte conservan su procedencia.
- `specs/02-domains/05-usuarios-rbac/spec.md` aún llama «pendiente de código» a política diaria/gracia por responsable, ya implementada después.
- `proc-05-gestion-usuarios.md` aún llama pendiente a la ampliación MONTO_DIARIO.
- `security-and-rbac.md` conserva una nota de estado piloto de pagos/reservas/notificaciones previa a su persistencia integrada.
- La máquina de estados de cuotas dice que CONCILIAR_PARCIAL lleva a PAGO_PARCIAL, mientras la implementación puede conservar EN_MORA. Debe resolverse con CON-27.
- La matriz de trazabilidad contiene entradas antiguas como `POST /api/v1/usuarios` y `test_usuarios.py`, además de filas nuevas correctas. Diferenciar contratos implementados de capacidades futuras.
- La tarea CON-79 admite almacenamiento equivalente, mientras la documentación difiere S3/MinIO. Mantener el requisito contractual explícito para evitar rehacer el storage sin una necesidad acordada.

## Verificación de la revisión inicial — 28/10/2026 (histórico)

| Verificación | Resultado de la revisión inicial |
|---|---|
| Pruebas JavaScript `node --test frontend/tests/*.test.mjs` | **22 aprobadas**. |
| TypeScript `tsc --noEmit --incremental false -p frontend/tsconfig.json` | **Correcto**. |
| `scripts/verify_sdd_compliance.py` | **Correcto**. Es un control estático de presencia/reglas, no una prueba de cumplimiento funcional de todas las HU. |
| Suite backend completa, sin PostgreSQL de pruebas | **347 aprobadas, 1 fallida, 302 omitidas**, 650 recogidas. |
| Docker / servicios / migraciones contra PostgreSQL actual | No verificados: Docker Desktop no expone el daemon y no hay URL de pruebas configurada. |
| Build frontend, Spectral, cobertura completa y checks remotos de GitHub | No ejecutados/consultados en esta revisión. |

La prueba fallida es `src/tests/integration/test_usuarios_alcances.py::test_listas_privadas_y_calendario_sin_unidad_ajena`. Sus dobles aíslan identidad/pagos/reservas, pero la consulta de disponibilidad entra al repositorio SQL real y falla por conexión PostgreSQL rechazada. Es un fallo reproducido por dependencia de infraestructura, no evidencia de una filtración de datos. También muestra que la suite no omite uniformemente los casos que necesitan PostgreSQL. No se oculta ni se presenta la ejecución como verde.

El entorno Windows inicialmente tuvo errores de lectura cp1252, ausencia de `python-docx`/`reportlab` en `.venv` y bloqueo de sockets internos de asyncio dentro del aislamiento. La ejecución final usó UTF-8, importó exclusivamente esas bibliotecas ya incluidas en el runtime de la aplicación y corrió fuera de ese aislamiento. No se modificaron dependencias ni código del repositorio. Se forzaron URLs locales durante el proceso para no usar la base configurada del proyecto.

El reporte JUnit de la ejecución final está en `tmp/sprint3-audit/backend.xml` (evidencia local, fuera de la documentación canónica). Para repetir en un entorno preparado, instalar las dependencias declaradas de desarrollo y ejecutar `python -X utf8 -m pytest -q`, configurando `CON3_TEST_DATABASE_URL` y `CON13_TEST_DATABASE_URL` contra PostgreSQL exclusivo de pruebas. Con esas variables, las pruebas crean y eliminan esquemas de prueba: no apuntarlas a una base operativa.

La evidencia histórica de CON-75 (533 pruebas y cobertura del corte anterior) y de la recuperación del 26/10 (650 aprobadas según su documento) se conserva con su procedencia. Esas cifras no acreditan las 302 omisiones de la revisión inicial. La validación posterior de 651 pruebas sobre el código corregido tiene su propia ejecución y fuentes al inicio; no se presenta como una repetición de aquel entorno incompleto.

## Orden recomendado para repartir trabajo

Primero acordar los cuatro contratos: roles/activación, estados de pago parcial, destinatarios de identidad y alcance de almacenamiento. Registrar en los tickets el comportamiento existente y el incremento pendiente, con criterios observables y estimaciones actualizadas.

Luego organizar seis frentes por continuidad técnica. La comprobación del 30/10 confirmó 12 asignaciones conforme a esta propuesta; CON-24/79 siguen sin asignar. La capacidad individual y las revisiones propuestas aún deben validarse con el equipo:

| Frente | Tickets | Continuidad sugerida |
|---|---|---|
| Identidad y cambios de acceso | CON-7, CON-76 | Jerson, por CON-4/5/6. Coordinar con el frente de correo. |
| Conciliación y reglas financieras | CON-25/26/27/28 | Anderson, por CON-70. Unificar la transacción y revisar con quien implemente el estado de cuenta. |
| Bandeja y archivos | CON-24, CON-79 | Brandon, como propuesta full stack; coordinar cambios de storage con Anderson. |
| Correo y recordatorios | CON-78, CON-33 | Alejandro, por notificaciones y reintentos. Es trabajo sustancial; confirmar capacidad después de estimar proveedor y programación. |
| Persistencia y ambiente | CON-80, CON-81 | Nicolás (Tarqui), por CON-73/74 e integración. |
| Estado de cuenta y aceptación de aislamiento | CON-14, CON-77 | Gerardo, con revisión técnica de Jerson y pruebas cruzadas de Alejandro. |

Antes de aceptar el Sprint 3: ejecutar PostgreSQL/migraciones y recorridos de navegador en el ambiente común, probar cambios de rol/vínculo y cruces de condominio, acreditar correo real, verificar reinicios sin memoria y conciliar Jira con los criterios efectivamente entregados. Puede iniciarse desarrollo en paralelo mientras se resuelve ese cierre; todavía no corresponde declarar todas las historias originales de S1/S2 cumplidas al 100 %.
