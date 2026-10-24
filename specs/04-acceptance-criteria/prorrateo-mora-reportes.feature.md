# Aceptación objetivo: prorrateo, moras, reportes y evidencia

Escenarios documentales **pendientes de automatización e implementación**; no son
pruebas ya ejecutables. Regla: [dominio](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).

Primera entrega: pruebas automáticas de configuración/versionado en
`src/tests/unit/test_politica_diaria.py`, transporte inline en
`src/tests/integration/test_voucher_inline.py` e historial real dentro de
`src/tests/integration/test_convergencia_con72.py` (requiere PostgreSQL).
Motor diario, reparto, fondos y exportaciones de los escenarios siguientes
permanecen pendientes; no se considera completada esta característica integral.

```gherkin
Característica: Mora diaria por cuota mensual y fecha bancaria
  Escenario: Sin gracia predeterminada
    Dado una cuota con vencimiento 2026-10-10 y principal pendiente de 150.00 PEN
    Y política diaria de 1.00 PEN y gracia 0
    Cuando se procesa el 2026-10-11 en America/Lima
    Entonces su mora es 1.00 y su deuda total es 151.00
    Y el departamento tiene restringidas las reservas aunque el cron no haya actualizado su marca

  Escenario: Dos cuotas acumulan independientemente
    Dado septiembre y octubre impagos con vencimientos el día 10
    Y mora diaria de 1.00 PEN y gracia 0
    Cuando se procesa hasta el 2026-10-12 inclusive
    Entonces septiembre acumula 32.00 PEN y octubre 2.00 PEN
    Y el incremento conjunto del día 12 es 2.00 PEN

  Escenario: Reejecución y recuperación de días omitidos
    Dado una cuota impaga vencida el 10 con mora diaria de 1.00 PEN
    Cuando dos workers procesan concurrentemente el 13 y recuperan días 11 a 13
    Y se repite la ejecución
    Entonces existen tres devengos de 1.00 y ninguna duplicación

  Escenario: Tarifa editable sin recalcular historia
    Dado una cuota emitida con tarifa 1.00 y gracia 0
    Cuando la junta cambia la tarifa global a 2.50 y emite otra cuota
    Entonces la primera conserva 1.00 y la nueva fotografía 2.50
    Y cada cambio registra auditoría de siete campos

  Escenario: Herencia y excepción del responsable
    Dado gracia global 2 y dos vínculos de una unidad
    Y el responsable tiene override 0 y el otro vínculo override 5
    Cuando se emite la cuota
    Entonces aplica gracia 0, sin sumar ni maximizar excepciones
    Cuando se establece override null para una nueva emisión
    Entonces hereda gracia 2

  Escenario: Pago oportuno aprobado tarde
    Dado principal 150.00 con vencimiento 10 y gracia 0
    Y un pago de 150.00 con operación bancaria validada del día 10
    Cuando la junta lo aprueba el día 14
    Entonces la cuota queda pagada sin mora
    Y cualquier devengo posterior se compensa con trazabilidad, sin borrar registros

  Escenario: Pago tardío incluye su día de operación
    Dado principal 150.00 vencido el día 10 y tarifa 1.00
    Y un pago validado de 152.00 con operación del día 12
    Cuando se aprueba el día 15
    Entonces se imputan 2.00 a mora y 150.00 al principal
    Y no se cargan días 13 a 15

  Escenario: Principal liquidado con mora residual
    Dado principal liquidado y mora pendiente por un ajuste auditado
    Cuando transcurre otro día
    Entonces no se genera mora sobre la mora residual
    Y la deuda residual sigue restringiendo reservas

  Escenario: Protección de revisión no condona
    Dado comprobante EN_REVISION y pausa provisional de 24 horas
    Cuando se rechaza tras tres días de atraso
    Entonces se recuperan los tres días exigibles
    Y reprocesar no renueva indefinidamente la pausa

Característica: Reparto por pisos y unidades
  Escenario: Cuatro edificios con pesos exactos
    Dado edificios con 14, 14, 10 y 10 pisos y gasto común de 4800.00
    Cuando se calcula POR_PISOS
    Entonces se asignan 1400.00, 1400.00, 1000.00 y 1000.00
    Y se conserva denominador 48 sin redondeo previo de porcentajes

  Escenario: Reparto equitativo y cierre de centavos
    Dado 139 unidades del edificio 03 y gasto distribuible de 500.00
    Cuando se distribuye y cierra el ítem
    Entonces 99 unidades reciben 3.60 y 40 reciben 3.59 según orden estable
    Y la suma es 500.00 y el unitario de referencia mostrado es 3.60
    Y otros edificios no reciben ese gasto exclusivo

  Escenario: Abono no es saldo a favor individual
    Dado un aporte de electricidad con signo negativo en la fuente
    Cuando se normaliza como ABONO y se distribuye su magnitud
    Entonces reduce el presupuesto una sola vez sin crear pagos ni créditos personales

  Escenario: Caso histórico discrepante
    Dado la transcripción de septiembre con sus totales declarados
    Cuando se valida
    Entonces se conserva la evidencia original y se muestran las diferencias
    Y no se permite aprobar hasta conciliar importes, financiación y fondos

Característica: Gastos cubiertos por moras cobradas
  Escenario: Cobertura parcial
    Dado fondo disponible de moras conciliadas de 300.00 y gasto de 500.00
    Cuando se aprueba aplicar 300.00 al gasto
    Entonces el distribuible es 200.00 y el fondo disponible final es 0.00
    Y el pago al proveedor no se contabiliza dos veces

  Escenario: Unitario cero con sustento
    Dado gasto de 3900.00 y fondo disponible de 3900.00
    Cuando se financia completamente con moras cobradas
    Entonces se conserva el gasto y el movimiento de 3900.00
    Y el distribuible y el unitario son 0.00

  Escenario: No gastar moras no cobradas ni fondos ya reservados
    Dado moras devengadas de 5000.00 y cobradas de 100.00
    Y otro borrador ya reserva los 100.00 disponibles
    Cuando se intenta reservar 1.00 adicional concurrentemente
    Entonces se rechaza sin sobregiro ni aplicación duplicada

Característica: Reporte mensual y evidencia privada
  Escenario: PDF y DOCX de la misma versión
    Dado un prorrateo aprobado con versión explícita
    Cuando se exporta PDF y DOCX
    Entonces ambos contienen mismos conceptos, importes, cobertura y ajustes
    Y modificar el DOCX local no modifica la versión oficial

  Escenario: Borrador y conflicto de versión
    Dado un borrador modificado después de su previsualización
    Cuando se solicita exportar con versión anterior
    Entonces se responde 409 sin exportar otra versión silenciosamente
    Y las exportaciones válidas de borrador llevan marca BORRADOR

  Escenario: Vista inline e historial autorizados
    Dado un comprobante con evidencia PNG o JPEG o PDF vigente e histórica
    Cuando un usuario autorizado pide inline con evidencia_id del comprobante
    Entonces recibe el archivo con MIME validado, no-store y nosniff
    Y puede visualizarlo sin guardarlo manualmente y descargarlo por separado
    Y una referencia de otra unidad o condominio no entrega archivo ni ruta privada

  Escenario: Reporte general no filtra evidencia ni deudas de vecinos
    Dado un residente autorizado a su edificio
    Cuando consulta o exporta el reporte aprobado
    Entonces no recibe comprobantes, teléfonos personales ni deudas nominales ajenas
    Y un fallo de generación no modifica el presupuesto ni sus cuotas
```
