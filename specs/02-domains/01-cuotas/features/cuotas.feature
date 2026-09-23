# language: es
Característica: Emisión y cálculo de cuotas de mantenimiento ordinarias
  Como administrador del condominio
  Quiero emitir las cuotas mensuales basadas en el presupuesto y alícuotas
  Para distribuir equitativamente los gastos comunes del edificio

  Escenario: Emisión regular con cálculo de alícuota porcentual
    Dado que existe un condominio con presupuesto mensual de "20000.00" soles
    Y el departamento "301" tiene un coeficiente de participación de "0.8500" por ciento
    Y el departamento "301" no registra saldos a favor
    Cuando el sistema emite el lote de cuotas para el periodo "2026-10"
    Entonces se genera una cuota por un monto exacto de "170.00" soles
    Y la cuota queda registrada en estado "PENDIENTE"
    Y la fecha de vencimiento es el "2026-10-20"

  Escenario: Liquidación automática de cuota mediante saldo a favor preexistente
    Dado que existe un condominio con presupuesto mensual de "20000.00" soles
    Y el departamento "102" tiene una cuota emitida de "150.00" soles
    Y el departamento "102" cuenta con un saldo a favor de "200.00" soles
    Cuando se procesa la amortización automática del lote
    Entonces el estado de la cuota cambia inmediatamente a "PAGADA"
    Y el saldo a favor restante del departamento "102" pasa a ser de "50.00" soles
    Y se registra la transacción compensatoria en la bitácora inmutable de auditoría
