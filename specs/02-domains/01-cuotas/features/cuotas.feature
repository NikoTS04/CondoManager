# language: es
Característica: Presupuesto mensual y emisión de cuotas de mantenimiento ordinarias
  Como miembro autorizado de la junta
  Quiero registrar y aprobar el presupuesto mensual del condominio
  Para que la emisión distribuya un importe persistido y aprobado

  Escenario: Crear y modificar un presupuesto mensual en borrador
    Dado que existe el condominio "Villa Bonita 3" con moneda "PEN"
    Y estoy autenticado como "ADMIN_JUNTA" de ese condominio
    Cuando registro el presupuesto del periodo "2026-10" por "20000.00" "PEN" con vencimiento "2026-10-20"
    Entonces se crea un único presupuesto con UUID y estado "BORRADOR"
    Y el actor de creación corresponde al claim "sub" de mi token
    Y se registra la auditoría "PRESUPUESTO_CREADO"
    Cuando reemplazo el monto del borrador por "20500.00"
    Entonces el presupuesto conserva su UUID y queda con monto "20500.00"
    Y se registra la auditoría "PRESUPUESTO_MODIFICADO" con los estados anterior y posterior

  Esquema del escenario: Rechazar datos inválidos del presupuesto
    Dado que existe el condominio "Villa Bonita 3" con moneda "PEN"
    Y estoy autenticado como "ADMIN_JUNTA" de ese condominio
    Cuando intento registrar periodo "<periodo>", monto "<monto>", moneda "<moneda>" y vencimiento "<vencimiento>"
    Entonces la API responde 422 con código "DATOS_PRESUPUESTO_INVALIDOS"
    Y no se persiste ningún presupuesto

    Ejemplos:
      | periodo | monto    | moneda | vencimiento |
      | 2026-13 | 20000.00 | PEN    | 2026-10-20 |
      | 2026-10 | 0.00     | PEN    | 2026-10-20 |
      | 2026-10 | 20000.00 | USD    | 2026-10-20 |
      | 2026-10 | 20000.00 | PEN    | 2026-11-20 |

  Escenario: Aprobar un presupuesto y hacerlo inmutable
    Dado que existe un presupuesto "BORRADOR" para el periodo "2026-10"
    Y estoy autenticado como "ADMIN_JUNTA" de su condominio
    Cuando apruebo el presupuesto
    Entonces su estado cambia a "APROBADO"
    Y "aprobado_por" corresponde al claim "sub" de mi token
    Y "aprobado_en" contiene una fecha UTC
    Y se registra la auditoría "PRESUPUESTO_APROBADO"
    Cuando intento modificar o aprobar nuevamente el presupuesto
    Entonces la API responde 409 con código "PRESUPUESTO_NO_EDITABLE"

  Escenario: Rechazar escritura sin autenticación
    Dado que no envío un Bearer Token
    Cuando intento registrar un presupuesto mensual
    Entonces la API responde 401 con código "NO_AUTENTICADO"

  Escenario: Restringir al auditor a solo lectura
    Dado que existe un presupuesto para el periodo "2026-10"
    Y estoy autenticado como "AUDITOR" del mismo condominio
    Cuando consulto el presupuesto por condominio y periodo
    Entonces obtengo el presupuesto sin poder modificarlo
    Cuando intento aprobar el presupuesto
    Entonces la API responde 403 con código "PRESUPUESTO_ACCESO_DENEGADO"

  Escenario: Impedir dos presupuestos del mismo condominio y periodo
    Dado que el condominio "Villa Bonita 3" ya tiene un presupuesto para "2026-10"
    Y estoy autenticado como "ADMIN_JUNTA" de ese condominio
    Cuando intento registrar otro presupuesto para "2026-10"
    Entonces la API responde 409 con código "PRESUPUESTO_PERIODO_DUPLICADO"
    Y permanece una sola fila para ese condominio y periodo

  Escenario: Permitir el mismo periodo en condominios distintos
    Dado que existen dos condominios con moneda "PEN"
    Y soy "SUPERADMIN"
    Cuando registro un presupuesto para "2026-10" en cada condominio
    Entonces ambos presupuestos se crean con UUID diferentes

  Escenario: Aislar la consulta por condominio
    Dado que existe un presupuesto del condominio "Villa Bonita 3" para "2026-10"
    Y estoy autenticado como "ADMIN_JUNTA" de otro condominio
    Cuando intento consultarlo usando el identificador de "Villa Bonita 3"
    Entonces la API responde 403 con código "PRESUPUESTO_ACCESO_DENEGADO"
    Y no expone datos del presupuesto

  Escenario: CON-11 solo recupera un presupuesto aprobado
    Dado que existe un presupuesto "BORRADOR" para el periodo "2026-10"
    Cuando CON-11 solicita el presupuesto utilizable del condominio y periodo
    Entonces la emisión queda bloqueada por falta de presupuesto aprobado
    Cuando un usuario autorizado aprueba ese presupuesto
    Entonces CON-11 recupera su monto y vencimiento persistidos
    Y no acepta un monto alternativo enviado por el cliente

  Escenario: Emisión regular con cálculo de alícuota porcentual
    Dado que existe un condominio con presupuesto mensual aprobado de "20000.00" soles
    Y el departamento "301" tiene un coeficiente de participación de "0.8500" por ciento
    Y el departamento "301" no registra saldos a favor
    Cuando el sistema emite el lote de cuotas para el periodo "2026-10"
    Entonces se genera una cuota por un monto exacto de "170.00" soles
    Y la cuota queda registrada en estado "PENDIENTE"
    Y la fecha de vencimiento es el "2026-10-20"

  Escenario: Liquidación automática de cuota mediante saldo a favor preexistente
    Dado que existe un condominio con presupuesto mensual aprobado de "20000.00" soles
    Y el departamento "102" tiene una cuota emitida de "150.00" soles
    Y el departamento "102" cuenta con un saldo a favor de "200.00" soles
    Cuando se procesa la amortización automática del lote
    Entonces el estado de la cuota cambia inmediatamente a "PAGADA"
    Y el saldo a favor restante del departamento "102" pasa a ser de "50.00" soles
    Y se registra la transacción compensatoria en la bitácora inmutable de auditoría
