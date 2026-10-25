# Prorrateo jerárquico, mora diaria y rendición mensual

## Estado y precedencia

Avance parcial en rama de implementación: configuración diaria y edición auditada,
visor privado e historial implementados. Motor diario, prorrateo y fondos aún
pendientes. Emisión MONTO_DIARIO temporalmente rechazada con
`MOTOR_DIARIO_PENDIENTE`; no desplegar como solución financiera completa.
Detalle de adopción: [contrato](../../05-api/prorrateo-mora-reportes.md#avance-de-implementación--primera-entrega).

Segunda entrega: excepciones por vínculo, responsable único, revocación segura y
snapshot de nuevas emisiones implementados. Migración 0017 y concurrencia
verificadas en PostgreSQL aislado. No se inventan snapshots históricos. Motor
diario persistente y reconstrucción bancaria siguen pendientes de integración.

Especificación objetivo aprobada por el responsable del proyecto (2026-10-24).
**Pendiente de implementación**: no afirma que estas capacidades existan en código.
Complementa CON-9/10/11/13 y sustituye las reglas anteriores de vencimiento el día
20, gracia predeterminada de dos días, recargo único y fechas financieras UTC.
Los contratos históricos de integración se conservan como antecedentes, no como
excepción a estas reglas. No se reescriben presupuestos aprobados, lotes, pagos,
evidencias ni auditorías existentes; la adopción requiere una migración futura
con fecha de vigencia explícita y conciliación de saldos.

## 1. Calendario y política de mora

- Día de vencimiento regular: **10**, inclusive hasta las 23:59:59 de
  `America/Lima`. Se compara por fecha local; timestamps de auditoría en UTC.
- `dias_gracia`: global por condominio, entero 0..30, predeterminado **0**.
- `dias_gracia_override`: entero 0..30 o `null`, por vínculo propietario/inquilino
  con departamento. `null` hereda; `0` anula una gracia global positiva.
- La junta designa un único responsable de pago activo por departamento. Solo su
  excepción se aplica; no se suman ni se elige la mayor entre copropietarios.
  Sin responsable designado se hereda la política global. No cambia el deudor:
  existe una única obligación por departamento y periodo.
- `MONTO_DIARIO` es la modalidad predeterminada; `monto_mora_diario` es editable
  por SuperAdmin/Junta del contexto, decimal positivo de dos posiciones,
  predeterminado **1.00 en PEN**. No se aplica conversión implícita a USD: otros
  condominios deben declarar el importe en su moneda. `MONTO_FIJO` y
  `PORCENTAJE_SALDO` se conservan para compatibilidad, no son la política piloto.
- La política efectiva (importe, modalidad, gracia, responsable y zona horaria)
  se fotografía al emitir la cuota. Cambios posteriores rigen nuevas emisiones;
  ajustes de cuotas existentes requieren una operación explícita auditada.
- Cada **cuota mensual vencida** acumula su propia mora. Septiembre y octubre
  impagos producen dos cargos de 1.00 por cada nuevo día, no uno por departamento.
- Se cobra una vez por fecha local posterior a `vencimiento + gracia`, incluido
  el día efectivo de un pago tardío. No hay capitalización ni mora sobre mora.
  Un pago parcial no reduce el importe diario fijo. Se detiene cuando se cubre
  el principal de esa cuota; la mora pendiente sigue siendo deuda exigible y
  bloquea reservas, pero no genera nuevos recargos por sí misma.

### Conciliación y fecha efectiva

La fecha efectiva es `fecha_operacion` bancaria **validada** por la junta, no la
fecha de carga ni de aprobación. Se conserva el orden de imputación existente:
moras, extraordinarias vencidas, ordinarias vencidas y ordinaria vigente.
Antes de imputar, se determina la mora correspondiente a la fecha efectiva.
Pagos aprobados después se reconstruyen en orden efectivo (fecha, identificador
estable para empates) para no perjudicar al residente por demoras administrativas.
Un pago insuficiente para cubrir mora y principal no liquida la cuota.

La protección de 24 horas por comprobante `EN_REVISION` se conserva como pausa
de contabilización provisional, no como gracia ni condonación. Al aprobar se
regulariza hasta la fecha bancaria; al rechazar se recuperan todos los días
exigibles. Nunca se congela indefinidamente por reejecuciones del job. Un
comprobante no conciliado no extingue deuda ni habilita reservas.

El motor ejecuta diariamente después de medianoche de Lima y recupera fechas
omitidas, incluyendo cuotas `EN_MORA`, `VENCIDA` y `PAGO_PARCIAL`, no solo
`PENDIENTE`. La identidad de devengo es `(cuota_id, fecha_local)`; reintentos y
concurrencia no duplican cargos. Ajustes/reversos son movimientos compensatorios,
nunca borrados. Pagos retroactivos que alteren imputaciones o fondos ya utilizados
requieren conciliación transaccional: no ocultar déficit ni fabricar caja.

## 2. Dos niveles de reparto

**Categoría** (agua, limpieza...) y **jerarquía** (condominio, edificio, unidad)
son dimensiones distintas. Se mantiene un presupuesto ordinario por condominio y
periodo, desglosado en ítems y asignaciones por edificio; no se crean cuatro
presupuestos duplicados para un mismo gasto.

### Condominio → edificios: POR_PISOS

Decisión: distribuir los gastos comunes por pisos, usando el dato existente
`edificios.total_pisos`. Para el piloto: 4 edificios, dos de 14 y dos de 10;
denominador **48**. Cada edificio de 14 recibe `14/48` (29.166666… %) y cada
uno de 10 recibe `10/48` (20.833333… %). No redondear primero los porcentajes:
calcular con numerador/denominador y cerrar centavos sobre cada ítem.

Es una política prospectiva verificable, **no** la reconstrucción exacta del
prorrateo histórico. Se fotografía el padrón de edificios y sus pesos al aprobar.
Una asignación excepcional usa `ASIGNACION_EXPLICITA`, importes por edificio,
motivo, documento sustentatorio y aprobación. La suma debe cerrar con el gasto
común distribuible. No se inventan porcentajes para reproducir una transcripción.
Un gasto exclusivo usa `DIRECTO_EDIFICIO`, sin volver a repartirlo entre torres.

### Edificio → departamentos: EQUITATIVA en el piloto

El edificio 03 tiene **139 departamentos**: importe distribuible del edificio
dividido entre 139. Se fotografía la lista de unidades participantes; no usar 139
como constante universal ni sustituirla silenciosamente si cambia el padrón.
Se conservan alícuotas como modalidad alternativa, normalizadas dentro del
conjunto participante del edificio, no usando un coeficiente global incompatible.
Al aprobar se validan unidades activas y se resuelve cualquier diferencia con el
padrón esperado. Ningún gasto exclusivo se carga a otro edificio.

En ambos niveles: `Decimal`, `ROUND_HALF_UP`, dos posiciones monetarias y cierre
determinista por importe descendente e identificador ascendente, un centavo a la
vez, sin dejar cargos negativos. Los abonos se reparten por magnitud y se aplica
después su signo. Se cierran los ítems antes de sumar las cuotas; no volver a
repartir el total global con CON-10 como si el desglose no existiera.

El unitario impreso es una referencia redondeada. El anexo por departamento
conserva cargos y ajustes efectivos; no se promete que 139 × unitario redondeado
sea idéntico al total. La suma exacta de cargos debe coincidir con el total
distribuible, no con el gasto bruto ni con lo cubierto mediante moras.

## 3. Campos de origen y campos calculados

| Fuente | Campo objetivo | Regla |
|---|---|---|
| Septiembre 2026 | `periodo` | `2026-09`; moneda `PEN` |
| Código | `codigo_origen` | Literal, repetible; no es PK ni código normalizado |
| Descripción | `descripcion`, `concepto_codigo` | Identidad de ítem independiente del catálogo |
| Encabezado | `seccion` | `AACC`, `EDIFICIO`, `CRONOGRAMA_AACC` |
| OBS | `observacion_origen` | Conservar `AACC`, `Edif`, `(*)`; no confundir con estado |
| CONDOMINIO | `monto_origen_condominio` | Decimal con signo o null si no aplica |
| EDIFICIO 03 | `edificio_id`, `monto_origen_edificio` | Conservar valor fuente, separado del cálculo |
| UNITARIO | `monto_unitario_origen` | Referencia histórica; no sobrescribe fórmula |
| Suministro/teléfono/cotización | `referencia_servicio`, `referencia_documento` | Texto, preserva ceros y formato |
| Subtotales/total | `totales_declarados` | Comparar con `totales_calculados`; no son entradas al reparto |

Cada ítem incluye `categoria_codigo`, `tipo_movimiento` (`CARGO`/`ABONO`),
`monto_periodo` no negativo y `monto_distribuible_periodo`. El signo de origen se
normaliza mediante el tipo de movimiento, no se aplica dos veces. `ABONO` reduce
el reparto, no es pago individual ni saldo a favor. Ninguna cuota puede quedar
negativa; si sucede se bloquea aprobación y se exige resolver el destino del
excedente expresamente.

Financiamientos: `obligacion_referencia`, `numero_cuota`, `total_cuotas`,
`monto_total_obligacion`, `monto_periodo` y sustento. Validar 1 <= número <= total;
no cobrar el capital total otra vez ni inferir una sexta parte del importe
transcrito. Estar pendiente de pago al proveedor no determina si se cobra al
residente: son estados independientes.

## 4. Catálogo normalizado inicial

Los códigos son estables dentro del condominio. Los códigos antiguos son alias
de origen, no equivalencias globales: `TL01`, `PS01`, `ST01` y `PJ01` son ambiguos.
La misma partida puede aparecer cada mes o en distintos ámbitos sin duplicar el
concepto. El catálogo no se borra si ya fue utilizado.

| Código | Categoría | Concepto / referencia septiembre | Código origen |
|---|---|---|---|
| AGU-01 | SERVICIOS_BASICOS | Agua 6015099 | SA01 |
| AGU-02 | SERVICIOS_BASICOS | Agua 6015102 | SA02 |
| ELE-01 | SERVICIOS_BASICOS | Electricidad común 2433387 | SE01 |
| ELE-02 | SERVICIOS_BASICOS | Garita Conde de Lemos 2488660 | SE01 |
| ELE-03 | SERVICIOS_BASICOS | Garita Argentina 2488661 | SE01 |
| ELE-04 | SERVICIOS_BASICOS | Bomba de agua 2433401 | SE01 |
| ELE-05 | SERVICIOS_BASICOS | Bomba contra incendios 2433402 | SE01 |
| ELE-06 | SERVICIOS_BASICOS | Electricidad edificio 03, 2433391 | TE01 |
| TEL-01 | SERVICIOS_BASICOS | Telefonía fija común | ST01 |
| TEL-02 | SERVICIOS_BASICOS | Celular seguridad | ST01 |
| TEL-03 | SERVICIOS_BASICOS | Celular administración | TL01 |
| INT-01 | SERVICIOS_BASICOS | Internet administración | TL01 |
| SEG-01 | SEGURIDAD_Y_VIGILANCIA | Remuneraciones seguridad | PS01 |
| SEG-02 | SEGURIDAD_Y_VIGILANCIA | Liquidación seguridad, fracción 1/2 | ST01 |
| LIM-01 | LIMPIEZA_Y_JARDINERIA | Personal limpieza común y edificio (dos ítems) | PL01 / TL01 |
| LIM-02 | LIMPIEZA_Y_JARDINERIA | Insumos EDG-020219 | TL01 |
| JAR-01 | LIMPIEZA_Y_JARDINERIA | Mantenimiento jardines | PJ01 |
| MAN-01 | MANTENIMIENTO_PREVENTIVO | Ascensores JR Technology Buildings | TA01 |
| MAN-02 | MANTENIMIENTO_PREVENTIVO | Cronograma AACC y otros; exigir desglose para nuevas emisiones | PJ01 |
| ADM-01 | GASTOS_ADMINISTRATIVOS | Administrador y operaciones | TL01 |
| ADM-02 | GASTOS_ADMINISTRATIVOS | Hojas bond | TL01 |
| BAN-01 | GASTOS_ADMINISTRATIVOS | Comisiones + ITF + seguro, agrupación fuente | TL01 |
| COR-01 | IMPREVISTOS_Y_CONTINGENCIAS | Correctivo equipo biométrico | TL01 |
| COR-02 | IMPREVISTOS_Y_CONTINGENCIAS | Reparación fuga Bricer | TL01 |
| COR-03 | IMPREVISTOS_Y_CONTINGENCIAS | Detección fuga Bricer | TL01 |
| FIN-01 | OBLIGACIONES_FINANCIADAS | Agua marzo–abril, cuota 6/6 | TL01 |
| APO-01 | SERVICIOS_BASICOS | Abono electricidad SUM agosto | PS01 |
| APO-02 | SERVICIOS_BASICOS | Abono electricidad canchita agosto | PS01 |

`OBLIGACIONES_FINANCIADAS` es la única categoría nueva. Los dos aportes son abonos
al prorrateo; su naturaleza contable final requiere sustento, no se presume ingreso
de caja. El caso contiene 29 filas y 28 conceptos porque LIM-01 aparece dos veces.

## 5. Cobertura de gastos con moras cobradas

Unitario cero significa gasto financiado con moras, no ausencia de gasto. Cada
asignación de edificio distingue `monto_periodo`, `monto_cubierto_moras` y
`monto_distribuible_periodo = monto_periodo - monto_cubierto_moras` para cargos.
Puede haber cobertura parcial; nunca superar el importe del periodo. En abonos
no se admite cobertura con moras.

Mantener un registro de fondos por condominio/edificio/moneda: cobros de mora
conciliados, aplicaciones a ítems concretos y reversos. Mora devengada no cobrada
es cuenta por cobrar, **no fondo disponible**. Solo la parte del pago realmente
imputada a mora ingresa al fondo. No mezclar saldo a favor del residente.

`saldo_disponible = cobros_confirmados - aplicaciones_netas`. Cada aplicación
conserva importe, fuente, destino, actor, aprobación y motivo. Bloqueos e
idempotencia impiden gastar dos veces un saldo. No usar fondos de otra torre sin
transferencia expresamente aprobada y auditada. Una aplicación al gasto no es
un segundo egreso bancario: el pago al proveedor se registra una sola vez en caja.
Reversos de cobros ya utilizados exigen resolver la financiación sustituta dentro
de la misma operación; no producir saldo negativo silencioso.

## 6. Caso histórico septiembre 2026

Fuente inalterada: [transcripción](../../../prorrateo_mantenimiento_setiembre_2026.md).
Es evidencia histórica, no un presupuesto automáticamente aprobado. Las filas
COR-02 (3900.00) y COR-03 (1500.00) se explican como cubiertas con moras; para
reconstruir los movimientos se requieren saldos y documentos de respaldo. No
crear cobros ficticios para completar los **5400.00** de cobertura.

| Validación | Declarado | Suma de filas |
|---|---:|---:|
| AACC condominio | 66705.30 | 62705.30 |
| AACC edificio | 19479.07 | 19479.06 |
| AACC unitario | 140.14 | 140.13 |
| Gastos edificio | 23882.34 | 23782.34 |
| Gastos edificio unitario | 51.83 | 51.12 |

Los subtotales unitarios declarados suman **194.20**, no **194.19**. La bomba
de agua asigna 1488.85 al edificio frente a 1098.50 del condominio. FIN-01 muestra
13533.99 y unitario 16.23: no se deduce el importe del periodo sin cronograma.
Los pisos no reproducen exactamente las asignaciones antiguas. Se permite
conservar y consultar evidencia discrepante, pero no aprobar ni emitir desde
ella hasta conciliar valores y financiación. Toda corrección conserva el original.

## 7. Reporte mensual: llenado, consulta, PDF y DOCX

- Borrador por periodo: precargar conceptos recurrentes sin copiar pagos,
  comprobantes ni aplicaciones de moras del mes anterior; completar importes,
  referencias y sustentos, calcular, previsualizar, aprobar y exportar.
- Presupuesto y reporte comparten detalle aprobado: no mantener dos totales
  editables independientes. Aprobación valida padrón, fondos, sumas y permisos;
  congela versión, catálogo mostrado, pesos, importes y cierre de centavos.
- Mostrar secciones AACC, edificio y cronograma; código normalizado y original,
  descripción, OBS, condominio, edificio, unitario, cobertura de moras,
  distribuible, subtotales, total, vencimiento, unidades y anexo de ajustes.
- Adjuntar resumen de moras: saldo inicial disponible, cobros del periodo,
  aplicaciones, reversos, saldo final y mora pendiente de cobro separada.
- PDF y DOCX se generan desde la **misma versión** y plantilla con mismos
  importes, identificador de versión, fecha, estado y aprobación. Borradores
  llevan marca BORRADOR. Fallo de exportación no aprueba ni modifica el presupuesto.
- Reportes aprobados son inmutables; una corrección posterior es nueva versión
  vinculada y no altera cuotas emitidas sin ajuste contable explícito.
- La junta llena/aprueba; auditor consulta; residentes autorizados consultan la
  versión aprobada de su ámbito, sin exponer vouchers, teléfonos personales,
  datos bancarios ni deudas nominales de otros residentes en el reporte general.
- Editar el DOCX descargado no actualiza la versión oficial. Exportaciones son
  descargas privadas, no enlaces públicos; indicar error controlado si fallan.

## 8. Comprobantes visibles sin guardado manual

Visor integrado de imágenes PNG/JPEG (ampliar/rotar) y PDF (páginas/zoom), con
descarga como acción independiente. El archivo se transfiere al navegador; no
se promete impedir caché local, capturas ni copias del usuario autorizado.

Reutilizar GET privado de voucher, con `disposicion=inline|attachment` (default
`attachment` para compatibilidad) y `evidencia_id` opcional para una revisión
histórica autorizada. Validar pertenencia al comprobante y permiso actual en cada
lectura; nunca aceptar ruta/URL arbitraria ni publicar uploads como estáticos.
Tipo MIME comprobado, `Content-Disposition` seguro, `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`; no incrustar formatos activos no admitidos.
El visor usa autenticación existente sin poner JWT en la URL, muestra errores de
archivo ausente/sesión expirada, permite teclado y tiene alternativa de descarga.
Las capturas de egresos se sujetan al mismo control privado con permisos de
tesorería/auditoría; no reutilizar el acceso del residente a su pago para verlas.

## 9. Auditoría y aceptación

Política, excepciones, aprobación, devengos, ajustes y aplicaciones de fondos
usan auditoría inmutable de siete campos, estados anterior/posterior, actor y
motivo. Operaciones financieras y outbox se confirman transaccionalmente.
Mantener la convención canónica actual de `departamento_id = NULL` para eventos
generales del condominio; no introducir un ID ficticio incompatible con FK.

Criterios: [aceptación documental](../../04-acceptance-criteria/prorrateo-mora-reportes.feature.md).
Contrato objetivo: [API y persistencia](../../05-api/prorrateo-mora-reportes.md).
