# language: es
Característica: CON-14 - Estado de cuenta privado y trazable
  Escenario: Pago parcial y excedente en la cuenta
    Dado un departamento con un cargo de 100.00
    Cuando se aprueban abonos de 40.00 y 80.00
    Entonces la deuda actual es 0.00 y el saldo a favor es 20.00
    Y el saldo neto de cierre es -20.00
    Y el pago en revisión no se cuenta como otro abono

  Escenario: Una corrección mantiene la historia y el saldo correcto
    Dado un devengo y un pago aprobados con sus registros originales
    Cuando un pago retroactivo genera compensaciones de mora e imputación
    Entonces los movimientos originales y sus compensaciones permanecen consultables
    Y el estado de cuenta concilia con la deuda y crédito persistidos sin duplicar recibos

  Escenario: Aislamiento y paginación estable
    Dado un residente con una unidad autorizada
    Cuando consulta movimientos por rango y página
    Entonces los saldos corresponden a todo el rango y el orden es estable
    Y consultar una unidad ajena o con vínculo revocado es rechazado
