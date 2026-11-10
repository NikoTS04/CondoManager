# CON-14 — Estado de cuenta por unidad y periodo

Base: `/api/v1`. `GET /cuotas/departamentos/{departamento_id}/estado-cuenta`.
Consulta de solo lectura: no devenga mora, concilia, corrige ni crea movimientos.

## Acceso y contrato

- Bearer y sesión persistida vigente. Residente: vínculo activo de la unidad en
  su contexto; Junta/Auditor: su condominio; SuperAdmin: soporte global por UUID.
- UUID de unidad validado antes de leer movimientos. 401 sin sesión, 403 sin
  alcance/vínculo, 404 unidad inexistente, 409 historial inconsistente, 422 filtros.
- `desde` y `hasta`: fechas inclusivas de **registro en America/Lima**, ambas o
  ninguna. Sin fechas: mes actual de Lima. Máximo 366 días, `hasta >= desde`.
  La fecha bancaria/devengo se muestra aparte y no altera retrospectivamente la
  fecha de registro de una aprobación o compensación.
- `limite` de 1 a 200 (50 por defecto) y `offset >= 0`. Orden estable por registro,
  tipo y UUID. Saldos y totales corresponden a todo el rango, no solo a la página.
- Dinero como cadena decimal de dos posiciones, incluidos saldos negativos
  (saldo neto a favor). `Cache-Control: private, no-store`.

## Lectura financiera

Se reutilizan cuotas, comprobantes aprobados, imputaciones legacy, conciliaciones
diarias, devengos/ajustes inmutables y aplicaciones de crédito CON-13.

1. Cargo de cuota: exigible actual menos devengos diarios netos, pues estos tienen
   su propia fila. Las cuotas históricas conservan su base registrada.
2. Devengo y ajuste: cada registro original permanece visible. Una compensación
   negativa reduce el cargo; no borra el devengo ni un recibo anterior.
3. Pago aprobado: un solo abono por el importe del comprobante, en su fecha de
   aprobación. Incluye su excedente: no se suma de nuevo el crédito como otro pago.
4. Distribuciones/compensaciones del pago y aplicaciones CON-13 se muestran como
   detalle trazable, con cargo/abono cero: reasignan deuda y crédito del mismo
   departamento, sin introducir otro ingreso en su saldo neto.
5. Pagos EN_REVISION aparecen separados; no reducen el saldo.

`saldo_final = saldo_inicial + cargos_periodo - abonos_periodo`.
El saldo neto actual debe coincidir con deuda persistida menos saldo a favor.
`deuda_actual`, `deuda_vencida_actual` y `saldo_a_favor_actual` se identifican como
actuales, separados del saldo de cierre de un rango anterior.

## Base histórica y consistencia

Antes de la primera operación detallada puede existir crédito inicial o
amortización previa sin desglose. Se identifican por separado:

- crédito inicial = crédito actual + crédito CON-13 consumido − crédito generado
  por pagos (ledger diario neto o remanente legacy; nunca recibos diarios obsoletos);
- abono histórico por cuota = amortizado actual − aplicaciones diarias netas −
  imputaciones legacy − aplicación inicial CON-13.

Ambos deben ser no negativos. Forman `saldo_base_historico`, de origen sin fecha
documentada, que se declara explícitamente; no se inventa un movimiento bancario
ni una fecha de aprobación. `base_historica_sin_fecha` e `historial_desde` delimitan
lo conocido; una consulta anterior a ese inicio no certifica una historia completa.
No se utiliza un ajuste arbitrario para cuadrar diferencias: importes negativos,
pagos sin respaldo o una proyección que no concilie con deuda/crédito producen
409 `ESTADO_CUENTA_INCONSISTENTE`. No se modifica la base para ocultar el problema.

Lecturas en una transacción PostgreSQL REPEATABLE READ, READ ONLY para evitar
mezclar una conciliación concurrente con su estado anterior. No requiere migración.

## Entrega

Pantalla del residente en la pestaña de cuenta, unidad autorizada, rango de fechas,
resumen inicial/cargos/abonos/final, movimientos con referencias, paginación,
pendientes separados y estados de carga, vacío y error. Cambiar de unidad o filtro
descarta datos previos y respuestas tardías. Se respetan los cuatro roles vigentes.

Los casos de parciales/excedentes y correcciones se verifican sobre el productor
financiero vigente; cualquier cambio de contrato de CON-25/27/28 requiere repetir
esa integración. No se cambia el motor de Anderson ni se cierra Jira automáticamente.
