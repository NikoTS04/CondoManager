# Máquina de Estados: Comprobante de Pago y Conciliación

## Integración Sprint 2

EN_REVISION → OBSERVADO / RECHAZADO / APROBADO. OBSERVADO puede revisarse nuevamente;
observar o rechazar exige motivo y nunca aplica fondos. APROBADO y RECHAZADO son
terminales para el prototipo. La aprobación e imputación son una única transacción;
CONCILIADO es el alias de consulta de APROBADO, no otro estado SQL. El contrato
[CON-22/70/42](sprint-2-anderson.md) prevalece sobre el diagrama histórico inferior
para este alcance. Las anulaciones compensatorias no se implementan en estos tickets.

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
