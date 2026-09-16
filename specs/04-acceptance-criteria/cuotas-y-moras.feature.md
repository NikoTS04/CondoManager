# Criterios de Aceptación: Cuotas, Pagos y Moras (BDD / Gherkin)

## Característica: Emisión, Conciliación y Aplicación Automática de Moras

### Escenario 1: Generación mensual de cuotas con alícuotas
```gherkin
Dado que el edificio "Torre A" tiene un presupuesto mensual de mantenimiento de S/ 15,000.00
Y el departamento 101 tiene un coeficiente de participación del 1.20%
Cuando el sistema ejecuta el proceso programado el día 1 del mes a las 00:00 horas
Entonces se genera una cuota ordinaria para el departamento 101 por un importe de S/ 180.00
Y la cuota queda registrada en estado "PENDIENTE"
Y la fecha de vencimiento se fija para el día 20 del mes a las 23:59:59.
```

### Escenario 2: Aplicación de mora tras vencer periodo de gracia sin pago
```gherkin
Dado que el departamento 202 tiene una cuota de S/ 180.00 con vencimiento el día 20
Y el condominio tiene configurado un periodo de gracia de 2 días y recargo por mora fijo de S/ 20.00
Y el residente del departamento 202 no ha reportado ningún comprobante de pago
Cuando el reloj del sistema avanza a las 00:01 horas del día 23
Entonces el estado de la cuota cambia a "EN_MORA"
Y se agrega un cargo por mora de S/ 20.00 a la cuenta del departamento 202
Y el total de la deuda exigible pasa a ser de S/ 200.00
Y se registra el evento en la bitácora de auditoría inmutable con los 7 campos obligatorios.
```

### Escenario 3: Postergación de mora si existe comprobante reportado pendiente de revisión
```gherkin
Dado que el departamento 305 tiene una cuota vencida el día 20
Y el periodo de gracia concluye el día 22 a las 23:59:59
Y el residente reportó un comprobante de pago el día 21 a las 18:00 (en estado "EN_REVISION")
Cuando el evaluador de moras corre el día 23 a las 00:01 horas
Entonces el sistema detecta el comprobante pendiente de conciliar
Y pospone la aplicación de la penalidad por 24 horas para permitir la revisión del administrador
Y notifica a la junta directiva que existe un comprobante pendiente de validación para evitar moras injustificadas.
```

### Escenario 4: Conciliación de pago con excedente (Saldo a Favor)
```gherkin
Dado que el departamento 401 tiene una cuota pendiente de S/ 150.00
Cuando el residente reporta un pago por S/ 200.00 y la junta directiva lo aprueba
Entonces la cuota de S/ 150.00 cambia al estado "PAGADA"
Y el remanente de S/ 50.00 se abona automáticamente como "saldo_a_favor" del departamento 401
Y dicho saldo queda disponible para descontarse en la emisión del próximo mes.
```
