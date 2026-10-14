# language: es
Característica: Aplicación automática y atómica del crédito del departamento (CON-13)
  Como residente
  Quiero amortizar las cuotas nuevas con mi saldo a favor
  Para pagar solamente el pendiente sin perder créditos ni alterar el presupuesto

  Esquema del escenario: Amortizar el bruto definitivo de una cuota
    Dado una cuota EMITIDA de "150.00" y saldo disponible "<saldo>"
    Cuando se aplica automáticamente el saldo a favor
    Entonces el bruto exigible sigue siendo "150.00" y el descuento "0.00"
    Y el pago con crédito es "<aplicado>" y el pendiente "<pendiente>"
    Y el saldo restante es "<restante>" y el estado "<estado>"
    Y la auditoría registra sus siete campos obligatorios y el actor

    Ejemplos:
      | saldo  | aplicado | pendiente | restante | estado    |
      | 200.00 | 150.00   | 0.00      | 50.00    | PAGADA    |
      | 50.00  | 50.00    | 100.00    | 0.00     | PENDIENTE |
      | 0.00   | 0.00     | 150.00    | 0.00     | PENDIENTE |
      | 150.00 | 150.00   | 0.00      | 0.00     | PAGADA    |

  Escenario: Reintentar la misma cuota incluso si antes no tenía crédito
    Dado una aplicación registrada para una cuota
    Cuando se reintenta la aplicación con un saldo disponible diferente
    Entonces se devuelve la aplicación original sin consumir saldo ni duplicar auditorías

  Escenario: Serializar cuotas concurrentes del mismo departamento
    Dado dos cuotas nuevas de "100.00" y un saldo compartido de "150.00"
    Cuando ambas aplicaciones compiten por el bloqueo del condominio
    Entonces el pago acumulado es "150.00" y el saldo restante "0.00"
    Y una cuota queda PAGADA y la otra PENDIENTE con pago "50.00"

  Escenario: Mantener lineal la cadena de auditoría entre departamentos concurrentes
    Dado dos departamentos distintos del mismo condominio con cuotas nuevas
    Cuando ambas aplicaciones compiten por el bloqueo del condominio
    Entonces los bloqueos siguen el orden condominio, departamento y cuota
    Y cada hash_previo corresponde al hash_actual de la auditoría anterior
    Y la cadena no se bifurca entre departamentos

  Escenario: Aplicar crédito después del ajuste residual
    Dado un lote cuyo redondeo requiere ajustar centavos
    Cuando se fija el bruto definitivo y luego se amortizan las cuotas
    Entonces la suma bruta permanece igual al presupuesto aprobado
    Y ningún pago supera el exigible definitivo

  Escenario: Revertir una aplicación fallida
    Dado una cuota nueva y crédito disponible
    Cuando falla la persistencia de la auditoría
    Entonces se revierten cuota, saldo y registro de aplicación juntos
