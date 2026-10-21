# Catálogo de Eventos Asíncronos de Dominio (Domain Events Catalog)

En CondoManager, los dominios se comunican de forma desacoplada y reactiva mediante eventos de dominio publicados en Redis Streams (`condomanager:domain-events`) después del commit transaccional y procesados por workers asíncronos con garantías de idempotencia.

---

## 1. Matriz de Publicadores y Suscriptores

| Evento de Dominio | Dominio Publicador | Dominios Suscriptores | Esquema JSON | Propósito |
| :--- | :--- | :--- | :--- | :--- |
| `CuotasEmitidasEvent` | `01-cuotas` (CON-11) | `03-notificaciones` (CON-32) | `schemas/cuotas-emitidas.schema.json` | Lote mensual confirmado; genera avisos individuales `NOTIF_EMISION_CUOTA` leyendo las cuotas persistidas del lote. |
| `CuotaEmitidaEvent` | `01-cuotas` (legado) | `03-notificaciones` | `schemas/cuota-emitida.schema.json` | Compatibilidad de emisión por lote/periodo. |
| `PagoReportadoEvent` | `02-pagos` (CON-22 / CON-70) | `03-notificaciones` (CON-34) | `schemas/pago-reportado.schema.json` | Confirmar recepción de comprobante en `EN_REVISION` (`NOTIF_PAGO_RECIBIDO`). |
| `PagoRevisadoEvent` | `02-pagos` (CON-70) | `03-notificaciones` (CON-34) | `schemas/pago-revisado.schema.json` | Comunicar resultado persistido de revisión: `APROBADO` (`NOTIF_PAGO_CONCILIADO`), `OBSERVADO` (`NOTIF_PAGO_OBSERVADO`) o `RECHAZADO` (`NOTIF_PAGO_RECHAZADO`). |
| `PagoConciliadoEvent` | `02-pagos` | `01-cuotas`, `03-notificaciones`, `04-reservas` | `schemas/pago-conciliado.schema.json` | Alias compatible de aprobación de pago con monto aplicado y saldo resultante. |
| `MoraAplicadaEvent` | `02-pagos` | `03-notificaciones`, `04-reservas` | `schemas/mora-aplicada.schema.json` | Enviar liquidación con recargo y avisar bloqueo de reservas de áreas comunes. |
| `ReservaConfirmadaEvent` | `04-reservas` (CON-41) | `03-notificaciones` (CON-36) | `schemas/reserva-confirmada.schema.json` | Confirmar reserva (`NOTIF_RESERVA_CONFIRMADA`) con área, fecha, horario, costo y normas de uso. |
| `ReservaCanceladaEvent` | `04-reservas` (CON-46) | `03-notificaciones` (CON-36) | `schemas/reserva-cancelada.schema.json` | Comunicar cancelación (`NOTIF_RESERVA_CANCELADA`), liberación del horario y ajuste económico aplicable. |

> **Nota sobre CON-04 (Invitaciones de usuario):** La invitación y verificación por correo electrónico quedan diferidas para una evolución posterior al Sprint 2; el alta utiliza habilitación administrativa directa por `SUPERADMIN`.

---

## 2. Convención de Envelope de Eventos

Todo mensaje publicado en el stream `condomanager:domain-events` se serializa como JSON en el campo `event` con el siguiente envelope estándar:

```json
{
  "event_id": "uuid",
  "event_type": "PagoRevisadoEvent",
  "producer": "service.pagos",
  "occurred_at": "2026-10-20T20:30:00Z",
  "data": {}
}
```

### Reglas de Publicación y Consumo Idempotente
1. **Publicación posterior al commit:** ningún productor publica un evento antes de confirmar su transacción en PostgreSQL. En `01-cuotas`, `eventos_lote_outbox` se persiste en la misma transacción de emisión y el relay marca `publicado_en` únicamente tras `XADD` exitoso.
2. **Deduplicación de consumo:** el consumidor de notificaciones registra `(consumidor, event_id)` en `eventos_consumidos` (`pk_eventos_consumidos`) y cada entrega lógica en `notificaciones` con `clave_deduplicacion` única (`uq_notificacion_entrega_logica`):
   - Cuotas (CON-32): `CUOTA:{cuota_id}:NOTIF_EMISION_CUOTA:{canal}:{usuario_id}`
   - Pagos (CON-34): `COMPROBANTE:{comprobante_id}:{plantilla}:{canal}:{usuario_id}`
   - Reservas (CON-36): `RESERVA:{reserva_id}:{plantilla}:{canal}:{usuario_id}`
   - Comunicados: `COMUNICADO:{comunicado_id}:{canal}:{usuario_id}`
3. **Atomicidad y confirmación:** la marca del evento consumido, la resolución de destinatarios activos y la inserción de notificaciones en `EN_COLA` ocurren en una sola transacción; cualquier error la revierte sin registros parciales. El worker de notificaciones (grupo `notificaciones-workers`) confirma con `XACK` solo después del commit:
   - Evento de un tipo sin consumidor de notificaciones: `XACK` sin efectos.
   - Error de contrato (envelope o `data` inválidos, variables de plantilla ausentes): reintentar no lo corrige; se copia a `condomanager:domain-events:dlq` con el error y se confirma.
   - Error transitorio (base de datos, red): sin `XACK`; el mensaje queda pendiente y se recupera con `XAUTOCLAIM` tras el reinicio o la caída del worker.
4. **Integridad financiera (Zero-Float):** los importes en `data` se transmiten como cadenas decimales con dos posiciones (`"150.00"`) o `Decimal`, nunca `float`. Las plantillas nunca inventan saldos ni montos por defecto (`0.00`); si falta un dato requerido por el contrato (p. ej. `saldo_resultante` en un pago `APROBADO`), el consumidor rechaza el evento con error de contrato.
