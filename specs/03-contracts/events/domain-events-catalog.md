# Catálogo de eventos — Contrato del Sprint 2 / CON-72

Base acordada el 20/10/2026. Los contratos HTTP y las reglas asociadas están en [sprint-2-contratos.md](../../05-api/sprint-2-contratos.md). Este catálogo define mensajes para implementar en las historias de origen; no acredita que todos sus productores y consumidores ya estén integrados.

## Productores, consumidores y esquemas

| Evento | Productor | Consumidor y efecto | Esquema canónico | Estado del productor |
|---|---|---|---|---|
| `CuotasEmitidasEvent` | CON-11, cuotas | CON-32 genera avisos por cuota y destinatario desde el lote persistido. | [cuotas-emitidas.schema.json](schemas/cuotas-emitidas.schema.json) | Existente con outbox; conservar compatibilidad. |
| `PagoReportadoEvent` | Anderson, CON-22/70; Brandon integra CON-23 | CON-34 confirma recepción sin aplicar saldos; también por subsanación real de un observado. | [pago-reportado.v1.schema.json](schemas/pago-reportado.v1.schema.json) | Integración pendiente. |
| `PagoConciliadoEvent` | Anderson, resultado aprobado de CON-70 | CON-34 comunica el resultado; los demás consumidores refrescan vistas sin aplicar otra vez el pago. | [pago-conciliado.v1.schema.json](schemas/pago-conciliado.v1.schema.json) | Integración pendiente. |
| `PagoRevisadoEvent` | Anderson, revisión observada/rechazada de CON-70 | CON-34 comunica motivo e instrucciones. No modifica saldos. | [pago-revisado.v1.schema.json](schemas/pago-revisado.v1.schema.json) | Integración pendiente. |
| `ReservaConfirmadaEvent` | Brandon, CON-41 | CON-36 comunica área, fecha, horario, costo y normas. | [reserva-confirmada.v1.schema.json](schemas/reserva-confirmada.v1.schema.json) | Integración persistente pendiente. |
| `ReservaCanceladaEvent` | Gerardo, CON-46 | CON-36 comunica cancelación y estado real del ajuste económico. | [reserva-cancelada.v1.schema.json](schemas/reserva-cancelada.v1.schema.json) | Integración persistente pendiente. |

Alejandro implementa consumo, plantillas y reintentos. Nicolás implementa persistencia de notificaciones y eventos pendientes en CON-73 y coordina la integración. No hay evento de invitación requerido para cerrar CON-04: la habilitación es administrativa y manual.

## Envelope propio, versión 1

Los mensajes nuevos utilizan [event-envelope.v1.schema.json](schemas/event-envelope.v1.schema.json). Es un formato propio de CondoManager; no se declara conformidad con CloudEvents.

```json
{
  "event_id": "04452ad0-e363-4a77-b55f-b336e50d5e9a",
  "event_type": "PagoReportadoEvent",
  "schema_version": 1,
  "producer": "service.pagos",
  "occurred_at": "2026-10-20T18:00:00Z",
  "correlation_id": "6ef0c55d-bf52-48ea-aa7c-2519587d8628",
  "causation_id": null,
  "data": {
    "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "departamento_id": "6c78c3b5-1efb-4d0b-a5f8-78fc17364083",
    "comprobante_id": "75e9efb4-b726-4bc0-a8d6-170fbbbcf614",
    "estado": "EN_REVISION",
    "monto": "150.00",
    "fecha_operacion": "2026-10-20"
  }
}
```

- `event_id` identifica una operación confirmada y se conserva al republicar. Otra operación sobre el mismo recurso tiene otro identificador.
- `schema_version` versiona el payload, independientemente de OpenAPI y de la Release.
- `occurred_at` representa el hecho confirmado en UTC, no la hora del último reintento. El evento no cambia al retransmitirse.
- `correlation_id` enlaza el recorrido; el productor lo genera si el origen no aporta uno válido. `causation_id` referencia otro evento cuando lo hay, o es nulo.
- `data.condominio_id` y los UUID de la operación delimitan el contexto. Destinatarios se resuelven desde registros autorizados; no incluir contraseñas, tokens, documento de identidad ni contenido del voucher.
- Importes como cadenas de dos decimales. Horas de reservas en `America/Lima`; instantes de auditoría/eventos en UTC.

## Publicación y consumo

1. Guardar operación, auditoría y evento pendiente en una transacción. Una reversión no deja eventos de éxito publicables. Nunca notificar antes del commit.
2. El relay publica el campo `event` con el JSON en Redis Stream `condomanager:domain-events`; marca publicado tras `XADD` exitoso. La entrega es al menos una vez.
3. Registrar procesamiento con unicidad `(consumidor, event_id)`. Los avisos usan además unicidad lógica `(evento_id, operacion_id, destinatario_id, canal)`: `operacion_id` es la cuota de un lote, el comprobante o la reserva.
4. Insertar avisos y registrar procesamiento conjuntamente. Reentregar un lote permite completar lo que falte sin duplicar avisos existentes.
5. Los reintentos de transporte actualizan el mismo aviso; no reaplican pagos ni ajustes. Consultar solvencia desde deuda persistida, sin activar un permiso global por un evento atrasado.
6. Conservar versiones desconocidas o payloads inválidos como incidencias identificables, sin tratarlos como éxito ni reintentarlos indefinidamente sin registro.

## Compatibilidad y esquemas históricos

`CuotasEmitidasEvent` ya está implementado. Su esquema acepta opcionalmente `schema_version=1`, correlación y causación; esos campos no son obligatorios para leer eventos previos. El consumidor trata la versión ausente como 1 únicamente para este evento. CON-72 no modifica su relay.

Los archivos sin sufijo `.v1` de [pago conciliado](schemas/pago-conciliado.schema.json), [reserva confirmada](schemas/reserva-confirmada.schema.json), [mora aplicada](schemas/mora-aplicada.schema.json) y [cuota emitida](schemas/cuota-emitida.schema.json) se conservan como contratos históricos. Los nuevos productores de pagos y reservas usan los esquemas `.v1` de la tabla.

Si hay un consumidor de mensajes planos, su adaptación se entrega junto con el productor: preservar `event_id`, resolver contexto desde registros autorizados y transformar campos explícitamente. `monto_conciliado` y `saldo_restante_departamento` históricos requieren comprobar su significado frente al resultado financiero real. No inventar UUID o importes ausentes.

`CuotaEmitidaEvent` histórico describe un agregado y no se usa para volver a notificar un lote de `CuotasEmitidasEvent`. `MoraAplicadaEvent` queda fuera de los nuevos productores de este sprint; conserva su versión histórica hasta una evolución explícita.
