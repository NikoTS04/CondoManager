# Estados de comprobantes — Base CON-72 del Sprint 2

Contrato objetivo: [pagos](../../05-api/sprint-2-contratos.md#5-pagos--anderson-y-brandon-persistencia-con-70). Estado público y persistido coinciden. La imputación es un efecto atómico de `APROBADO`, no un quinto estado `IMPUTADO`.

| Origen | Operación | Destino | Resultado y efectos |
|---|---|---|---|
| No existe | Reporte con archivo válido y hash nuevo | `EN_REVISION` | `202`, archivo y comprobante persistidos; `PagoReportadoEvent`. No cancela deuda. |
| `EN_REVISION` | Reintento propio equivalente | `EN_REVISION` | `200`, mismo UUID/hash, sin nueva carga ni evento. |
| `EN_REVISION` | Aprobar por administración autorizada | `APROBADO` | Imputación, resultado, auditoría y outbox en la misma transacción; `PagoConciliadoEvent`. |
| `EN_REVISION` | Observar con motivo | `OBSERVADO` | Sin imputación; `PagoRevisadoEvent` con motivo. |
| `EN_REVISION` | Rechazar con motivo | `RECHAZADO` | Sin imputación; `PagoRevisadoEvent` con motivo. |
| `OBSERVADO` | Nueva versión de archivo por la ruta de subsanación | `EN_REVISION` | `202`, mismo UUID/hash y metadatos; conserva archivo anterior y abre revisión nueva; otro `PagoReportadoEvent`. |
| Final de revisión vigente | Repetir exactamente esa decisión | Mismo estado | `200` con resultado original, sin otra imputación, auditoría de cambio ni evento. |
| Final de revisión vigente | Cambiar decisión sin revisión abierta | Sin transición | `409 ESTADO_COMPROBANTE_INVALIDO`. |
| `APROBADO` | Reportar de nuevo el mismo pago | Sin transición | `409 VOUCHER_YA_CONCILIADO`. |
| `OBSERVADO` / `RECHAZADO` | Repetir el reporte original | Sin transición | `409 VOUCHER_REQUIERE_SUBSANACION` / `409 VOUCHER_RECHAZADO`. |

La reutilización en otra unidad siempre produce conflicto sin divulgar el registro previo. La corrección observada y la revisión se serializan sobre el comprobante; una carrera no puede aprobar un archivo y sobrescribirlo simultáneamente.

La anulación de una aprobación mediante una nota de crédito queda fuera de los endpoints de este sprint. Requiere un contrato de compensación propio; no se publica `ANULADO` como estado permitido por el esquema actual ni se borran efectos financieros históricos.
