# CON-53 — Reportar una incidencia

- **Reporte válido.** Dado un residente con vínculo activo, cuando envía un
  reporte completo sin foto, entonces el sistema devuelve el ID, persiste el
  estado `REGISTRADO` y encola un aviso por integrante activo de Junta del
  condominio.
- **Campos obligatorios.** Dado un formulario sin ubicación, cuando el residente
  intenta enviarlo, entonces ve el campo pendiente y conserva lo ingresado. La
  API rechaza la solicitud sin crear el ticket ni encolar el aviso.
- **Reintento.** Dado un reporte registrado, cuando se reenvía con la misma clave
  y datos, entonces recibe el mismo ID y se conservan un ticket y un aviso por
  destinatario.
- **Aislamiento.** Dado un reporte con foto, cuando un residente de otro
  condominio intenta consultar el ticket o la foto, entonces recibe 404.
- **Evidencia inválida.** Dado un reporte completo con una foto inválida,
  cuando se envía, entonces el archivo se rechaza, el reporte se conserva
  sin foto y se muestra el motivo en la confirmación.
- **Mis reportes.** Dado un residente con reportes propios, cuando vuelve al
  portal, entonces encuentra sus incidencias de la más reciente a la más
  antigua y puede abrir cada detalle. Si Junta rechazó una, ve el motivo.
  No aparecen reportes de otros residentes, aunque compartan unidad.

## CON-54 — Clasificar y priorizar tickets

- **Prioridad efectiva.** Dado un reporte urgente pendiente, cuando Junta le
  confirma otra prioridad o eleva otro reporte a urgente, entonces la bandeja
  refleja la prioridad vigente y coloca los urgentes pendientes primero.
- **Trazabilidad.** Dado un reporte registrado, cuando Junta corrige su
  categoría y prioridad, entonces se conserva el reporte original y queda
  registrada la decisión con actor, fecha y valores previos y posteriores.
- **Rechazo.** Dado un reporte registrado, cuando Junta lo rechaza con motivo,
  entonces queda `RECHAZADO`, el reportante puede leer el motivo y una
  revisión posterior se rechaza. Una solicitud sin motivo se rechaza sin
  modificar el reporte.
- **Permisos y concurrencia.** Dado un reporte registrado, cuando lo revisa un
  residente, una Junta ajena o una Junta con una versión desactualizada, la
  decisión se rechaza y se conserva la última versión válida.

## CON-55 — Asignar responsable y plazo

- **Asignación válida.** Dado un ticket registrado o asignado, cuando Junta
  confirma un responsable vigente del condominio y un plazo futuro, entonces el
  ticket pasa a `ASIGNADO`, se guarda la asignación con actor y fecha y se
  registran los siete campos de auditoría.
- **Responsable incompatible.** Dado un usuario inactivo o ajeno al condominio,
  cuando Junta intenta asignarlo, entonces la solicitud se rechaza sin crear la
  asignación ni cambiar el estado del ticket.
- **Reintento y reasignación.** Dada una asignación confirmada, cuando se repite
  la misma clave y datos, entonces se devuelve la asignación original sin avisos
  nuevos; cuando se usa otra clave, entonces se crea otra asignación y se
  conservan los avisos anteriores. Una clave distinta con los mismos datos se
  rechaza con 409.
- **Avisos.** Dada una asignación confirmada, cuando se guarda, entonces se
  encola un aviso al residente con código, estado `ASIGNADO` y enlace; si el
  responsable es un proveedor externo con correo, se encola otro aviso con
  código, ubicación, categoría, prioridad, descripción y plazo, sin datos
  personales del residente. Ambos usan el ID de la asignación como evento.
- **Contacto faltante.** Dado un proveedor sin correo, cuando se confirma la
  asignación, entonces solo se encola el aviso al residente y Junta ve
  `CONTACTO_FALTANTE` para el proveedor.
- **Consulta de avisos.** Dada una asignación con avisos, cuando Junta o Auditor
  del condominio consulta `/avisos`, entonces ve por destinatario el estado, los
  intentos y si hay alerta abierta, sin correos ni contenido. Un residente
  recibe 403 y un perfil de otro condominio recibe 404.

## CON-56 — Seguimiento, evidencias, costos y resolución

- **Avance.** Dado un ticket `ASIGNADO`, cuando Junta registra un diagnóstico o
  avance con versión vigente, entonces pasa a `EN_PROCESO` y el historial guarda
  fecha, actor, observación y estado anterior y posterior.
- **Evidencia y costos.** Dado un ticket `EN_PROCESO`, cuando Junta adjunta una
  foto válida y registra repuestos con monto decimal, entonces ambos quedan
  asociados al avance, con importe `NUMERIC(12,2)` y sin usar `float`. Un archivo
  inválido se rechaza sin borrar el avance.
- **Resolución.** Dado un ticket `EN_PROCESO`, cuando Junta registra la
  resolución, entonces pasa a `RESUELTO`; una resolución desde otro estado se
  rechaza con 409 y una versión desactualizada también.
- **Visibilidad.** Dado un avance con sustento interno, cuando el residente
  consulta el historial, entonces ve solo las actualizaciones publicadas y el
  estado vigente; Junta y Auditor del condominio ven también costos y evidencias.
  Otro condominio recibe 404.
- **Auditoría.** Dado cualquier cambio de estado, cuando se guarda, entonces se
  registra con los siete campos obligatorios, actor y contexto, en la misma
  transacción que el avance.

## CON-57 — Confirmar, calificar, cerrar o reabrir

- **Cierre conforme.** Dado un ticket `RESUELTO`, cuando el residente confirma con
  calificación de 1 a 5, entonces pasa a `CERRADO`, queda fecha y actor de cierre
  y se registra `CIERRE_CONFORME_TICKET` con los siete campos de auditoría.
- **Reapertura.** Dado un ticket `RESUELTO`, cuando el residente indica que no
  está conforme con motivo, entonces vuelve a `EN_PROCESO`, el motivo queda
  visible para Junta y el reportante, y se registra la decisión con actor y fecha.
- **Cierre administrativo.** Dado un ticket `RESUELTO` sin confirmación del
  residente, cuando Junta cierra con una decisión autorizada y motivo, entonces
  pasa a `CERRADO` y queda trazable el actor y el motivo. El proveedor nunca cierra.
- **Calificación inválida.** Dado un residente que envía una calificación fuera
  de 1 a 5 o un motivo vacío, cuando intenta cerrar o reabrir, entonces la API
  rechaza la solicitud sin modificar el ticket.
- **Permisos y versión.** Dado un ticket de otro condominio o de otro residente,
  cuando se intenta confirmar o reabrir, entonces se recibe 404; una versión
  desactualizada o un estado distinto de `RESUELTO` se rechaza con 409. Un ticket
  `CERRADO` es terminal.
# Reparto independiente de costos y pago dirigido

```gherkin
Scenario Outline: Reparto por monto con alcance y método elegidos
  Given un costo positivo y departamentos activos del mismo condominio
  When Junta previsualiza y publica con alcance <alcance> y método <metodo>
  Then se conserva la instantánea y la suma de cargos coincide exactamente con el costo
  And repetir la confirmación devuelve el mismo reparto
  Examples:
    | alcance       | metodo       |
    | TODOS         | EQUITATIVA   |
    | TODOS         | POR_ALICUOTA |
    | SELECCIONADOS | EQUITATIVA   |
    | SELECCIONADOS | POR_ALICUOTA |

Scenario: Cambio entre previsualización y publicación
  Given una previsualización de un reparto
  When cambian participantes o coeficientes antes de confirmar
  Then se rechaza la publicación sin crear cargos

Scenario: Pago individual o conjunto
  Given varios cargos de incidencias pendientes de mi departamento
  When reporto un comprobante por la suma de los cargos seleccionados
  Then se conserva la selección y los cargos siguen pendientes
  When Junta aprueba el comprobante
  Then solo los cargos seleccionados quedan pagados
  And repetir la aprobación no duplica efectos
  And reconstruir moras de cuotas no redistribuye ese pago

Scenario: Privacidad del cargo
  Given un cargo derivado de un costo interno de una incidencia ajena
  When el residente consulta sus cargos
  Then ve su concepto público e importe sin comentarios ni evidencias internos
  And no puede seleccionar cargos de otro departamento

Scenario: Proveedor real del directorio
  Given un proveedor activo del condominio
  When Junta lo selecciona como responsable
  Then se toma nombre y contacto del directorio
  And se rechazan proveedores inexistentes, inactivos o de otro condominio
```
