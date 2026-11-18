# Máquina de Estados: Comprobante de Pago y Conciliación

## Contrato vigente CON-72 y CON-25–28

EN_REVISION → OBSERVADO / RECHAZADO / APROBADO. Observar y rechazar requieren
motivo público y no acreditan el importe del comprobante; pueden regularizar mora
diaria provisionalmente pausada. OBSERVADO solo vuelve a EN_REVISION mediante
subsanación versionada. APROBADO y RECHAZADO son terminales en este alcance.
Repetir la revisión vigente con iguales decisión, motivo y notas normalizados
devuelve el recibo original; un cambio incompatible responde 409.

La aprobación e imputación son una sola transacción, con revisión, auditoría y
outbox. El estado público es APROBADO: no se publica CONCILIADO ni IMPUTADO.
Rigen [CON-72](../../05-api/sprint-2-contratos.md) y
[CON-25–28](../../05-api/pagos-sprint-3.md), sobre el antecedente Sprint 2.
Las anulaciones compensatorias no se implementan en estas historias.

```
   [ Residente envía voucher ]
                 │
                 ▼
          [ EN_REVISION ]
                 │
        ┌────────┴──────────────────────────┐
        ▼                                   ▼
    [ APROBADO ]                  [ OBSERVADO / RECHAZADO ]
    (ya imputado)                    (motivo obligatorio)

    [ OBSERVADO ] -- nueva evidencia --> [ EN_REVISION ]
```

## Tabla de Transiciones del Comprobante

| Estado Origen | Evento | Estado Destino | Guardas / Precondiciones | Acciones / Efectos |
| :--- | :--- | :--- | :--- | :--- |
| `[NULL]` | `SUBIR_COMPROBANTE` | `EN_REVISION` | Reporte válido y hash único; duplicados siguen contrato. | Guarda evidencia privada y evento; no acredita dinero. |
| `EN_REVISION` | `APROBAR_CONCILIACION` | `APROBADO` | Usuario es `ADMIN_JUNTA` o `SUPERADMIN`. | Ejecuta imputación atómica, reduce deudas, emite `PagoConciliadoEvent`. |
| `EN_REVISION` | `RECHAZAR_COMPROBANTE` | `RECHAZADO` | `motivo_rechazo != null` (texto explícito obligatorio). | Despacha notificación con motivo a Alejandro, reactiva evaluación de moras. |
| `EN_REVISION` | `OBSERVAR_COMPROBANTE` | `OBSERVADO` | Motivo público obligatorio. | Revisión auditada y evento; sin acreditar el comprobante. |
| `OBSERVADO` | `SUBSANAR_VOUCHER` | `EN_REVISION` | Evidencia nueva válida y actor autorizado. | Conserva historia, UUID, hash y datos bancarios. |
| Estado final | Repetir revisión idéntica | Mismo estado | Misma decisión, motivo y notas normalizados. | Devuelve recibo, sin repetir efectos. |
