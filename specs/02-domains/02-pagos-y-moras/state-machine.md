# Máquina de Estados: Comprobante de Pago y Conciliación

```
   [ Residente envía voucher ]
                 │
                 ▼
          [ EN_REVISION ]
                 │
        ┌────────┴──────────────────────────┐
        ▼                                   ▼
   [ APROBADO ]                        [ RECHAZADO ]
        │                       (Requiere motivo de rechazo)
        ▼
   [ IMPUTADO ]
(Distribuido a deudas)
```

## Tabla de Transiciones del Comprobante

| Estado Origen | Evento | Estado Destino | Guardas / Precondiciones | Acciones / Efectos |
| :--- | :--- | :--- | :--- | :--- |
| `[NULL]` | `SUBIR_COMPROBANTE` | `EN_REVISION` | `idempotency_hash` no existe en estado `APROBADO`. | Almacena imagen en S3, calcula hash, pospone corte de mora 24h. |
| `EN_REVISION` | `APROBAR_CONCILIACION` | `APROBADO` | Usuario es `ADMIN_JUNTA` o `SUPERADMIN`. | Ejecuta imputación atómica, reduce deudas, emite `PagoConciliadoEvent`. |
| `EN_REVISION` | `RECHAZAR_COMPROBANTE` | `RECHAZADO` | `motivo_rechazo != null` (texto explícito obligatorio). | Despacha notificación con motivo a Alejandro, reactiva evaluación de moras. |
| `APROBADO` | `ANULAR_CONCILIACION` | `ANULADO` | Solo permitido mediante Nota de Crédito / Asiento Compensatorio. | Reversa saldos imputados, restaura estado previo de cuotas, registra auditoría obligatoria. |
