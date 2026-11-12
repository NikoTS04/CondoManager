# language: es
Característica: Reporte y revisión durable de comprobantes locales
  Escenario: Reportar evidencia local sin pagar la deuda
    Dado un residente activo vinculado a un departamento con deuda en mora
    Cuando sube un voucher válido y reporta su pago
    Entonces recibe un comprobante EN_REVISION persistido
    Y url_voucher contiene la ruta autenticada del comprobante
    Y la deuda y el bloqueo de reservas no cambian

  Escenario: Aprobar una única vez y recuperar la solvencia
    Dado un comprobante persistido que cubre toda la deuda en mora
    Cuando la junta aprueba el comprobante
    Entonces las imputaciones, el resultado, la auditoría y el evento son atómicos
    Y el siguiente intento de reserva queda habilitado
    Y volver a aprobar no aplica fondos otra vez

  Escenario: Observar no equivale a aprobar
    Dado un comprobante EN_REVISION
    Cuando la junta lo observa con un motivo
    Entonces el estado persistido es OBSERVADO y los saldos no cambian

  Escenario: Reintentos concurrentes conservan un único comprobante
    Dado un voucher autorizado y dos reportes equivalentes
    Cuando llegan desde sesiones PostgreSQL independientes
    Entonces existe un solo comprobante y un único evento de recepción

  Escenario: Un voucher privado no puede recuperarse desde otra unidad
    Dado un comprobante con evidencia adjuntada a un departamento
    Cuando un residente sin vínculo intenta descargar el voucher
    Entonces recibe rechazo y no obtiene el contenido del archivo
