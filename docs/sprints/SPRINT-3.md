# Sprint 3 — Usuarios y seguridad

## Objetivo

Completar el acceso de usuarios mediante invitación, consolidar la seguridad por rol y condominio, enviar correos reales y terminar los recorridos de conciliación y consulta financiera sobre datos persistentes. El recorrido final debe funcionar desde el navegador, conservarse después de reiniciar y dejar evidencia de sus resultados y errores.

El sprint contiene **14 elementos: 8 historias de usuario y 6 entregas técnicas**. El trabajo parte de lo ya integrado en `develop`; cada responsable completa y verifica el incremento pendiente de sus tickets.

## Base de planificación y estado

- Plan preparado el **28/10/2026**, a partir de `develop`, commit `f49dc55`, y de la [revisión de preparación](SPRINT-3-REVISION.md).
- Actualización para publicación: **30/10/2026**, sobre `develop` en `befae2d`. El [PR #29](https://github.com/NikoTS04/CondoManager/pull/29) incorporó las correcciones de entrega y el [PR #25](https://github.com/NikoTS04/CondoManager/pull/25) ya integró el Sprint 2 en `main` (`8b09a35`). Los documentos del Sprint 3 aún no estaban versionados. No se encontraron incrementos funcionales del Sprint 3 integrados en `develop` respecto a esa base.
- Antecedentes: [Sprint 1](SPRINT-1.md), [Sprint 2](SPRINT-2.md), [entrega CON-75](CON-75-entrega-sprint-2.md) y [ampliación financiera vigente](../../specs/05-api/prorrateo-mora-reportes.md).
- La consulta inicial encontró los 14 tickets `Por hacer` y sin asignar. En la comprobación de Jira del **30/10/2026**, CON-7 y CON-76 están `En curso` con Jerson; los otros 12 siguen `Por hacer`. Hay 12 tickets asignados conforme a este reparto. **CON-24 y CON-79 siguen sin asignar en Jira; Brandon es la propuesta del plan para ambos.** Esta publicación no modifica tickets ni asignaciones. El estado operativo vigente debe consultarse en Jira.
- Las historias conservan **41 puntos originales**. Las seis tareas técnicas están **por estimar**. Se debe estimar el trabajo restante después de reconocer lo implementado; sumar los puntos originales no mide la capacidad pendiente.
- La consulta inicial de Jira registraba el sprint activo del 21 al 28 de octubre de 2026. Este documento organiza el trabajo pendiente por etapas; Gerardo actualizará el calendario de ejecución con el equipo, sin presentar esas fechas anteriores como un nuevo compromiso. En esta actualización no se reprogramó el sprint ni se volvió a comprobar su calendario.
- Este es un documento de planificación. No declara implementados ni aprobados los cambios descritos aquí.

## Alcance y asignación

| Jira | Historia / entrega | ID funcional | Puntos originales | Responsable principal | Revisión principal |
|---|---|---|---:|---|---|
| [CON-7](https://tarquisoncco2.atlassian.net/browse/CON-7) | Gestionar cambios de residente o junta directiva | USR-06 | 5 | **Jerson** | Gerardo |
| [CON-14](https://tarquisoncco2.atlassian.net/browse/CON-14) | Consultar el estado de cuenta | CUE-06 | 5 | **Gerardo** | Anderson |
| [CON-24](https://tarquisoncco2.atlassian.net/browse/CON-24) | Consultar la bandeja de conciliación | PAG-03 | 5 | **Brandon** | Anderson |
| [CON-25](https://tarquisoncco2.atlassian.net/browse/CON-25) | Aprobar e imputar un pago | PAG-04 | 8 | **Anderson** | Jerson |
| [CON-26](https://tarquisoncco2.atlassian.net/browse/CON-26) | Rechazar u observar un comprobante | PAG-05 | 5 | **Anderson** | Alejandro |
| [CON-27](https://tarquisoncco2.atlassian.net/browse/CON-27) | Registrar un pago parcial | PAG-06 | 5 | **Anderson** | Gerardo |
| [CON-28](https://tarquisoncco2.atlassian.net/browse/CON-28) | Registrar un pago en exceso | PAG-07 | 3 | **Anderson** | Gerardo |
| [CON-33](https://tarquisoncco2.atlassian.net/browse/CON-33) | Enviar recordatorios de vencimiento | NOT-02 | 5 | **Alejandro** | Anderson |
| [CON-76](https://tarquisoncco2.atlassian.net/browse/CON-76) | Completar autenticación, activación y RBAC | Transversal | Por estimar | **Jerson** | Nicolás |
| [CON-77](https://tarquisoncco2.atlassian.net/browse/CON-77) | Verificar y completar el aislamiento por condominio | Transversal | Por estimar | **Gerardo** | Jerson |
| [CON-78](https://tarquisoncco2.atlassian.net/browse/CON-78) | Integrar correo transaccional real | Transversal | Por estimar | **Alejandro** | Nicolás |
| [CON-79](https://tarquisoncco2.atlassian.net/browse/CON-79) | Consolidar almacenamiento privado de vouchers y documentos | Transversal | Por estimar | **Brandon** | Nicolás |
| [CON-80](https://tarquisoncco2.atlassian.net/browse/CON-80) | Eliminar almacenes en memoria de los flujos principales | Transversal | Por estimar | **Nicolás (Tarqui)** | Brandon |
| [CON-81](https://tarquisoncco2.atlassian.net/browse/CON-81) | Validar y completar el ambiente de demostración | Transversal | Por estimar | **Nicolás (Tarqui)** | Jerson |

Las revisiones no sustituyen las pruebas de quien implementa. Alejandro coordina los escenarios de aceptación con todos los responsables; cada integrante entrega las pruebas y evidencia de su propio trabajo.

La columna de responsable combina las 12 asignaciones comprobadas en Jira con la propuesta aún no asignada de Brandon. La columna de revisión representa la coordinación propuesta por el plan, no una aprobación o asignación ya registrada en Jira.

### Qué hace cada integrante y por dónde empieza

| Integrante | Primero | Después | Resultado que entrega |
|---|---|---|---|
| **Jerson** | Definir con Alejandro el contrato de invitación, destinatarios de identidad y activación en CON-76. | Completar CON-76 y luego CON-7 sobre los roles/vínculos existentes. Revisar las migraciones nuevas. | Usuario invitado que activa su cuenta y cambios de acceso auditados, comunicados y efectivos en la siguiente petición. |
| **Anderson** | Verificar CON-25 y acordar estados de abono/mora con Gerardo. | Consolidar CON-27/28 en el mismo motor; completar CON-26 y revisar el contrato consumido por CON-14/24. | Conciliación exacta y transaccional, pago parcial, excedente y decisiones sin doble aplicación. |
| **Brandon** | Acordar filtros/paginación de CON-24 con Anderson y el alcance de archivos de CON-79 con Nicolás. | Completar bandeja y gestión privada de evidencias, con UI y pruebas. | Bandeja filtrable y archivos recuperables, trazables y protegidos. |
| **Alejandro** | Acordar con Jerson el contrato de identidad y con Nicolás la configuración del proveedor; iniciar CON-78. | Conectar los avisos existentes y de identidad; desarrollar CON-33 y su deduplicación. | Correo real con intentos/reintentos y recordatorios automáticos correctos. |
| **Nicolás (Tarqui)** | Iniciar CON-81: ambiente común y PostgreSQL exclusivo de pruebas, revisión del esquema y guía reproducible. | Retirar compatibilidad en memoria en CON-80; integrar migraciones, storage y workers; cerrar CON-81 con ensayo de recuperación. | Ambiente repetible y datos operativos compartidos entre procesos y después de reiniciar. |
| **Gerardo** | Registrar acuerdos de alcance, estimar el pendiente y definir con Anderson el contrato de CON-14; iniciar matriz de CON-77. | Implementar estado de cuenta; verificar aislamiento del conjunto integrado y coordinar aceptación. | Consulta financiera completa, matriz de accesos y evidencia final vinculada a los 14 tickets. |

El número de tickets no representa el esfuerzo. Los cuatro tickets de Anderson comparten un motor ya implementado; correo/activación y persistencia pueden requerir más cambios nuevos. Reestimar antes de fijar fechas y mover apoyo según el esfuerzo pendiente.

## Acuerdos de alcance que se registran primero

Estos son los criterios propuestos por este plan para resolver las discrepancias de la revisión. **Gerardo los registra y valida con los responsables en Jira y en las especificaciones antes de integrar el cambio correspondiente.** No se han modificado los criterios originales de Jira mediante este documento.

| Tema | Criterio de este plan | Responsable del acuerdo |
|---|---|---|
| Roles | Mantener `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR` y `RESIDENTE`. Propietario, copropietario e inquilino son vínculos por unidad. Alinear CON-6/76. | Gerardo + Jerson |
| Invitación y activación | Incluir en CON-76 el flujo diferido de CON-4: invitación, token temporal de un uso y contraseña elegida por el usuario. Alejandro transporta el correo en CON-78; Jerson implementa la identidad y pantalla de activación. Conservar compatibilidad de las cuentas existentes sin reactivarlas o cambiarles claves por migración. | Gerardo + Jerson + Alejandro |
| Cambio de Junta | Solo SuperAdmin puede conceder/revocar ADMIN_JUNTA, conforme al contrato actual. Cambiar Junta no exige desactivar globalmente la cuenta ni retirar sus vínculos de residente en otros contextos. | Gerardo + Jerson |
| Pago parcial y mora | Conservar `EN_MORA` mientras quede deuda vencida; mostrar el abono parcial y el saldo explícitamente. Fuera de mora, usar `PAGO_PARCIAL` cuando corresponda. Alinear CON-27 y la máquina de estados; la solvencia se deriva de deuda real, no de una etiqueta de UI. | Gerardo + Anderson |
| Observación/rechazo | No acreditar el importe del comprobante. La revisión puede regularizar mora diaria pausada conforme a la política vigente; documentarlo para que «sin afectar saldos» no oculte ese efecto. | Gerardo + Anderson |
| Bandeja | Junta/SuperAdmin concilian; Auditor consulta en lectura dentro de su contexto. Residente conserva solo sus consultas autorizadas. | Gerardo + Brandon + Jerson |
| Canales | Correo real como canal verificable de esta entrega. Configurar los recordatorios para EMAIL; otros canales requieren integración explícita antes de habilitarlos o prometer entrega. | Gerardo + Alejandro |
| Recordatorio | Anticipación configurable, con valor inicial de 3 días antes del vencimiento de la cuota. Usar fecha local de Lima y política histórica; precisar el tratamiento de gracia individual y evitar recordatorios duplicados o fechas que contradigan la política de la cuota. | Gerardo + Alejandro + Anderson |
| Archivos | El almacenamiento privado local persistente es la alternativa inicial de CON-79. Cubrir vouchers y los PDF/DOCX de prorrateo ya existentes. S3/MinIO solo entra si el ambiente lo necesita y se registra el cambio de alcance. Balances nuevos y documentos de proveedores pertenecen a sus entregas posteriores. | Gerardo + Brandon + Nicolás |
| Calendario y capacidad | Actualizar fechas de ejecución y estimar las seis tareas técnicas y los incrementos de las historias. | Gerardo + equipo |

## Dependencias: para empezar y para cerrar

La base de condominio, estructura, cuotas, vínculos, pagos y reservas del Sprint 2 ya está disponible. Una dependencia de cierre no obliga a esperar para desarrollar contra un contrato acordado.

| Ticket | Puede empezar cuando… | Para cerrarlo necesita… |
|---|---|---|
| **CON-81** | Se identifica el ambiente objetivo y el procedimiento actual. | Migraciones y servicios de los demás frentes integrados; respaldo/restauración y salud comprobados. |
| **CON-78** | Se acuerdan proveedor, canal y contrato de la cola con CON-76. | Ambiente inicial de CON-81, configuración real y pruebas de correo/reintentos. |
| **CON-76** | Se acuerdan roles, activación y destinatarios con CON-78. | Cola/transportes integrados, migración y pantalla de activación, pruebas SQL y de sesión. |
| **CON-7** | Existen contratos de CON-76 y los endpoints previos de roles/vínculos. | CON-76/78 integrados y avisos a afectados, incluso después de revocar su acceso operativo. |
| **CON-25** | Se fija la regla financiera vigente y se dispone de PostgreSQL de pruebas. | Transacción, prelación, ledger, auditoría, outbox e idempotencia verificados. |
| **CON-27** | Se acuerda su estado y el contrato de CON-25. | Motor de CON-25 integrado y solvencia SQL comprobada con deuda restante. |
| **CON-28** | Se acuerdan crédito/remanente de CON-25 y su representación en CON-14. | CON-25 integrado; origen de crédito visible en CON-14 y consumo posterior compatible con CON-13. |
| **CON-26** | Se acuerda la revisión de CON-25 y el aviso de CON-78. | Rechazo/observación/subsanación integrados y comunicación real comprobada. |
| **CON-24** | Se fijan filtros, respuesta y permisos con Anderson/Jerson. | CON-25/26 integrados para sus acciones y CON-79 para acceso a evidencias. |
| **CON-79** | Se acuerdan archivos, retención y almacenamiento con CON-81. | Acceso contextual, persistencia, reemplazo y recuperación demostrados en el ambiente. |
| **CON-14** | Se acuerda con Anderson la consulta de movimientos y saldos vigentes. | Casos de CON-25/27/28 integrados y accesos de CON-77 verificados. |
| **CON-33** | Se fijan calendario, deuda y contrato de correo con CON-78. | CON-78 y scheduler integrados; consulta de deuda vigente, deduplicación y pago previo al envío verificados. |
| **CON-80** | Se identifican fuentes de memoria y sus equivalentes SQL. | Pruebas de reservas/notificaciones con dos procesos, reinicios y errores SQL en el ambiente inicial de CON-81. |
| **CON-77** | Se inventarían endpoints, roles, contextos y pruebas existentes. | Contratos y cambios de todos los frentes integrados y matriz ejecutada contra PostgreSQL. |

Orden resumido de integración:

```text
Acuerdos de alcance + contratos + ambiente inicial CON-81
  |
  +--> Identidad: CON-76 + contrato CON-78 --> CON-7
  |
  +--> Finanzas: CON-25 --> CON-27 / CON-28 / CON-26
  |                          |                 |
  |                          +--> CON-14       +--> acciones de CON-24
  |
  +--> Bandeja y evidencia: CON-79 + contrato de listado --> CON-24
  |
  +--> Comunicaciones: CON-78 --> envío real de CON-7 / CON-26 / CON-33
  |
  +--> Persistencia: CON-80 --> pruebas entre procesos y reinicios

CON-77: matriz desde el inicio; aceptación final sobre todo lo integrado.
CON-81: ambiente desde el inicio; cierre con despliegue y recuperación finales.
```

## Etapas de ejecución y orden de PR

### Etapa 0 — Preparar la base común

1. **Gerardo** registra los acuerdos anteriores, reparto y estimaciones pendientes; mantiene el alcance de 14 tickets y enlaza esta planificación en el seguimiento del equipo.
2. **Nicolás** habilita ambiente común y PostgreSQL de pruebas separados; comprueba arranque, dependencias declaradas y revisión de migración. El corte de partida tiene cabeza `20261025_0020`; las migraciones nuevas deben partir del grafo vigente.
3. **Jerson y Alejandro** entregan el contrato de invitación/activación, avisos de cambio de acceso y destinatarios sin departamento activo. **Anderson y Gerardo** fijan estados financieros y consulta de cuenta. **Brandon** acuerda filtros y archivos.
4. Cada frente incorpora especificaciones, OpenAPI y escenarios de aceptación de sus cambios. **Gerardo** consolida los enlaces y **Jerson** revisa su compatibilidad.

**Salida:** contratos mínimos disponibles, un ambiente reproducible y responsables identificados. No hace falta cerrar todos los contratos secundarios para empezar desarrollo independiente.

### Etapa 1 — Desarrollar los seis frentes en paralelo

- Jerson implementa el incremento de CON-76; Alejandro desarrolla el adaptador de CON-78 sobre el contrato compartido.
- Anderson valida CON-25 y completa CON-27/28/26 en una secuencia única de cambios financieros.
- Brandon desarrolla CON-79 y filtros de CON-24; Gerardo desarrolla CON-14 con respuestas de contrato y pruebas de cálculo/presentación.
- Nicolás retira la compatibilidad en memoria de CON-80, manteniendo los bloqueos y eventos SQL existentes.
- Gerardo amplía la matriz de CON-77 con los nuevos endpoints mientras cada autor prueba sus permisos.

**Salida:** incrementos funcionales verificables por frente, con pruebas y PR revisable. Los dobles utilizados durante el desarrollo se conservan únicamente en pruebas.

### Etapa 2 — Integrar productores, consumidores e interfaz

1. Integrar primero las migraciones compatibles y el consumidor de los contratos nuevos; después habilitar sus productores/workers.
2. Integrar invitación/activación CON-76 con correo CON-78; después cerrar el cambio de accesos CON-7 y sus mensajes.
3. Integrar CON-25, luego sus casos CON-27/28/26. Sobre esa respuesta estable, cerrar CON-14 y CON-24/79. Brandon puede fusionar antes los filtros independientes.
4. Integrar CON-33 con el transporte real; comprobar el recorrido de cuota pendiente y de cuota pagada antes del despacho.
5. Integrar CON-80 y volver a probar reserva/cancelación, conflictos y recuperación con SQL como única fuente operativa.

**Salida:** recorridos completos en `develop`, con datos SQL y correo real. Cada PR actualiza su rama con los cambios de los que depende y conserva sus propios resultados de checks.

### Etapa 3 — Aceptación y entrega

1. Cada responsable ejecuta los casos de su sección y entrega evidencia vinculada al commit probado.
2. Gerardo y Jerson completan CON-77; Alejandro coordina la ejecución cruzada de los recorridos de aceptación.
3. Nicolás finaliza CON-81: arranque limpio, revisión final, persistencia tras reinicios y restauración de respaldo en ensayo separado.
4. Gerardo verifica los 14 tickets contra su alcance acordado, actualiza el documento de entrega y prepara el PR de `develop` a `main` con revisión de otro integrante.

**Salida:** evidencia reproducible y aceptación de los 14 elementos. Los tickets con criterios pendientes permanecen abiertos y se identifica su bloqueo concreto.

## Alcance y criterios por ticket

### CON-76 — Completar autenticación, activación y RBAC · Jerson

**Base:** login SQL, JWT v2, `auth_revision`, cuentas activas, cuatro roles y vistas protegidas.

**Debe entregar:**

- Invitación administrativa persistida y activación por enlace con token temporal de un uso; el usuario establece su contraseña. Definir expiración, reenvío, revocación y respuestas ante token inválido/usado/expirado.
- Token almacenado de forma no recuperable desde la base mediante su hash; no registrar tokens, claves ni enlaces completos en logs. Consumir token y habilitar la cuenta atómicamente, evitando doble activación concurrente.
- Pantalla de activación y estados de éxito, error y enlace vencido, integrada con el login. Mantener las cuentas existentes y los privilegios administrativos conforme a su concesión autorizada.
- Integración con la cola de CON-78; el fallo temporal de correo no genera identidades o invitaciones duplicadas al reintentar.
- Una duración JWT configurable y coherente entre configuración, emisión y respuesta de login. Mantener invalidación por cuenta/rol/vínculo.
- Registro de accesos denegados con actor cuando exista, ruta, contexto solicitado, código y correlación, sin secretos. No requiere construir la plataforma completa de observabilidad de S4.

**Termina cuando:** una cuenta invitada activa su acceso desde correo real; un enlace reutilizado/expirado falla; cuentas y roles no autorizados no obtienen permisos; las sesiones revocadas dejan de operar. Las pruebas incluyen PostgreSQL y navegador.

**Trazabilidad:** [alta administrativa previa](../../specs/02-domains/05-usuarios-rbac/alta-administrativa.md), [identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [seguridad](../../specs/01-architecture/security-and-rbac.md). Actualizar el contrato para distinguir claramente alta manual histórica y nueva invitación.

### CON-7 — Cambios de residente o Junta · Jerson

**Base:** gestión SQL de roles/vínculos y revocación mediante `auth_revision`.

**Debe entregar:** recorrido administrativo para retirar/conceder acceso, preservar historial y notificar a los afectados mediante CON-78. Un cambio de Junta respeta la autoridad de SuperAdmin; un cambio de inquilino afecta su vínculo específico. La revocación del responsable de pago conserva la consistencia de su designación y de las políticas históricas de cuotas.

**Termina cuando:** el usuario saliente pierde el acceso operativo correspondiente, el entrante obtiene solo su alcance y los pagos, cuotas, reservas y auditorías permanecen consultables por los usuarios autorizados. El cambio y su aviso se registran sin duplicarse al reintentar; un error de correo se recupera sin deshacer el control de acceso.

**Dependencia particular:** el destinatario saliente puede dejar de tener rol/vínculo activo. Su aviso de seguridad necesita un contrato específico; no se debe permitir por ese motivo enviarle nuevas comunicaciones operativas del departamento.

**Trazabilidad:** [roles y permisos](../../specs/02-domains/05-usuarios-rbac/roles-y-permisos.md), [vínculos](../../specs/02-domains/05-usuarios-rbac/vinculos-departamentos.md), [PROC-05](../../specs/02-processes-and-automations/proc-05-gestion-usuarios.md).

### CON-25 — Aprobar e imputar un pago · Anderson

**Base:** conciliación persistente, prelación, reconstrucción diaria, imputaciones, crédito, auditoría y outbox.

**Debe entregar:** validación y correcciones del motor existente para imputar en orden moras, extraordinarias vencidas, ordinarias vencidas y cuota actual; nunca superar el importe aprobado. Conservar fecha bancaria, snapshots, crédito consumido y restricciones de fondos comprometidos.

**Termina cuando:** aprobación, saldos, auditoría y evento se confirman en una transacción; dos aprobaciones concurrentes o un reintento no duplican aplicaciones; una excepción revierte todos los efectos. La suma de aplicaciones y crédito generado explica el importe del comprobante y el resultado puede recuperarse desde otra sesión.

**Trazabilidad:** [pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [contrato financiero vigente](../../specs/05-api/prorrateo-mora-reportes.md), `src/modules/pagos/persistencia.py`, `contabilidad.py` y `mora_diaria.py`.

### CON-26 — Rechazar u observar un comprobante · Anderson

**Debe entregar:** motivos obligatorios, decisiones persistentes, recorrido UI y correo de resultado con instrucciones. OBSERVADO permite subsanar conservando la historia de evidencias; RECHAZADO conserva su carácter definitivo según el contrato vigente. Una decisión repetida compatible no duplica efectos; una incompatible recibe conflicto controlado.

**Termina cuando:** el comprobante observado/rechazado no genera imputaciones propias, la regularización de mora es explicable y auditable, y el residente recibe el resultado real. Se prueba motivo vacío, revisión repetida, subsanación, fallo de correo y rechazo por rol.

**Integración:** Anderson conserva la producción del resultado/outbox; Alejandro implementa su transporte. Brandon conserva la referencia privada y el historial de archivos.

**Trazabilidad:** [contratos del flujo de pagos](../../specs/05-api/sprint-2-contratos.md), [política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md), [evidencia previa](SPRINT-2-ANDERSON-VERIFICACION.md).

### CON-27 — Registrar un pago parcial · Anderson

**Debe entregar:** pago menor que la deuda siguiendo la prelación de CON-25, saldo restante visible y regla de estados acordada al inicio. Mantener el importe efectivamente pagado separado del exigible; la condición de mora se calcula con fechas y deuda persistidas.

**Termina cuando:** un abono reduce correctamente la deuda, queda identificado como parcial y la reserva sigue bloqueada si existe deuda vencida. Al completar esa deuda se recupera la solvencia sin intervención manual. Actualizar Jira, máquina de estados, API y UI con la misma interpretación de `PAGO_PARCIAL` y `EN_MORA`.

**Trazabilidad:** [máquina de estados de cuotas](../../specs/02-domains/01-cuotas/state-machine.md), [pagos y mora](../../specs/02-domains/02-pagos-y-moras/spec.md), [solvencia integrada](SPRINT-2-ANDERSON-USO.md).

### CON-28 — Registrar un pago en exceso · Anderson

**Debe entregar:** validación del remanente después de cancelar las obligaciones que correspondan, registro de origen del crédito y respuesta consumible por CON-14. Conservar las reglas de precisión y de no reutilizar créditos ya consumidos al reconstruir pagos.

**Termina cuando:** el excedente aparece una sola vez como saldo a favor, tiene origen rastreable y se consume correctamente en una nueva emisión mediante CON-13. Las repeticiones, concurrencia y correcciones no fabrican crédito ni producen saldos negativos.

**Trazabilidad:** [pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [cuotas y crédito](../../specs/02-domains/01-cuotas/spec.md), [ampliación diaria](../../specs/05-api/prorrateo-mora-reportes.md).

### CON-14 — Consultar el estado de cuenta · Gerardo

**Base:** resumen de deuda/crédito del portal y consulta de comprobantes. Falta el detalle completo.

**Debe entregar:**

- Contrato y consulta por departamento y periodo/rango: cargos, abonos aplicados, moras, ajustes, saldo a favor y deuda exigible. Definir saldo inicial/final y el tratamiento de movimientos fuera del periodo.
- Identificadores de origen y orden estable para relacionar un movimiento con cuota, pago, crédito o ajuste. Leer el ledger vigente sin sumar de nuevo recibos históricos ya compensados.
- Pantalla para residente con selección de unidad autorizada, filtros y estados de carga/vacío/error; consulta administrativa contextual cuando corresponda.
- Importes y moneda de fuentes persistentes; dinero como cadena decimal. Presentar pagos EN_REVISION separados de abonos efectivos.

**Termina cuando:** un residente entiende cómo se obtiene su saldo por periodo; ve el origen del crédito de CON-28 y los abonos de CON-27; las correcciones conservan los movimientos originales y sus compensaciones. Un usuario no consulta unidades ajenas manipulando el UUID.

**Trazabilidad:** [dominio de cuotas](../../specs/02-domains/01-cuotas/spec.md), [contrato financiero vigente](../../specs/05-api/prorrateo-mora-reportes.md), `frontend/src/features/residente/ResumenCuenta.tsx` y `src/modules/usuarios/departamentos.py`.

### CON-24 — Bandeja de conciliación · Brandon

**Base:** tabla de comprobantes con voucher, banco, operación, fecha, importe, estado y acciones.

**Debe entregar:** filtros combinables por fecha bancaria, departamento UUID, banco y estado; contrato de rango inclusivo, orden y paginación. Conservar resultados al recargar filtros y mostrar estados vacíos/errores. Junta/SuperAdmin pueden decidir; Auditor consulta; Residente no obtiene la bandeja completa.

**Termina cuando:** los filtros de la interfaz producen el mismo resultado que la API, cada comprobante permite ver evidencia autorizada y ejecutar las decisiones de CON-25/26, y cambiar filtro/condominio no mezcla resultados anteriores.

**Coordinación:** Brandon modifica listado y UI; Anderson mantiene la transacción de revisión. Acordar sus cambios en el archivo compartido `pagos/persistencia.py` antes de abrir PR incompatibles.

**Trazabilidad:** [pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [seguridad](../../specs/01-architecture/security-and-rbac.md), `frontend/src/features/junta/ConciliacionSection.tsx`.

### CON-79 — Almacenamiento privado de evidencias · Brandon

**Base:** storage local privado de vouchers, validación real de PNG/JPEG/PDF hasta 5 MiB, referencias SQL, descarga autenticada e historial de reemplazos. Hay exportación PDF/DOCX de prorrateo.

**Debe entregar:** comprobar y completar el almacenamiento equivalente acordado, su volumen persistente y recuperación; catálogo explícito de tipos/tamaños por clase de documento, nombres generados y permisos de descarga. El límite actual de vouchers no se aplica automáticamente a todos los documentos.

Conservar trazabilidad del reemplazo y de cualquier eliminación autorizada. Si el negocio no permite borrar una evidencia vigente, rechazar esa operación y documentar retención/limpieza de huérfanos. Mantener versión, contexto y controles de los documentos de prorrateo existentes; no crear un módulo de balances de S5 dentro de este ticket.

**Termina cuando:** una evidencia válida se recupera después de reiniciar/restaurar, archivos inválidos y rutas manipuladas se rechazan, y un usuario no descarga evidencias ajenas. Un fallo de disco/storage no informa éxito ni deja una operación financiera parcialmente aceptada.

**Trazabilidad:** [contrato de pagos](../../specs/05-api/sprint-2-contratos.md), [documentos financieros](../../specs/05-api/prorrateo-mora-reportes.md), `src/modules/pagos/storage.py` y `models_persistencia.py`.

### CON-78 — Correo transaccional real · Alejandro

**Base:** cola SQL, plantillas, intentos, reintentos a 2/10/30 minutos, alertas y recuperación. El worker solo transporta SIMULADO.

**Debe entregar:**

- Adaptador SMTP o API configurado por entorno, con timeouts y errores normalizados; configuración del ambiente coordinada con Nicolás.
- Sustitución del rechazo PROVEEDOR_NO_CONFIGURADO cuando el proveedor esté correctamente configurado; no marcar un envío real como exitoso usando transporte simulado.
- Persistencia de cada intento y referencia del proveedor, reintentos, rebote definitivo y alerta. Diferenciar aceptación `ENVIADO` de confirmación `ENTREGADO` cuando exista evidencia del proveedor.
- Manejo de aceptación incierta para evitar reenvíos automáticos ciegos después de una caída; documentar idempotencia o reconciliación según las capacidades del proveedor elegido.
- Contrato compartido con Jerson para invitaciones y avisos de cambio de acceso: cuentan con usuario/contexto, pero pueden carecer de unidad o vínculo activo. Mantener las comprobaciones de destinatarios operativos para pagos, cuotas y reservas.
- Conectar plantillas existentes de cuota, resultado de pago y reservas, además de las nuevas de identidad y recordatorio. Los eventos internos de fondos siguen sin enviarse al residente.

**Termina cuando:** se recibe un correo real en el ambiente demo, cada intento puede seguirse en SQL y los fallos temporales/permanentes se recuperan o escalan de forma controlada. La prueba de envío se realiza sobre cuentas de prueba autorizadas y no sobre el padrón operativo.

**Trazabilidad:** [dominio de notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md), [catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md).

### CON-33 — Recordatorios de vencimiento · Alejandro

**Base:** plantilla NOTIF_RECORDATORIO_PREVIO. Falta productor programado.

**Debe entregar:** configuración de anticipación/canal/hora local; selección SQL de cuotas pendientes próximas a vencer; identidad estable por cuota, fecha programada, destinatario y canal. La programación y su recuperación tras reinicio no deben duplicar recordatorios ni enviar masivamente fechas pasadas sin una política de recuperación explícita.

Revalidar saldo y elegibilidad antes del despacho. Si la cuota se pagó, registrar la supresión sin enviar el recordatorio. Precisar con Anderson cómo coordinar la comprobación con un pago concurrente y qué instante define la elegibilidad; una lectura al encolar no es suficiente. Un voucher pendiente de revisión no equivale a cuota pagada.

**Termina cuando:** se recibe el recordatorio esperado en correo real, una cuota pagada antes del despacho no recibe aviso de deuda y ejecutar dos workers/reintentar no genera mensajes lógicos duplicados. Fecha de Lima, gracia y estados de cuota siguen el contrato acordado.

**Trazabilidad:** [notificaciones](../../specs/02-domains/03-notificaciones/spec.md), [calendario financiero](../../specs/02-domains/01-cuotas/prorrateo-y-mora-diaria.md), [política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md).

### CON-80 — Eliminar fuentes operativas en memoria · Nicolás

**Base:** los módulos principales ya disponen de repositorios persistentes. Reservas conserva `RESERVAS_REGISTRADAS`, combinación SQL/piloto y adopción de reservas desde memoria.

**Debe entregar:** inventario de colecciones temporales utilizadas por rutas/workers; retiro de esas ramas en el flujo normal, incluidos listado, disponibilidad, creación y cancelación. Trasladar los dobles/adaptadores históricos a pruebas. Conservar autorización, locks, transacciones, eventos y comportamiento idempotente.

Una tabla requerida ausente o un fallo SQL produce un error operativo controlado; no presenta calendario libre o éxito utilizando el diccionario piloto. Los datos demo se cargan mediante seed explícito y el login conserva PostgreSQL como fuente.

**Termina cuando:** dos procesos observan la misma reserva/pago/aviso; reiniciar backend y workers conserva operaciones y pendientes; solo una reserva concurrente ocupa el turno y su cancelación lo libera para cualquier proceso. Hay una verificación de que el modo normal no depende de mocks.

**Trazabilidad:** [persistencia del Sprint 2](../../specs/02-domains/04-reservas/persistencia-sprint-2.md), [concurrencia](../../specs/01-architecture/concurrency-and-locking.md), [reservas integradas](CON-73-CON-74-integracion.md).

### CON-81 — Ambiente compartido y recuperación · Nicolás

**Debe entregar:** ambiente demo identificado, configuración documentada, revisión de esquema visible sin credenciales, seed repetible y PostgreSQL de pruebas separado. Instalar las dependencias declaradas para PDF/DOCX y fijar los comandos necesarios para ejecutar pruebas en el entorno compartido.

Probar migraciones desde una instalación limpia y la actualización desde la base soportada. Coordinar el orden de nuevas revisiones con Jerson para conservar una única cabeza de Alembic; no utilizar la reparación legacy como un atajo genérico para adoptar esquemas.

Agregar o documentar una comprobación real de disponibilidad de PostgreSQL y de los servicios necesarios para el recorrido. El `/health` estático actual solo acredita respuesta HTTP de la API. Respaldar base y vouchers/documentos persistentes y demostrar restauración en un ambiente de ensayo separado.

**Termina cuando:** otro integrante puede arrancar el entorno siguiendo la guía, identificar la revisión instalada, iniciar sesión, ejecutar los recorridos del sprint y recuperar un respaldo con sus evidencias privadas. Los servicios/workers necesarios reportan estado verificable y no se alteran datos operativos para probar seeds o restauraciones.

**Trazabilidad:** [README](../../README.md), [operación](../../specs/05-operations/deployment-and-runbooks.md), [seed](../../specs/05-operations/seed-data-spec.md), [CI/CD](../procesos/CI-CD.md), [recuperación anterior](reconciliacion-esquema-20261026.md).

### CON-77 — Aislamiento completo por condominio · Gerardo

**Base:** validaciones de rol/contexto/vínculo y pruebas negativas existentes.

**Debe entregar:** matriz de rutas y acciones con los cuatro roles, condominio autorizado, unidad y resultado esperado; incluir identidad/activación, cuotas, pagos, archivos, reservas, notificaciones, estado de cuenta, condiciones de pago, fondos y exports.

Crear dos condominios de prueba, unidades con igual número y UUID distintos, vínculos activos/revocados y actores administrativos/residentes. Verificar lectura y escritura manipulando UUID, query, body y contexto, incluyendo recursos encadenados de otro condominio. Documentar la excepción legítima del SuperAdmin global; un identificador enviado por el cliente no otorga acceso.

Las rutas públicas de activación se autorizan mediante su token específico y no conceden lectura de recursos antes de autenticar. Auditor conserva lectura autorizada; cuentas/roles/vínculos revocados pierden el acceso previsto. Corregir las brechas encontradas con el dueño del módulo y volver a ejecutar sus casos.

**Termina cuando:** la matriz actual se ejecuta contra PostgreSQL y navegador, no mezcla datos entre contextos y conserva los rechazos controlados sin efectos parciales. Se acredita tanto el acceso válido como el denegado para cada grupo de rutas.

**Trazabilidad:** [seguridad](../../specs/01-architecture/security-and-rbac.md), [identidad](../../specs/02-domains/05-usuarios-rbac/identidad-y-alcances.md), [aceptación de autenticación/RBAC](../../specs/04-acceptance-criteria/auth-and-rbac.feature.md).

## Contratos compartidos y archivos con cambios concurrentes

| Contrato / superficie | Quién lo conduce | Consumidores / coordinación |
|---|---|---|
| Invitación, token, activación y avisos de identidad | Jerson | Alejandro implementa cola/transporte; Nicolás integra migraciones/configuración; Gerardo valida permisos. |
| Estado de cuota, abonos, crédito y ledger vigente | Anderson | Gerardo consume en CON-14; Brandon en CON-24; Alejandro selecciona deuda para CON-33. |
| Listado de comprobantes, filtros y paginación | Brandon | Anderson revisa consultas, permisos y compatibilidad con decisiones. |
| Archivo privado, referencia y retención | Brandon | Anderson conserva consistencia del reporte/revisión; Nicolás mantiene volumen y respaldo. |
| Programación, entrega e idempotencia de mensajes | Alejandro | Jerson/Anderson producen hechos; Nicolás mantiene worker y ambiente. |
| Migraciones nuevas y grafo de Alembic | Jerson revisa; cada autor escribe la migración de su cambio | Nicolás coordina orden de integración y prueba la cabeza resultante. No editar revisiones históricas para incorporar nuevas funciones. |
| OpenAPI, eventos y matriz de trazabilidad | Cada autor actualiza su parte; Gerardo consolida | Acordar nombres/campos antes de implementar consumidores. |

Cada frente trabaja desde `develop` actualizado y presenta PR pequeños vinculados a sus tickets según [CONTRIBUTING.md](../../CONTRIBUTING.md). Los cambios de `pagos/persistencia.py`, `usuarios/service.py`, notificaciones y contratos compartidos se coordinan antes de fusionar. El mismo archivo compartido no se convierte en motivo para crear un segundo motor o repositorio incompatible.

## Guion mínimo de aceptación integrada

Datos de prueba: dos condominios A/B, SuperAdmin, Junta y Auditor por contexto, residentes con varias unidades y unidades de igual número en edificios distintos. Preparar fechas fijas de Lima y cuotas identificables; suspender o controlar el reloj de workers en pruebas para que los importes esperados sean reproducibles.

| Recorrido | Pasos y resultado observable | Tickets / responsable de evidencia |
|---|---|---|
| Invitación y activación | Crear invitación, recibir correo, elegir contraseña e iniciar sesión. Reutilizar/vencer el enlace produce error y no eleva permisos. | CON-76/78 · Jerson y Alejandro |
| Relevo de accesos | Revocar inquilino o Junta, registrar reemplazo y probar token anterior/nuevo login. Historial intacto y avisos a afectados trazables. | CON-7/76 · Jerson |
| Bandeja y evidencias | Combinar los cuatro filtros, abrir voucher y decidir un pago. Auditor puede leer pero no decidir; residente no accede a la bandeja completa. | CON-24/79/77 · Brandon y Gerardo |
| Aprobación exacta | Con deuda fija 100.00 y sin nuevos devengos durante el caso, aprobar 100.00: deuda cero. Repetir aprobación no duplica aplicaciones. | CON-25 · Anderson |
| Pago parcial | Sobre deuda fija 100.00, aprobar 40.00: pendiente 60.00. Si es vencida, conserva bloqueo; completar deuda recupera solvencia. | CON-27/14 · Anderson y Gerardo |
| Excedente y emisión | Sobre deuda fija 100.00, aprobar 120.00: aplica 100.00 y genera 20.00 de crédito con origen visible. Una nueva cuota consume el crédito una vez. | CON-28/14 y regresión CON-13 · Anderson y Gerardo |
| Observación/rechazo | Motivo obligatorio, cero imputación propia, correo con instrucciones; subsanar un observado conserva las evidencias y la revisión histórica. | CON-26/78/79 · Anderson, Alejandro y Brandon |
| Recordatorio | Seleccionar cuota próxima a vencer; correr scheduler dos veces y despachar: un aviso lógico. Pagar otra cuota encolada antes del despacho: no recibe aviso de deuda. | CON-33/78 · Alejandro |
| Persistencia y concurrencia | Crear reserva, consultar desde otro proceso y reiniciar; mismo UUID/estado. Dos solicitudes al mismo turno: una confirmada, otra conflicto. Cancelar libera el turno para ambos procesos. | CON-80 · Nicolás con Brandon |
| Cruce de condominios | Alterar IDs en cuenta, pagos, voucher, reserva, usuario, fondo y export: rechazo sin lectura ni modificación ajena. | CON-77 · Gerardo con Jerson |
| Recuperación | Respaldar base y evidencias demo, restaurar en ensayo y repetir lecturas autenticadas. Cola e intentos continúan sin duplicar efectos. | CON-81/79/78 · Nicolás con responsables |

Agregar casos financieros de mora diaria, pago bancario retroactivo, rollback por fallo de auditoría y fondos comprometidos conforme al contrato vigente. Los ejemplos simples anteriores no sustituyen esas regresiones.

## Verificación y evidencia de entrega

La [revisión inicial del 28/10](SPRINT-3-REVISION.md) obtuvo 347 pruebas backend aprobadas, 302 omitidas y una fallida por dependencia de PostgreSQL; 22 pruebas JavaScript, TypeScript y SDD pasaron. Ese resultado corresponde al entorno y código anteriores a las correcciones de entrega.

La preparación posterior del [PR #29](https://github.com/NikoTS04/CondoManager/pull/29) validó **651 pruebas backend y cobertura del 92,15 % en GitHub**, **326 pruebas de integración PostgreSQL** y contratos **68 + 24 sin omisiones**. También comprobó los flujos de pagos y reservas en Chromium y su persistencia tras reiniciar API y workers. La evidencia se detalla en la [validación del candidato del Sprint 2](SPRINT-2-VALIDACION-PR25.md) y en los resultados finales del PR. Las correcciones ya están en `develop` y en la entrega a `main`; no hay un fallo backend pendiente acreditado únicamente por aquella ejecución inicial sin PostgreSQL.

**Son resultados de la base del Sprint 2, no del Sprint 3 terminado ni una certificación del ambiente compartido.** La revisión documental no incluyó una nueva ejecución manual de la suite funcional; cada incremento debe producir su propia evidencia y completar los checks aplicables de su PR.

Nicolás prepara las dependencias declaradas de desarrollo y el PostgreSQL exclusivo de pruebas. En ese entorno se ejecutan los checks aplicables de [CI/CD](../procesos/CI-CD.md), incluyendo:

```powershell
# Desde la raíz, con dependencias instaladas y variables de pruebas configuradas.
python -X utf8 -m pytest -q --cov --junitxml=pytest.xml
python -X utf8 scripts/verify_sdd_compliance.py

# Desde frontend/, con sus dependencias instaladas.
node --test tests/*.test.mjs
npm run lint
npx --no-install tsc --noEmit
npm run build
```

Configurar `CON3_TEST_DATABASE_URL` y `CON13_TEST_DATABASE_URL` contra la base exclusiva de pruebas. Usar el comando de migraciones del entorno y verificar el ciclo en una base desechable conforme al workflow; los downgrades protegidos de datos financieros se evalúan con sus pruebas y no se ejecutan sobre la demo para satisfacer un check.

Cada responsable adjunta a su PR o documento de entrega:

- Ticket y criterios cubiertos; commit probado y entorno/revisión de esquema.
- Comando ejecutado, resultado, omisiones y motivo; reporte de pruebas y cobertura cuando corresponda.
- Datos identificables de prueba, pasos y respuestas/capturas de navegador de los casos exitosos y rechazados.
- Evidencia SQL, referencia de mensaje/intentos o recuperación según la operación, sin secretos.
- Limitaciones pendientes y dependencia concreta que impide el cierre, si existe.

Mantener en este directorio las entregas por frente (`CON-7-76`, `CON-14-77`, `CON-24-79`, `CON-25-28`, `CON-33-78`, `CON-80-81`) y un índice final `SPRINT-3-ENTREGA.md` cuando existan resultados. Estos documentos son entregables futuros; no están creados ni acreditados por este plan.

## Definición de Terminado del sprint

Una historia o tarea técnica queda terminada cuando:

1. Cumple sus criterios refinados en Jira y las especificaciones del incremento pendiente, con una demostración identificable.
2. Tiene código integrado en `develop` mediante PR revisado por otro integrante y checks aplicables en verde.
3. Sus datos, auditoría, claves de idempotencia y mensajes pendientes persisten; los reinicios y la concurrencia no duplican efectos.
4. Respeta los cuatro roles, condominio y vínculos vigentes; los cambios de acceso invalidan las sesiones previstas.
5. Conserva precisión decimal, historial y reglas de conciliación/mora/fondos de la base financiera actual.
6. Usa correo real para los avisos comprometidos; cada resultado indica si es encolado, aceptado, entregado o fallido según la evidencia disponible.
7. Mantiene vouchers/documentos privados, referencias y trazabilidad al reemplazar, limpiar o restaurar archivos.
8. Tiene OpenAPI, eventos, modelos de datos, escenarios BDD y documentación de uso/operación actualizados cuando cambian sus contratos.
9. Incluye pruebas reales de PostgreSQL y los recorridos de navegador aplicables. Las omisiones de casos críticos no se cuentan como aprobaciones.
10. Forma parte del guion integrado, con evidencia reproducible, sin depender de memoria temporal o contactos/éxitos inventados.

El cierre del sprint requiere los 14 elementos aceptados o una reducción explícita y registrada de alcance. La preparación documental, un transporte simulado o un `/health` estático no acreditan por sí solos esa aceptación.
