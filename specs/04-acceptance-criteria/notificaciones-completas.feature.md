# Cierre PROC-03 EMAIL

```gherkin
Escenario: Confirmación repetida de audiencia revisada
  Dada una audiencia contextual previsualizada por Junta
  Cuando confirma dos veces el mismo borrador
  Entonces solo existe un lote y un aviso por usuario
  Y cambios de audiencia previos a confirmar exigen otra previsualización

Escenario: Incertidumbre y supresión
  Dado un contacto bloqueado y un intento incierto de otro contacto
  Cuando corre el job
  Entonces el bloqueado no consume transporte y el incierto no se reenvía
  Cuando Junta registra una decisión explícita con evidencia y ciclo esperado
  Entonces la resolución queda auditada sin borrar intentos anteriores

Escenario: Recuperación y exactitud
  Dado un cursor diario y un abono parcial posterior al encolado
  Cuando el programador se recupera
  Entonces persiste avisos faltantes una sola vez y actualiza el saldo al enviar
  Y no envía avisos de cuotas pagadas

Escenario: Rehabilitación
  Dado un departamento con deuda vencida
  Cuando su pago aprobado cancela toda la deuda vencida
  Entonces se genera un único aviso de reservas rehabilitadas
  Y repetir la conciliación no duplica ese aviso
```
