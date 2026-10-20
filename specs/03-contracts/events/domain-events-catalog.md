# Catálogo de Eventos Asíncronos de Dominio (Domain Events Catalog)

En CondoManager, los dominios se comunican de forma desacoplada y reactiva mediante eventos de dominio publicados en Redis y procesados por workers asíncronos.

---

## 1. Matriz de Publicadores y Suscriptores

| Evento de Dominio | Dominio Publicador | Dominios Suscriptores | Propósito |
| :--- | :--- | :--- | :--- |
| `CuotaEmitidaEvent` | `01-cuotas` (Anderson) | `03-notificaciones` (Alejandro) | Despachar aviso mensual con monto y fecha límite a residentes. |
| `CuotasEmitidasEvent` | `01-cuotas` (CON-11, Nicolás) | `03-notificaciones` | Lote mensual confirmado; outbox transaccional y Redis Stream `condomanager:domain-events`. |
| `PagoReportadoEvent` | `02-pagos` (Tarqui) | `03-notificaciones`, Dashboard Junta | Avisar al residente de recepción y notificar a directivos de pago pendiente. |
| `PagoConciliadoEvent`| `02-pagos` (Tarqui) | `01-cuotas`, `03-notif`, `04-reservas` | Imputar saldos, enviar recibo y **desbloquear permisos de reserva** si quedó al día. |
| `MoraAplicadaEvent` | `02-pagos` (Tarqui) | `03-notificaciones`, `04-reservas` | Enviar liquidación con recargo y **bloquear reservas de áreas comunes**. |
| `ReservaConfirmadaEvent`| `04-reservas` (Brandon) | `03-notificaciones` | Enviar confirmación con reglas del espacio al residente. |
| `ReservaCanceladaEvent` | `04-reservas` (Brandon) | `03-notif`, Calendario General | Notificar liberación de franja horaria a la comunidad. |

---

## 2. Convención de Envelope de Eventos
Todo mensaje publicado sigue el envelope estándar CloudEvents:
```json
{
  "event_id": "uuid",
  "event_type": "condomanager.pagos.pago_conciliado",
  "producer": "service.pagos",
  "occurred_at": "2026-09-22T20:30:00Z",
  "data": { ... }
}
```

CON-11 guarda `eventos_lote_outbox` en la transacción de emisión. El relay del
worker publica un campo `event` con el envelope JSON. `event_type` es
`CuotasEmitidasEvent`; `data` contiene `condominio_id`, `presupuesto_id`, `metodo`
y el resumen HTTP del lote. Entrega al menos una vez: el consumidor debe deduplicar
por `event_id` estable. `publicado_en` solo se confirma tras el XADD exitoso.
El consumidor de avisos individuales queda en el dominio de notificaciones.
