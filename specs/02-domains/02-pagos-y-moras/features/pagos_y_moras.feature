# language: es
Característica: Conciliación de pagos bancarios y aplicación de moras
  Como tesorero de la junta directiva
  Quiero conciliar los comprobantes bancarios y que el sistema gestione las moras
  Para mantener la liquidez y justicia financiera en el condominio

  Escenario: Aplicación automática de penalidad por mora al expirar periodo de gracia
    Dado que el departamento "402" tiene una cuota vencida de "150.00" soles con fecha de vencimiento "2026-10-20"
    Y el periodo de gracia configurado es de 2 días calendario
    Y el residente no ha reportado ningún comprobante de pago
    Cuando el evaluador nocturno de moras se ejecuta el "2026-10-23" a las 00:01 horas
    Entonces el estado de la cuota cambia a "EN_MORA"
    Y se agrega un recargo por mora de "20.00" soles
    Y el total exigible del departamento "402" pasa a ser de "170.00" soles
    Y el departamento queda inhabilitado para reservar áreas comunes

  Escenario: Rechazo de comprobante duplicado por clave de idempotencia
    Dado que existe un comprobante previamente aprobado en el banco "BCP" con operacion "098412" por "150.00" soles
    Cuando un residente intenta registrar nuevamente un voucher con banco "BCP" y operacion "098412"
    Entonces el sistema rechaza la solicitud con código de error "VOUCHER_YA_CONCILIADO"
    Y no se crea ningún registro duplicado en la base de datos

  Escenario: Imputación en orden de prelación con excedente a saldo a favor
    Dado que el departamento "205" mantiene una cuota vencida de "120.00" soles
    Cuando la junta directiva aprueba un comprobante reportado por "150.00" soles
    Entonces la cuota vencida pasa al estado "PAGADA"
    Y el remanente de "30.00" soles se asigna automáticamente al "saldo_a_favor" del departamento "205"
