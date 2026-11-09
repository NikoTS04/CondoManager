# language: es
Característica: Conciliación integrada de Anderson en Sprint 3
  Escenario: CON-25 aprobar y recuperar el mismo resultado
    Dado una unidad autorizada con deuda fija de "100.00"
    Cuando la junta aprueba un comprobante de "100.00"
    Entonces la deuda restante es "0.00" y el crédito es "0.00"
    Y repetir la aprobación recupera el mismo recibo

  Escenario: CON-27 abonar sin perder la condición de mora
    Dado una unidad autorizada con deuda fija de "100.00"
    Cuando la junta aprueba un comprobante de "40.00"
    Entonces la deuda restante es "60.00" y el crédito es "0.00"
    Y la unidad conserva el bloqueo de reservas por deuda vencida

  Escenario: CON-28 conservar el origen del excedente
    Dado una unidad autorizada con deuda fija de "100.00"
    Cuando la junta aprueba un comprobante de "120.00"
    Entonces la deuda restante es "0.00" y el crédito es "20.00"
    Y el estado de cuenta identifica el pago sin duplicar su abono

  Escenario: CON-26 observar y subsanar conservando historia
    Dado una unidad autorizada con deuda fija de "100.00"
    Cuando la junta observa un comprobante y el residente subsana la evidencia
    Entonces la deuda sigue intacta y el comprobante vuelve a EN_REVISION
    Y se conserva la evidencia de la revisión anterior
