# Backlog de épicas e historias de usuario — CondoManager

Este backlog traduce las especificaciones funcionales de CondoManager a elementos que pueden copiarse manualmente a Jira.

## Resumen

- **9 épicas**.
- **60 historias de usuario base**.
- Las historias cubren el alcance funcional completo documentado.
- Las tareas puramente técnicas —crear tablas, endpoints, componentes o pruebas— deberían registrarse en Jira como subtareas de la historia correspondiente.

## Plantilla recomendada para Jira

**Resumen:** título corto de la historia.  
**Descripción:** Como `[rol]`, quiero `[necesidad]`, para `[beneficio]`.  
**Criterios de aceptación:** condiciones observables que deben cumplirse para considerar terminada la historia.

---

# Mapa de historias de usuario

El mapa representa el recorrido principal del producto de izquierda a derecha.

| Actividad principal | Pasos del usuario o del negocio | Historias relacionadas |
|---|---|---|
| Configurar el condominio | Crear condominio → cargar departamentos → configurar reglas y alícuotas | USR-01, USR-02, CUE-01, CUE-02 |
| Incorporar usuarios | Crear usuario → vincular departamento → asignar rol → activar acceso | USR-03 a USR-06 |
| Generar obligaciones | Aprobar presupuesto → emitir cuotas → aplicar saldos → consultar cuenta | CUE-01 a CUE-06 |
| Recaudar y conciliar | Reportar voucher → detectar duplicados → revisar → aprobar/rechazar → imputar | PAG-01 a PAG-07 |
| Gestionar morosidad | Detectar vencimiento → proteger pagos en revisión → aplicar mora → corregir excepciones | PAG-08 a PAG-10 |
| Comunicar resultados | Crear aviso → seleccionar canal → ejecutar bot RPA → verificar persistencia → enviar → comprobar entrega → reintentar y reportar | NOT-01 a NOT-08 |
| Reservar áreas | Consultar disponibilidad → validar solvencia → reservar → pagar/cancelar | RES-01 a RES-09 |
| Administrar gastos | Registrar proveedor → contrato → egreso → pago → controlar vencimiento | EGR-01 a EGR-05 |
| Atender incidencias | Reportar → clasificar → asignar → resolver → confirmar cierre | TIC-01 a TIC-05 |
| Supervisar la gestión | Consultar KPIs → cerrar periodo → generar balance → publicar reportes | REP-01 a REP-05 |
| Controlar y recuperar | Auditar → impedir duplicados → gestionar excepciones → reintentar → monitorear | TRV-01 a TRV-06 |

## Cortes de entrega sugeridos

### Entrega 1 — MVP demostrable

- Configuración del condominio y departamentos.
- Usuarios básicos y relación con departamentos.
- Emisión de cuotas.
- Reporte y conciliación de pagos.
- Aplicación de mora.
- Notificaciones por correo.
- Catálogo y reserva con bloqueo por morosidad.
- Auditoría básica.

### Entrega 2 — Operación administrativa completa

- Cuotas extraordinarias y correcciones.
- Notificaciones multicanal, comunicaciones masivas y bot RPA de recordatorios por WhatsApp.
- Reglas avanzadas y cancelación de reservas.
- Proveedores, contratos y egresos.
- Tickets de incidencias.
- Dashboard y balances mensuales.

### Entrega 3 — Robustez y escalabilidad

- Multi-condominio completo.
- Cadena criptográfica de auditoría.
- Gestión centralizada de excepciones.
- Reintentos y fallos permanentes.
- Reportes avanzados y controles operativos.

---

# ÉPICA USR — Usuarios, roles y estructura del condominio

**Objetivo de la épica:** administrar condominios, departamentos, residentes y permisos de acceso.

## USR-01 — Configurar un condominio

**Historia:** Como superadministrador, quiero registrar y configurar un condominio, para que sus operaciones se administren de manera independiente.

**Criterios de aceptación:**

- Dado un usuario SuperAdmin, cuando registra nombre, dirección, moneda y reglas generales válidas, entonces el condominio queda creado y activo.
- El SuperAdmin puede listar los condominios activos y seleccionar el contexto sobre el cual operará.
- Un usuario sin permisos de SuperAdmin no puede crear condominios.
- Los datos de un condominio no deben mezclarse con los de otro.

**Trazabilidad:** [especificación de dominio](../../specs/02-domains/05-usuarios-rbac/spec.md), [proceso PROC-05](../../specs/02-processes-and-automations/proc-05-gestion-usuarios.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [contrato de API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml), [BDD ejecutable](../../specs/02-domains/05-usuarios-rbac/features/condominios.feature), [criterios BDD detallados](../../specs/04-acceptance-criteria/auth-and-rbac.feature.md), [matriz de trazabilidad](../../specs/00-core/traceability-matrix.md).

## USR-02 — Registrar edificios y departamentos

**Historia:** Como administrador, quiero registrar o importar edificios y departamentos, para disponer de la estructura inmobiliaria sobre la cual operar.

**Criterios de aceptación:**

- Se pueden registrar número, piso, edificio y coeficiente de cada departamento.
- No puede existir el mismo número de departamento dos veces dentro del mismo edificio o condominio.
- El sistema informa las filas inválidas de una importación sin duplicar las válidas ya procesadas.

## USR-03 — Crear e invitar usuarios

**Historia:** Como administrador, quiero crear usuarios y enviarles una invitación, para que puedan activar su cuenta y acceder al sistema.

**Criterios de aceptación:**

- El correo y documento de identidad deben ser válidos y únicos según las reglas definidas.
- Al crear el usuario, se genera un token de activación y se solicita a Notificaciones el envío de la invitación.
- La cuenta permanece inactiva hasta que el usuario establezca su contraseña.

## USR-04 — Vincular usuarios con departamentos

**Historia:** Como administrador, quiero relacionar propietarios e inquilinos con sus departamentos, para delimitar la información y operaciones que pueden realizar.

**Criterios de aceptación:**

- Un propietario puede estar vinculado con uno o varios departamentos.
- Un inquilino solo accede a los departamentos cuyo vínculo se encuentre vigente.
- Cada departamento debe tener al menos un propietario titular registrado.

## USR-05 — Asignar roles y permisos

**Historia:** Como administrador autorizado, quiero asignar roles a los usuarios, para controlar las funciones y datos que pueden utilizar.

**Criterios de aceptación:**

- Se admiten los roles SuperAdmin, Admin/Junta, Auditor, Propietario e Inquilino.
- Cada operación protegida valida el rol y el condominio del usuario.
- Un residente solo puede consultar y modificar información de sus departamentos vinculados.

## USR-06 — Gestionar cambios de residente o junta directiva

**Historia:** Como administrador, quiero desactivar vínculos y roles anteriores y registrar los nuevos, para mantener actualizados los accesos sin perder el historial.

**Criterios de aceptación:**

- Al finalizar un arrendamiento, el inquilino pierde acceso operativo al departamento.
- Los pagos, cuotas, reservas y auditorías históricas permanecen asociados al departamento.
- Todo cambio de rol o vínculo queda auditado y se comunica a los usuarios afectados.

---

# ÉPICA CUE — Cuotas y obligaciones de mantenimiento

**Objetivo de la épica:** calcular, emitir y consultar las obligaciones económicas de los departamentos.

## CUE-01 — Registrar el presupuesto mensual

**Historia:** Como miembro de la junta, quiero registrar el presupuesto aprobado del periodo, para utilizarlo como base de las cuotas de mantenimiento.

**Criterios de aceptación:**

- El presupuesto debe indicar condominio, periodo, moneda, monto total y fecha de vencimiento.
- Solo usuarios autorizados pueden aprobar o modificar un presupuesto.
- No se puede emitir el lote ordinario sin un presupuesto aprobado.

## CUE-02 — Configurar el método de distribución

**Historia:** Como administrador, quiero definir si las cuotas se calculan por alícuota o de forma equitativa, para aplicar la regla aprobada por el condominio.

**Criterios de aceptación:**

- El sistema permite seleccionar distribución porcentual o cuota fija equitativa.
- Para distribución porcentual, la suma de alícuotas activas debe ser exactamente 100.0000 %.
- Los cálculos monetarios se realizan con precisión decimal y redondeo a dos decimales.

## CUE-03 — Emitir automáticamente las cuotas mensuales

**Historia:** Como administrador, quiero que el sistema emita las cuotas al comenzar el mes, para evitar cálculos y registros manuales repetitivos.

**Criterios de aceptación:**

- El día configurado, el sistema genera una cuota para cada departamento activo.
- El total emitido debe coincidir con el presupuesto, considerando el ajuste de redondeo definido.
- Una segunda ejecución para el mismo condominio y periodo no genera cuotas duplicadas.

## CUE-04 — Emitir cuotas extraordinarias

**Historia:** Como administrador, quiero emitir cuotas extraordinarias respaldadas por un acuerdo, para financiar obras o necesidades no incluidas en el presupuesto ordinario.

**Criterios de aceptación:**

- La emisión exige concepto, monto, documento o acta de respaldo y número de fracciones.
- El sistema distribuye el monto con el método autorizado para el condominio.
- La cuota extraordinaria aparece diferenciada en el estado de cuenta.

## CUE-05 — Aplicar automáticamente saldos a favor

**Historia:** Como residente, quiero que mi saldo a favor se descuente de las nuevas cuotas, para pagar únicamente el importe neto pendiente.

**Criterios de aceptación:**

- Si el saldo cubre toda la cuota, esta queda PAGADA y se conserva el remanente.
- Si el saldo cubre una parte, la cuota queda PENDIENTE por la diferencia.
- La aplicación del saldo genera un movimiento de auditoría.

## CUE-06 — Consultar el estado de cuenta

**Historia:** Como propietario o inquilino autorizado, quiero consultar las cuotas, pagos, moras y saldos de mi departamento, para conocer mi situación financiera.

**Criterios de aceptación:**

- El estado de cuenta muestra cargos, abonos, saldo a favor y deuda exigible por periodo.
- El residente solo puede ver departamentos asociados con su cuenta.
- Los movimientos históricos no desaparecen aunque se realice una corrección contable.

---

# ÉPICA PAG — Pagos, conciliación y morosidad

**Objetivo de la épica:** registrar comprobantes, conciliarlos, imputar pagos y gestionar penalidades por atraso.

## PAG-01 — Reportar un comprobante de pago

**Historia:** Como residente, quiero registrar los datos y la evidencia de mi pago, para que la junta pueda validarlo.

**Criterios de aceptación:**

- El formulario solicita departamento, banco, operación, fecha, monto y archivo del voucher.
- Solo se aceptan formatos y tamaños de archivo permitidos.
- Un reporte válido se registra como EN_REVISION y no modifica todavía el saldo.

## PAG-02 — Evitar comprobantes duplicados

**Historia:** Como tesorero, quiero que el sistema detecte vouchers repetidos, para evitar doble aplicación o reutilización de un pago.

**Criterios de aceptación:**

- El sistema calcula una clave con condominio, banco, operación, fecha y monto normalizados.
- Si la clave ya existe, no se crea un segundo comprobante.
- La respuesta informa si el voucher ya fue conciliado o continúa en evaluación.

## PAG-03 — Consultar la bandeja de conciliación

**Historia:** Como tesorero, quiero revisar los comprobantes pendientes junto con sus datos, para conciliarlos con los movimientos bancarios.

**Criterios de aceptación:**

- La bandeja permite filtrar comprobantes por fecha, departamento, banco y estado.
- Cada registro muestra el voucher, datos declarados y departamento asociado.
- Solo usuarios con permiso de conciliación pueden acceder a la bandeja completa.

## PAG-04 — Aprobar e imputar un pago

**Historia:** Como tesorero, quiero aprobar un comprobante verificado, para reducir correctamente las deudas del departamento.

**Criterios de aceptación:**

- Un comprobante aprobado se aplica en el orden: moras, extraordinarias vencidas, ordinarias vencidas y cuota actual.
- La suma de imputaciones no puede superar el monto aprobado.
- La aprobación actualiza saldos de forma atómica y genera auditoría.

## PAG-05 — Rechazar u observar un comprobante

**Historia:** Como tesorero, quiero rechazar u observar comprobantes inválidos, para solicitar una corrección sin afectar los saldos.

**Criterios de aceptación:**

- El rechazo exige un motivo explícito.
- Un comprobante observado o rechazado no genera imputaciones.
- El residente recibe una notificación con el resultado y las instrucciones correspondientes.

## PAG-06 — Registrar un pago parcial

**Historia:** Como tesorero, quiero aplicar pagos menores que la deuda, para reflejar el abono sin cerrar obligaciones pendientes.

**Criterios de aceptación:**

- El importe se aplica siguiendo el orden de prelación.
- La cuota afectada queda PAGO_PARCIAL cuando aún existe saldo exigible.
- Si persiste deuda en mora, el bloqueo de reservas continúa activo.

## PAG-07 — Registrar un pago en exceso

**Historia:** Como residente, quiero que el excedente de un pago aprobado quede a mi favor, para utilizarlo en obligaciones futuras.

**Criterios de aceptación:**

- Primero se cancelan las obligaciones existentes.
- El remanente se registra como saldo a favor del departamento.
- El estado de cuenta muestra el origen y monto del crédito.

## PAG-08 — Aplicar automáticamente la mora

**Historia:** Como junta directiva, quiero que el sistema aplique la penalidad después del vencimiento y la gracia, para tratar a todos los residentes con la misma regla.

**Criterios de aceptación:**

- La evaluación se ejecuta diariamente sobre cuotas pendientes o parcialmente pagadas.
- La mora solo se aplica cuando terminó el periodo de gracia y no existe protección vigente.
- Al aplicarse, la cuota pasa a EN_MORA, se recalcula la deuda y se bloquean reservas.

## PAG-09 — Proteger pagos pendientes de revisión

**Historia:** Como residente, quiero que la mora se postergue si reporté mi pago oportunamente, para no ser penalizado por una demora administrativa.

**Criterios de aceptación:**

- Si existe un comprobante EN_REVISION, el sistema pospone la penalidad durante 24 horas.
- La junta recibe una alerta para revisar el comprobante pendiente.
- Si el comprobante es rechazado o vence la protección, la cuota vuelve a ser evaluada.

## PAG-10 — Exonerar o revertir una mora

**Historia:** Como administrador autorizado, quiero corregir una mora indebidamente aplicada, para resolver reclamos sin borrar el historial contable.

**Criterios de aceptación:**

- La operación exige justificación y permiso administrativo.
- La corrección se realiza mediante un asiento compensatorio, no eliminando el cargo original.
- Los saldos, estados y permisos de reserva se recalculan y auditan.

---

# ÉPICA NOT — Notificaciones y comunicaciones

**Objetivo de la épica:** enviar comunicaciones trazables sobre cuotas, pagos, moras, reservas y operaciones administrativas.

## NOT-01 — Notificar la emisión de una cuota

**Historia:** Como residente, quiero recibir el aviso de mi nueva cuota, para conocer el monto y la fecha límite de pago.

**Criterios de aceptación:**

- El aviso contiene periodo, departamento, monto, vencimiento y medios de pago.
- Se envía a los destinatarios configurados para el departamento.
- Cada intento queda registrado en la bitácora de notificaciones.

## NOT-02 — Enviar recordatorios de vencimiento

**Historia:** Como residente, quiero recibir recordatorios antes de la fecha de corte, para evitar atrasos y penalidades.

**Criterios de aceptación:**

- El sistema identifica cuotas con saldo pendiente próximas a vencer.
- El recordatorio se envía en los días y canales configurados.
- No se envía un recordatorio de deuda para una cuota ya pagada.

## NOT-03 — Comunicar el resultado de un pago

**Historia:** Como residente, quiero recibir el resultado de la revisión de mi comprobante, para saber si fue aprobado, observado o rechazado.

**Criterios de aceptación:**

- La recepción del voucher genera una confirmación inicial.
- La aprobación comunica el monto aplicado y el nuevo saldo.
- El rechazo u observación comunica el motivo y cómo subsanarlo.

## NOT-04 — Notificar mora y cambios de solvencia

**Historia:** Como residente, quiero ser informado cuando se aplique o levante una mora, para conocer mi deuda y el estado de mis permisos.

**Criterios de aceptación:**

- El aviso de mora incluye penalidad, deuda total y restricción de reservas.
- Al quedar sin deuda vencida, se comunica la rehabilitación de las reservas.
- Ambos eventos quedan vinculados con el departamento y la operación de origen.

## NOT-05 — Notificar reservas y otras operaciones

**Historia:** Como usuario, quiero recibir confirmaciones de reservas, activaciones y cambios relevantes, para disponer de evidencia de cada operación.

**Criterios de aceptación:**

- Una reserva confirmada comunica área, fecha, horario, costo y normas.
- Una cancelación informa que el horario fue liberado y si existió ajuste económico.
- Las invitaciones de usuario y alertas administrativas usan plantillas diferenciadas.

## NOT-06 — Reintentar notificaciones fallidas

**Historia:** Como administrador, quiero que el sistema reintente automáticamente los envíos fallidos, para superar interrupciones temporales del proveedor.

**Criterios de aceptación:**

- Los errores temporales generan reintentos a los 2, 10 y 30 minutos.
- Un envío ya ENTREGADO no se vuelve a enviar por un reintento duplicado.
- Después del último fallo, queda FALLIDO_PERMANENTE y se alerta al administrador.

## NOT-07 — Enviar comunicaciones generales

**Historia:** Como administrador, quiero enviar comunicados a grupos de residentes, para informar cortes de servicios, reuniones u otros asuntos comunitarios.

**Criterios de aceptación:**

- El administrador puede seleccionar audiencia, canal, asunto y contenido.
- Antes de confirmar se muestra la cantidad de destinatarios.
- El resultado permite conocer entregas, reintentos y fallos permanentes.

## NOT-08 — Ejecutar y controlar el bot RPA de recordatorios por WhatsApp

**Historia:** Como administrador del condominio, quiero que un bot RPA identifique las cuotas próximas a vencer, registre y verifique las notificaciones antes de enviarlas por WhatsApp, para reducir la morosidad y disponer de evidencia de que todos los registros del proceso fueron tratados correctamente.

**Valor de negocio:** Automatizar una tarea repetitiva de cobranza preventiva, reducir omisiones manuales y ofrecer un control de calidad cuantificable sobre cada ejecución masiva.

**Disparador:** El bot se ejecuta automáticamente a la hora configurada —por defecto, a las 08:00, tres días antes del vencimiento— o manualmente por un administrador autorizado.

**Flujo RPA requerido:**

1. **Solicitud:** recibe la ejecución programada o manual y genera un identificador único de proceso.
2. **Leer datos:** consulta las cuotas con saldo pendiente cuya fecha de vencimiento se encuentre dentro del rango configurado, junto con el residente y su número de WhatsApp.
3. **Validar:** comprueba que la cuota continúe pendiente, que el destinatario sea válido, que exista autorización de contacto y que la notificación no haya sido procesada previamente.
4. **Registrar:** crea un lote de ejecución y persiste una notificación en estado `EN_COLA` por cada cuota válida, antes de realizar el envío.
5. **Verificar:** compara los registros esperados con los persistidos, identifica faltantes, duplicados o datos incompletos y solo autoriza el envío cuando el lote sea consistente.
6. **Reportar:** informa los totales leídos, válidos, guardados, enviados, entregados, pendientes, omitidos y fallidos, junto con los motivos de cada excepción.

**Criterios de aceptación:**

- Cada ejecución genera un `proceso_id` único y registra la fecha, hora, disparador y parámetros utilizados.
- Solo se seleccionan cuotas con saldo pendiente que se encuentren dentro del rango de proximidad al vencimiento configurado.
- Una cuota pagada, un contacto inválido o una notificación ya procesada no produce un nuevo envío; la exclusión queda registrada con su motivo.
- Antes de enviar mensajes, el bot registra el lote y sus detalles en PostgreSQL dentro de una transacción.
- El control de persistencia compara `total_esperado`, `total_guardado` y `total_unicos`, y calcula las cantidades de registros faltantes, duplicados e inválidos.
- Si el proceso genera 100 notificaciones válidas, la verificación solo es exitosa cuando existen 100 registros persistidos, 100 claves de negocio distintas, 0 faltantes y 0 duplicados.
- La comprobación se repite desde una nueva sesión de base de datos después de confirmar la transacción, para demostrar que los registros no permanecen únicamente en memoria.
- Si la cantidad guardada no coincide con la esperada, el lote queda `FALLIDO_CONTROL`, no se informa un éxito general y se genera una alerta con los identificadores faltantes o duplicados.
- Cada detalle utiliza una clave de idempotencia; reejecutar el mismo proceso no crea registros ni mensajes duplicados.
- Después de superar el control, el bot envía el mensaje mediante el proveedor de WhatsApp y conserva el identificador y la respuesta retornados por dicho proveedor.
- Cada notificación termina en uno de los estados `ENTREGADO`, `REINTENTANDO`, `FALLIDO_PERMANENTE` u `OMITIDO`.
- Los errores temporales siguen la política de reintentos definida en NOT-06 y los errores permanentes se remiten a revisión manual.
- El reporte final diferencia claramente entre registros guardados y mensajes entregados; tener 100 registros persistidos no implica que los 100 mensajes hayan sido entregados.
- La ejecución y su resultado quedan vinculados con la bitácora de auditoría para reconstruir quién o qué inició el proceso, qué datos se procesaron y cuál fue el resultado.

**Ejemplo de reporte de control:**

```text
Proceso: RPA-WSP-2026-10-07-001
Cuotas leídas:                  105
Notificaciones válidas:         100
Registros esperados:             100
Registros guardados:             100
Claves únicas:                   100
Faltantes:                         0
Duplicados:                        0
Mensajes entregados:              98
Pendientes de reintento:           1
Fallidos permanentes:              1
Control de persistencia: VERIFICADO
Resultado general: COMPLETADO CON OBSERVACIONES
```

**Respuesta ante excepciones:**

- Si falla la lectura de datos, el proceso se detiene y reporta el componente no disponible.
- Si falla la transacción de registro, se ejecuta `ROLLBACK` y no se envían mensajes del lote incompleto.
- Si la verificación posterior encuentra diferencias, el proceso conserva la evidencia, queda en excepción y permite reintentar solamente los elementos faltantes.
- Si falla WhatsApp después de guardar correctamente el lote, los registros permanecen disponibles para reintento sin duplicar la notificación.

**Dependencias:** NOT-02 — Recordatorios de vencimiento; NOT-06 — Reintentos; CUE-06 — Estado de cuenta; TRV-01 — Auditoría; TRV-05 — Idempotencia de tareas automáticas.

---

# ÉPICA RES — Reservas de áreas comunes

**Objetivo de la épica:** administrar espacios compartidos, disponibilidad, solvencia y concurrencia de reservas.

## RES-01 — Administrar el catálogo de áreas comunes

**Historia:** Como administrador, quiero configurar las áreas comunes, para publicar sus condiciones de uso y reserva.

**Criterios de aceptación:**

- Cada área registra nombre, descripción, aforo, horarios, costo y estado activo.
- Un área inactiva no puede recibir nuevas reservas.
- Los residentes pueden consultar las áreas activas y sus reglas.

## RES-02 — Consultar disponibilidad

**Historia:** Como residente, quiero consultar fechas y horarios disponibles, para escoger una opción antes de solicitar la reserva.

**Criterios de aceptación:**

- La consulta puede filtrarse por área y fecha.
- Las reservas confirmadas o bloqueos de mantenimiento aparecen como no disponibles.
- La consulta no expone información privada de otros residentes.

## RES-03 — Reservar siendo un departamento solvente

**Historia:** Como residente al día, quiero reservar un área disponible, para utilizar los espacios comunes.

**Criterios de aceptación:**

- El sistema valida la relación del usuario con el departamento.
- Si el departamento está solvente y el horario cumple las reglas, la reserva queda CONFIRMADA.
- Se registra la operación y se solicita el envío de la confirmación.

## RES-04 — Bloquear reservas por deuda vencida

**Historia:** Como junta directiva, quiero impedir reservas de departamentos morosos, para aplicar automáticamente la política de solvencia.

**Criterios de aceptación:**

- Un departamento con deuda EN_MORA recibe una denegación antes de bloquear el horario.
- La respuesta informa claramente el motivo y el saldo vencido.
- Cuando se cancela toda la deuda vencida, el permiso se restablece automáticamente.

## RES-05 — Evitar reservas simultáneas

**Historia:** Como residente, quiero que un horario solo pueda asignarse una vez, para evitar conflictos entre vecinos.

**Criterios de aceptación:**

- Las solicitudes concurrentes sobre el mismo intervalo se procesan de forma atómica.
- Exactamente una solicitud puede quedar CONFIRMADA.
- Las demás reciben un conflicto controlado sin crear reservas duplicadas.

## RES-06 — Aplicar reglas y límites de uso

**Historia:** Como administrador, quiero definir anticipación, duración y límites por departamento, para distribuir equitativamente las áreas comunes.

**Criterios de aceptación:**

- Se valida la anticipación mínima y máxima de la solicitud.
- Se valida la duración, aforo y cantidad máxima de reservas activas.
- El rechazo identifica la regla incumplida.

## RES-07 — Generar el cargo de una reserva

**Historia:** Como tesorero, quiero que las reservas con tarifa generen un cargo, para incorporar el uso o limpieza al estado de cuenta.

**Criterios de aceptación:**

- Una reserva confirmada con costo genera un cargo por el importe configurado.
- Una reserva gratuita no genera movimientos monetarios.
- El cargo queda vinculado con la reserva y visible en el estado de cuenta.

## RES-08 — Cancelar una reserva

**Historia:** Como residente, quiero cancelar una reserva dentro del plazo permitido, para liberar el horario cuando ya no vaya a utilizarlo.

**Criterios de aceptación:**

- Se valida el plazo de cancelación o la autorización administrativa.
- Al cancelar, el horario vuelve a estar disponible.
- Si existió un cobro reembolsable, se genera un ajuste compensatorio.

## RES-09 — Bloquear áreas por mantenimiento

**Historia:** Como administrador, quiero bloquear temporalmente un área, para impedir reservas durante reparaciones u otras restricciones.

**Criterios de aceptación:**

- El bloqueo registra área, intervalo y motivo.
- No se aceptan reservas dentro del intervalo bloqueado.
- Los residentes con reservas afectadas reciben una notificación para reprogramar o cancelar.

---

# ÉPICA EGR — Egresos, proveedores y contratos

**Objetivo de la épica:** centralizar proveedores, documentos contractuales y gastos del condominio.

## EGR-01 — Administrar proveedores

**Historia:** Como administrador, quiero mantener un directorio de proveedores, para centralizar sus datos y servicios contratados.

**Criterios de aceptación:**

- El proveedor registra RUC, razón social, rubro y datos de contacto.
- No se permite duplicar un RUC dentro del mismo condominio.
- Se puede consultar el historial de contratos, egresos y tickets asociados.

## EGR-02 — Registrar contratos y documentos

**Historia:** Como administrador, quiero almacenar contratos y pólizas de proveedores, para evitar que los acuerdos permanezcan dispersos.

**Criterios de aceptación:**

- El contrato registra vigencia, monto, proveedor, contacto y archivo digital.
- Solo usuarios autorizados pueden reemplazar o agregar documentos.
- Los cambios conservan trazabilidad y fecha de registro.

## EGR-03 — Alertar vencimientos contractuales

**Historia:** Como miembro de la junta, quiero recibir alertas antes del vencimiento de contratos, para gestionar renovaciones o nuevas cotizaciones.

**Criterios de aceptación:**

- Se genera una alerta informativa a 60 días y una prioritaria a 30 días.
- Cada alerta se emite una sola vez por contrato y umbral.
- El aviso identifica proveedor, contrato y fecha de vencimiento.

## EGR-04 — Registrar y clasificar egresos

**Historia:** Como tesorero, quiero registrar cada egreso con su categoría y comprobante, para mantener un control presupuestal sustentado.

**Criterios de aceptación:**

- El egreso exige categoría, concepto, monto, fecha y documento de respaldo.
- El importe utiliza precisión decimal y debe ser mayor que cero.
- El movimiento queda vinculado con el proveedor cuando corresponda.

## EGR-05 — Aprobar y registrar pagos a proveedores

**Historia:** Como junta directiva, quiero revisar y aprobar pagos a proveedores, para controlar las salidas de dinero del condominio.

**Criterios de aceptación:**

- Los pagos que superen el límite configurado requieren aprobación autorizada.
- Un pago rechazado no afecta el flujo de caja.
- Un pago aprobado registra actor, sustento, saldo anterior y saldo posterior.

---

# ÉPICA TIC — Tickets e incidencias

**Objetivo de la épica:** registrar y seguir problemas de infraestructura hasta su solución y cierre.

## TIC-01 — Reportar una incidencia

**Historia:** Como residente, quiero reportar un desperfecto con evidencia, para que la administración pueda atenderlo.

**Criterios de aceptación:**

- El reporte contiene ubicación, categoría, descripción, urgencia y evidencia opcional.
- Un reporte válido crea un ticket REGISTRADO con identificador único.
- La administración recibe un aviso del nuevo ticket.

## TIC-02 — Clasificar y priorizar tickets

**Historia:** Como administrador, quiero validar y priorizar los tickets recibidos, para organizar la atención según impacto y urgencia.

**Criterios de aceptación:**

- El administrador puede confirmar o corregir categoría y prioridad.
- Un ticket inválido se rechaza indicando el motivo.
- Los tickets urgentes aparecen destacados en la bandeja administrativa.

## TIC-03 — Asignar un responsable

**Historia:** Como administrador, quiero asignar un ticket a mantenimiento o a un proveedor, para establecer quién debe resolverlo.

**Criterios de aceptación:**

- La asignación identifica responsable y plazo estimado.
- El ticket cambia de REGISTRADO a ASIGNADO.
- El responsable y el residente reciben la notificación correspondiente.

## TIC-04 — Registrar el progreso y la resolución

**Historia:** Como responsable de mantenimiento, quiero actualizar el diagnóstico, acciones y costos, para documentar la solución de la incidencia.

**Criterios de aceptación:**

- El ticket puede pasar de ASIGNADO a EN_PROCESO y luego a RESUELTO.
- Se conservan comentarios, evidencias, repuestos y costos registrados.
- Cada cambio de estado guarda fecha, actor y observación.

## TIC-05 — Confirmar o reabrir la incidencia

**Historia:** Como residente, quiero confirmar la solución o solicitar una revisión, para asegurar que el problema haya sido realmente resuelto.

**Criterios de aceptación:**

- El residente puede aceptar la solución y calificar la atención.
- Al aceptar, el ticket cambia a CERRADO.
- Si no está conforme, el ticket vuelve a EN_PROCESO con el motivo registrado.

---

# ÉPICA REP — Reportes, indicadores y balances

**Objetivo de la épica:** presentar información financiera confiable y generar rendiciones de cuentas periódicas.

## REP-01 — Consultar indicadores financieros

**Historia:** Como miembro de la junta, quiero consultar los principales KPIs, para evaluar la situación financiera del condominio.

**Criterios de aceptación:**

- El dashboard muestra morosidad, recaudación, flujo de caja y fondo de reserva.
- Los indicadores utilizan pagos conciliados y egresos registrados.
- Se muestra el periodo y la fecha de actualización de cada resultado.

## REP-02 — Consultar morosidad y cuentas por cobrar

**Historia:** Como tesorero, quiero consultar el detalle de deuda vencida, para priorizar las acciones de cobranza.

**Criterios de aceptación:**

- El reporte permite filtrar por periodo, edificio y estado financiero.
- Los totales coinciden con la suma de las obligaciones exigibles mostradas.
- Solo roles administrativos o de auditoría pueden consultar el detalle completo.

## REP-03 — Ejecutar el cierre mensual

**Historia:** Como tesorero, quiero consolidar y revisar el periodo antes de cerrarlo, para detectar diferencias antes de publicar el balance.

**Criterios de aceptación:**

- El cierre consolida ingresos conciliados, egresos, saldos y cuentas por cobrar.
- Si existen diferencias pendientes, el periodo queda EN_REVISION y no se publica.
- Un periodo cerrado genera un snapshot contable inmutable.

## REP-04 — Generar el balance mensual en PDF

**Historia:** Como junta directiva, quiero generar un balance mensual descargable, para rendir cuentas a los propietarios.

**Criterios de aceptación:**

- El PDF incluye resumen de ingresos, egresos, recaudación y cuentas por cobrar.
- El documento identifica el condominio, periodo y fecha de generación.
- El balance se genera a partir del snapshot del periodo cerrado.

## REP-05 — Publicar y descargar reportes autorizados

**Historia:** Como propietario o auditor, quiero acceder a los reportes permitidos por mi rol, para revisar la gestión del condominio.

**Criterios de aceptación:**

- El auditor puede acceder a balances y trazabilidad de todos los periodos autorizados.
- El propietario accede a balances públicos y a sus propios estados de cuenta.
- Cada descarga sensible valida rol y condominio.

---

# ÉPICA TRV — Auditoría, excepciones y resiliencia

**Objetivo de la épica:** asegurar trazabilidad, consistencia, recuperación de fallos y supervisión humana.

## TRV-01 — Registrar una auditoría inmutable

**Historia:** Como auditor, quiero que cada cambio financiero u operativo quede registrado, para reconstruir qué ocurrió y quién lo realizó.

**Criterios de aceptación:**

- Toda mutación relevante registra departamento, fecha, acción, motivo, resultado, estado anterior y estado posterior.
- También se registra el actor y el condominio de origen.
- Los registros de auditoría no pueden modificarse ni eliminarse mediante las operaciones normales.

## TRV-02 — Verificar la integridad de la auditoría

**Historia:** Como auditor, quiero comprobar la cadena de hashes de la bitácora, para detectar alteraciones no autorizadas.

**Criterios de aceptación:**

- Cada entrada contiene su hash y el hash de la entrada anterior.
- Una verificación válida confirma la continuidad completa de la cadena.
- Una inconsistencia genera una alerta crítica y no se oculta del historial.

## TRV-03 — Corregir operaciones mediante ajustes compensatorios

**Historia:** Como administrador autorizado, quiero corregir movimientos sin borrarlos, para conservar la integridad del historial contable.

**Criterios de aceptación:**

- No existe borrado físico de cuotas, pagos, moras o egresos confirmados.
- La corrección crea un movimiento inverso vinculado con el original.
- El ajuste exige motivo, autorización y registro de auditoría.

## TRV-04 — Gestionar una bandeja de excepciones

**Historia:** Como administrador, quiero consultar y resolver casos que no siguieron el flujo normal, para atender discrepancias y reclamos de manera controlada.

**Criterios de aceptación:**

- La bandeja muestra proceso de origen, causa, evidencia, prioridad y estado.
- El administrador puede aprobar, rechazar, corregir o solicitar información.
- La resolución registra decisión, motivo, actor y efecto producido.

## TRV-05 — Ejecutar tareas automáticas de forma idempotente

**Historia:** Como administrador, quiero que las tareas programadas puedan reintentarse sin duplicar resultados, para recuperar el sistema después de fallos.

**Criterios de aceptación:**

- Cada ejecución de emisión, mora o notificación utiliza una clave única de operación.
- Repetir una tarea completada no crea cargos, cuotas ni mensajes duplicados.
- Una ejecución interrumpida puede continuar o reintentarse dejando trazabilidad.

## TRV-06 — Monitorear servicios y fallos permanentes

**Historia:** Como administrador técnico, quiero conocer el estado de la API, base de datos, colas y almacenamiento, para reaccionar ante interrupciones del sistema.

**Criterios de aceptación:**

- Existe una comprobación de salud que informa si los servicios esenciales están operativos.
- Los fallos permanentes de procesos automáticos generan una alerta visible.
- La alerta contiene fecha, componente, operación afectada y referencia para diagnóstico.

---

# Recomendaciones para cargarlo en Jira

1. Crear primero las nueve épicas con las claves conceptuales `USR`, `CUE`, `PAG`, `NOT`, `RES`, `EGR`, `TIC`, `REP` y `TRV`.
2. Crear cada historia y asociarla con su épica correspondiente.
3. Usar los identificadores de este documento como prefijo del resumen, por ejemplo: `PAG-04 — Aprobar e imputar un pago`.
4. Añadir subtareas técnicas únicamente después de crear la historia: backend, frontend, base de datos, pruebas y documentación.
5. Priorizar primero las historias de la Entrega 1; las entregas 2 y 3 pueden permanecer en el backlog.
6. No marcar una historia como terminada hasta que cumpla todos sus criterios de aceptación y sus pruebas relacionadas.

