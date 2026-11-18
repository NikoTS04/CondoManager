# CON-25–28 — Revisión, abonos y crédito compatibles

Incremento sobre OpenAPI 2.5.0 y las migraciones 0019/0020. Reutiliza
`PagosPersistentesService`, el plan contable, la reconstrucción diaria y CON-13.
No agrega otro motor, endpoints financieros, tablas ni migraciones.

## Contrato y conservación

- `POST /pagos/{comprobante_id}/conciliar` y `GET /pagos/{comprobante_id}/resultado`
  conservan `ConciliarPago` y `ResultadoRevision` publicados en CON-72.
- Solo Junta del contexto y SuperAdmin deciden. Auditor consulta; residente solo
  consulta sus unidades autorizadas. Notas internas nunca son motivo público.
- Una revisión nueva exige EN_REVISION. Repetir decisión, motivo y notas
  normalizados devuelve el recibo original; un cambio incompatible responde 409.
  El recibo se selecciona por decisión y evidencia vigentes, incluso cuando dos
  revisiones comparten timestamp; una revisión legacy sin referencia es fallback.
- Por comprobante aprobado: aplicaciones efectivas + crédito atribuible = importe
  bancario. Ninguna parte es negativa. Los errores revierten toda la transacción.
  Un plan inconsistente responde 409 `IMPUTACION_PAGO_INCONSISTENTE`.
- Prelación: mora, extraordinaria vencida, ordinaria vencida, ordinaria vigente;
  desempate por vencimiento y UUID. No se anticipan ordinarias futuras.
- Nuevas aprobaciones, tanto legacy como diarias, no imputan a una cuota cuya
  fecha de emisión sea posterior a la fecha bancaria. El remanente genera crédito.
  Esta precisión no reconstruye pagos legacy aprobados ni altera sus recibos.
- La fecha bancaria no es la fecha de aprobación. No se aprueban fechas futuras
  en Lima. Gracia y política diaria provienen de snapshots históricos.

## Parcial y excedente

- CON-27: `monto_pagado` acumula abonos, sin reducir el bruto exigible. Si queda
  deuda vencida, la cuota conserva EN_MORA y las reservas siguen bloqueadas.
  Fuera de mora, un abono incompleto corresponde a PAGO_PARCIAL. La solvencia se
  deriva de deuda real; completar una cuota no habilita si existen otras vencidas.
- CON-28: solo el remanente crea crédito. Su origen es el comprobante aprobado:
  en legacy, importe menos imputaciones; en diario, ledger firmado CREDITO.
  CON-14 consume estas fuentes existentes sin duplicar el abono bancario.
- CON-13 consume el crédito al emitir, una sola vez. El alcance de las
  conciliaciones diarias impide reutilizarlo en cuotas emitidas después.
- Un retroactivo puede cambiar el crédito de otro comprobante: el campo
  `saldo_a_favor_generado` del recibo no equivale necesariamente al incremento
  global del saldo a favor. No se reescriben recibos originales.
- Crédito ya consumido o fondos de mora comprometidos responden 409 con sus
  códigos vigentes, sin inventar financiación ni confirmar efectos parciales.

## Observación y rechazo

- CON-26: motivo público no vacío, máximo 2000 caracteres; notas privadas
  opcionales hasta 2000. OBSERVADO y RECHAZADO no acreditan su comprobante.
- OBSERVADO permite `PUT /pagos/{id}/voucher`: conserva UUID, hash y datos
  bancarios, versiona evidencia y vuelve a EN_REVISION. RECHAZADO es definitivo.
- Revisar regulariza la mora diaria provisionalmente pausada. «Sin acreditar el
  pago» no significa prohibir esos devengos legítimos ni sus compensaciones.
- Avisos se producen mediante el outbox existente. Fallar el transporte no
  deshace una decisión financiera. Cola/SIMULADO no prueba recepción real:
  el transporte de correo real y su aceptación integrada dependen de CON-78.

## Interfaz y recuperación

La bandeja conserva listado y permisos de CON-24. La interfaz muestra el recibo
persistido, sus importes y el motivo, sin llamarlo saldo actual. Consulta de
resultado no modifica finanzas. GET/POST de resultado usan
`Cache-Control: private, no-store` y `Vary: Authorization`.
Los importes se muestran sin inventar moneda.
Un error conserva código y HTTP; una respuesta de red incierta no afirma que el
pago fue rechazado. Se ofrece consultar el resultado, sin aprobar automáticamente
otra vez. Una respuesta tardía de otro condominio/unidad se descarta.

## Verificación

BDD: `../02-domains/02-pagos-y-moras/features/sprint_3_anderson.feature`.
Pruebas PostgreSQL dedicadas, más regresiones de pagos, mora, fondos, CON-14,
CON-13, CON-77 y notificaciones. Las pruebas usan fechas fijas, sesiones
independientes y `autoflush=False`, nunca bases operativas o compartidas.
