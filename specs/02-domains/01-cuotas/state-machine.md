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
| `EMITIDA` | `AMORTIZAR_TOTAL` | `PAGADA` | `saldo_a_favor >= monto_total_exigible` y bruto definitivo | Consume crédito, marca `monto_pagado = monto_total_exigible`, conserva bruto y descuento cero; registra aplicación única y auditoría. |
| `EMITIDA` | `AMORTIZAR_PARCIAL` | `PENDIENTE` | `0.00 < saldo_a_favor < monto_total_exigible` y bruto definitivo | Marca `monto_pagado = saldo_a_favor`, consume todo el crédito; pendiente = exigible - pagado; conserva bruto y descuento cero; registra aplicación y auditoría. |
| `EMITIDA` | `PUBLICAR_CUOTA` | `PENDIENTE` | `saldo_a_favor = 0.00` y `monto_total_exigible > 0.00` | Registra aplicación cero y auditoría; publica la cuota sin alterar el bruto. |
| `PENDIENTE` | `EXPIRAR_FECHA` | `VENCIDA` | `fecha_actual > fecha_vencimiento` | Marca cuota como vencida. Habilita cuenta regresiva de periodo de gracia. |
| `VENCIDA` | `APLICAR_MORA` | `EN_MORA` | Fecha local posterior a vencimiento + gracia histórica y principal impago | Devengo diario por cuota/fecha; default 1.00 PEN editable. Pausa de revisión no condona ni habilita reservas. |
| `EN_MORA` / `PAGO_PARCIAL` | `DEVENGAR_DIA_MORA` | `EN_MORA` | Principal impago, fecha exigible no procesada, política histórica | Incrementa mora sin capitalización; reintentos no duplican; ajustes bancarios son compensatorios. |
| `PENDIENTE` / `VENCIDA` / `EN_MORA` | `CONCILIAR_TOTAL` | `PAGADA` | `monto_imputado == monto_total_exigible` | Desbloquea reservas si no adeuda otras cuotas, emite `PagoConciliadoEvent`. |
| `PENDIENTE` / `VENCIDA` / `EN_MORA` | `CONCILIAR_PARCIAL`| `PAGO_PARCIAL` | `0.00 < monto_imputado < monto_total_exigible`| Actualiza `monto_pagado`, recalcula `monto_total_exigible`. Mantiene restricción de mora. |

CON-13: las tres transiciones de emisión son atómicas bajo bloqueo condominio
→ departamento → cuota; el primero serializa la cadena de auditoría.
Si ya existe `aplicaciones_saldo_favor.cuota_id`, el reintento no ejecuta
otra transición ni modifica el saldo; devuelve el resultado original.
