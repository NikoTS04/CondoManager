# Avisos por correo del Sprint 4 — CON-47, CON-53 y CON-55

Contrato en el [catálogo de eventos](../03-contracts/events/domain-events-catalog.md).
Cada escenario indica si ya está cubierto (`Implementado`) o es el criterio que
debe cumplir el productor pendiente (`Contrato`).

## CON-47 — Reservas afectadas por un bloqueo (`NOTIF_RESERVA_AFECTADA_BLOQUEO`)

- **Un aviso por reserva** · Contrato. Dado un bloqueo confirmado que afecta tres
  reservas de tres titulares, cuando se guarda el bloqueo y las cancelaciones,
  entonces se encolan tres avisos EMAIL, uno por reserva, en la misma transacción.
  Cada uno indica área, fecha, horario y motivo, y enlaza a las reservas para
  elegir otro turno.
- **Sin aviso si se revierte** · Contrato. Dado un bloqueo cuya transacción falla,
  cuando se revierte, entonces no queda ningún aviso encolado.
- **Reintento sin duplicados** · Contrato. Dado un bloqueo ya confirmado, cuando
  se repite la confirmación, entonces no se crean avisos nuevos (clave
  `bloqueo_id` + `reserva_id` + titular).
- **Resumen** · Contrato. Dado un bloqueo con avisos en distintos estados, cuando
  Junta consulta el resumen, entonces ve cuántas reservas se cancelaron y cuántos
  avisos hay por estado, incluidas las reservas sin contacto utilizable.
- **Titular sin contacto** · Contrato. Dada una reserva cuyo titular no existe o no
  tiene correo, cuando se confirma el bloqueo, entonces la reserva se cancela, no
  se crea aviso y el resumen la informa como `CONTACTO_FALTANTE`.
- **Datos incompletos** · Contrato. Dada una reserva sin dato obligatorio de la
  plantilla, cuando se intenta encolar, entonces no se crea el aviso, se registra
  la incidencia `DATOS_PLANTILLA_INCOMPLETOS` y ningún valor aparece en el error.
- **Aislamiento** · Contrato. Dado un bloqueo de un condominio, cuando se
  calculan los avisos, entonces solo se consideran titulares de ese condominio.

## CON-53 — Aviso a administración (`NOTIF_INCIDENCIA_REGISTRADA`)

- **Aviso por integrante de Junta** · Implementado. Dado un reporte válido,
  cuando se registra, entonces se encola un aviso por integrante activo de Junta
  del condominio con el ID y un enlace privado al reporte.
- **Reintento sin duplicados** · Implementado. Dado un reporte ya registrado,
  cuando se reenvía con la misma clave y datos, entonces se conserva un aviso por
  destinatario (`evento_id` = `operacion_id` = ID de la incidencia).
- **Sin Junta activa** · Contrato. Dado un condominio sin integrantes activos de
  Junta, cuando un residente reporta, entonces el ticket se registra y la
  auditoría informa `avisos_encolados: 0`.
- **Solo la propia Junta** · Contrato. Dado un reporte, cuando se encolan avisos,
  entonces ningún destinatario pertenece a otro condominio.

## CON-55 — Confirmación de la asignación

- **Aviso al residente** · Contrato (`NOTIF_INCIDENCIA_ASIGNADA_RESIDENTE`). Dada
  una asignación confirmada, cuando se guarda, entonces se encola un aviso al
  reportante con el código del ticket, el estado `ASIGNADO` y el enlace de
  seguimiento.
- **Aviso al proveedor** · Contrato (`NOTIF_INCIDENCIA_ASIGNADA_PROVEEDOR`).
  Dada una asignación a un proveedor externo con correo registrado, cuando se
  confirma, entonces se encola un aviso a ese contacto con el código del ticket,
  ubicación, categoría, prioridad, descripción y plazo, sin datos personales del
  residente.
- **Referencia a la asignación** · Contrato. Dada una asignación confirmada,
  cuando se repite la confirmación, entonces no se crean avisos nuevos: ambos
  llevan el ID de la asignación como `evento_id`.
- **Reasignación** · Contrato. Dado un ticket ya asignado, cuando Junta confirma
  otra asignación, entonces se encolan avisos nuevos asociados a la nueva
  asignación y los anteriores se conservan.
- **Contacto faltante** · Contrato. Dado un proveedor sin correo, cuando se
  confirma la asignación, entonces el aviso al residente se encola, el del
  proveedor no se crea y Junta ve `CONTACTO_FALTANTE` para ese destinatario.
- **Fallo de entrega** · Contrato. Dado un aviso al proveedor que rebota (550),
  cuando se agotan o descartan los reintentos, entonces queda `FALLIDO_PERMANENTE`,
  se crea la alerta `ERROR_DEFINITIVO` y Junta lo ve junto a la asignación.
- **Visibilidad del resultado** · Contrato. Dada una asignación con avisos,
  cuando Junta consulta el ticket, entonces ve por destinatario el estado del
  aviso, sin tratar `ENVIADO` como entregado. Un Residente no consulta los avisos
  del proveedor.
- **Permisos y aislamiento** · Contrato. Dado un ticket de otro condominio, cuando
  Junta consulta sus avisos, entonces recibe 404.
