# Máquina de Estados: Cuota de Mantenimiento

```
                    [ DISPARADOR: Cron 00:00 Día 1 ]
                                   │
                                   ▼
                             [ EMITIDA ]
                                   │
                   ┌───────────────┴───────────────┐
       (saldo_a_favor >= cuota)         (saldo_a_favor < cuota)
                   ▼                               ▼
              [ PAGADA ]                     [ PENDIENTE ]
                   ▲                               │
                   │                               ▼ (Llega fecha_vencimiento)
                   │                          [ VENCIDA ]
                   │                               │
                   │ (Pago aprobado)               ▼ (Expiran dias_gracia)
                   ├───────────────────────── [ EN_MORA ]
                   │                               │
                   │ (Abono parcial aprobado)      ▼
                   └─────────────────────── [ PAGO_PARCIAL ]
```

## Tabla Exhaustiva de Transiciones y Guardas

| Estado Origen | Evento | Estado Destino | Guardas / Precondiciones | Acciones / Efectos Secundarios |
| :--- | :--- | :--- | :--- | :--- |
| `[NULL]` | `EMITIR_LOTE` | `EMITIDA` | Presupuesto > 0, Lote no emitido previamente en el periodo. | Genera registros en `cuotas_mantenimiento` con hash de idempotencia. |
| `EMITIDA` | `AMORTIZAR_TOTAL` | `PAGADA` | `departamento.saldo_a_favor >= cuota.monto` | Descuenta saldo a favor, marca `monto_pagado = monto_total`, emite log auditoría. |
| `EMITIDA` | `PUBLICAR_CUOTA` | `PENDIENTE` | `monto_exigible > 0.00` | Despacha evento `CuotaEmitidaEvent` a la cola de notificaciones. |
| `PENDIENTE` | `EXPIRAR_FECHA` | `VENCIDA` | `fecha_actual > fecha_vencimiento` | Marca cuota como vencida. Habilita cuenta regresiva de periodo de gracia. |
| `VENCIDA` | `APLICAR_MORA` | `EN_MORA` | `dias_transcurridos > dias_gracia` Y `sin_pago_en_revision` | Genera recargo de mora, bloquea reservas de áreas comunes (PROC-04), emite log. |
| `PENDIENTE` / `VENCIDA` / `EN_MORA` | `CONCILIAR_TOTAL` | `PAGADA` | `monto_imputado == monto_total_exigible` | Desbloquea reservas si no adeuda otras cuotas, emite `PagoConciliadoEvent`. |
| `PENDIENTE` / `VENCIDA` / `EN_MORA` | `CONCILIAR_PARCIAL`| `PAGO_PARCIAL` | `0.00 < monto_imputado < monto_total_exigible`| Actualiza `monto_pagado`, recalcula `monto_total_exigible`. Mantiene restricción de mora. |
