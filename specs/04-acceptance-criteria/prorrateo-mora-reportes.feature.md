# Aceptación objetivo: prorrateo, moras, reportes y evidencia

Característica: Fondos conciliados y cobertura de gastos (0020)
  Escenario: Solo la mora efectivamente cobrada alimenta fondos
    Dado un pago aprobado con principal, mora y crédito excedente
    Cuando se concilia, solo el componente mora entra al fondo de su edificio
    Y reintentos o el devengo diario no duplican ni crean caja

  Escenario: Reserva concurrente y cobertura íntegra
    Dado un fondo disponible y un gasto exclusivo de igual importe
    Cuando se reserva y aprueba su cobertura con versión y clave idempotente
    Entonces se conserva el gasto bruto y el cargo unitario es cero
    Y aprobación no vuelve a descontar el fondo
    Y dos solicitudes no pueden gastar más saldo del disponible

  Escenario: Liberación y modificación del borrador
    Dado una reserva vigente en un ítem del borrador
    Cuando se libera, el fondo recupera disponibilidad y el neto vuelve a cobrarse
    Y omitir el ítem sin liberarla o liberar una confirmada responde conflicto

  Escenario: Retroactivo con fondos comprometidos
    Dado moras cobradas reservadas o aplicadas a gastos
    Cuando un retroactivo necesita revertir más de la disponibilidad
    Entonces responde 409 FONDOS_MORAS_COMPROMETIDOS sin cambios parciales

  Escenario: Reporte privado y snapshot de caja
    Dado un presupuesto aprobado con cobertura de moras
    Cuando se exporta PDF o DOCX se muestran bruto, cobertura, neto y resumen congelado
    Y el residente no recibe movimientos bancarios ni aplicaciones ajenas

Característica: Devengo diario persistente y conciliación bancaria (0019)
  Escenario: Recuperación e idempotencia por cuota mensual
    Dado dos cuotas diarias impagas con política y gracia fotografiadas
    Cuando dos workers recuperan los días posteriores al vencimiento y gracia
    Entonces existe un cargo por cuota y fecha local, sin duplicados
    Y mora, deuda, auditoría y outbox se confirman juntos

  Escenario: Pago bancario oportuno aprobado tarde
    Dado un pago suficiente con fecha bancaria dentro del plazo
    Y cargos diarios contabilizados mientras se revisaba
    Cuando la junta valida y aprueba el pago
    Entonces se compensan los cargos posteriores sin borrar los originales
    Y no se cobra mora por la demora administrativa

  Escenario: Pagos aprobados fuera del orden bancario
    Dado un pago posterior ya aprobado y un nuevo pago bancario anterior
    Cuando se aprueba el anterior
    Entonces se reconstruyen ambos en orden fecha y UUID
    Y las diferencias se registran por componente sin reescribir revisiones

  Escenario: Crédito retroactivo ya consumido
    Dado que una reconstrucción necesita reducir crédito que ya no está disponible
    Cuando se intenta aprobar el retroactivo
    Entonces responde 409 CREDITO_RETROACTIVO_CONSUMIDO sin cambios financieros

  Escenario: Pausa de revisión no renovable por el job
    Dado un comprobante en revisión reportado hace menos de 24 horas
    Cuando se ejecuta el motor, se postergan cargos nuevos provisionalmente
    Y tras las 24 horas o al rechazar se recuperan todos los días exigibles


Tercera entrega: `src/tests/unit/test_prorrateo.py` verifica pisos, 139 unidades,
abonos, centavos y límites; `src/tests/integration/test_prorrateo_db.py` prueba
catálogo, versiones, snapshot, emisión, privacidad, eventos v2 y exportación en
PostgreSQL. `src/tests/unit/test_documentos_prorrateo.py` abre PDF/DOCX y verifica
importes, estado y versión. La cuarta entrega añade
`src/tests/unit/test_calculo_mora_diaria.py` y
`src/tests/integration/test_mora_diaria_db.py`: fechas, recuperación, pausa,
concurrencia, retroactivos, crédito consumido, conservación de recibos, eventos,
rollback y downgrade. La quinta entrega se verifica con
`src/tests/integration/test_fondos_moras_db.py`: cobros reales, cobertura cero,
idempotencia, concurrencia, retroactivos, adopción prospectiva, permisos, eventos,
rollback, inmutabilidad y downgrade; también con pruebas puras de cobertura.

Escenarios documentales **pendientes de automatización e implementación**; no son
pruebas ya ejecutables. Regla: [dominio](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).

Primera entrega: pruebas automáticas de configuración/versionado en
`src/tests/unit/test_politica_diaria.py`, transporte inline en
`src/tests/integration/test_voucher_inline.py` e historial real dentro de
`src/tests/integration/test_convergencia_con72.py` (requiere PostgreSQL).
Motor diario, reparto, fondos y exportaciones de los escenarios siguientes
permanecen pendientes; no se considera completada esta característica integral.

Segunda entrega: `src/tests/unit/test_condiciones_pago.py` cubre herencia/override,
versionado, auditoría, snapshot y frontera UTC/Lima. La integración concurrente
real está en `src/tests/integration/test_condiciones_pago_db.py` (PostgreSQL).

```gherkin
Característica: Mora diaria por cuota mensual y fecha bancaria
  Escenario: Revocar responsable no restaura su excepción al reactivar vínculo
    Dado responsable con gracia individual 5 y gracia global 0
    Cuando se revoca el vínculo y luego se restaura
    Entonces las nuevas cuotas heredan gracia global hasta nueva designación explícita
    Y las cuotas emitidas antes mantienen su responsable y gracia histórica

  Escenario: Cambios concurrentes de condiciones de pago
    Dado versión 1 de condiciones de pago de un departamento
    Cuando dos administradores envían cambios distintos con versión esperada 1
    Entonces solo uno confirma y el segundo recibe 409

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
  Escenario: Presupuesto detallado aprobado no se altera al emitir
    Dado un presupuesto detallado aprobado con snapshot de conceptos y padrón
    Cuando cambia el padrón de unidades activas antes de emitir
    Entonces se rechaza la emisión sin redistribuir ni crear cuotas parciales

  Escenario: Total distribuible cero
    Dado cargos y abonos que se compensan exactamente sin cargos individuales negativos
    Cuando se aprueba y emite el presupuesto detallado
    Entonces se conservan el detalle y las cuotas de bruto cero pagadas sin consumir créditos

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
