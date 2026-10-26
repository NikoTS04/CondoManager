# Contrato objetivo: prorrateo, mora diaria, reportes y evidencia

Estado: **flujo prospectivo implementado (0016–0020)**. Base `/api/v1`, Bearer Token,
aislamiento por condominio, `Decimal`/`NUMERIC(12,2)` y dinero JSON como cadenas.
Reglas normativas: [dominio](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
Los ejemplos de contratos anteriores no autorizan reescribir datos históricos.

### Avance de implementación — quinta entrega (0020)

Fondos por edificio/moneda integrados con conciliación legacy y diaria, reservas,
liberación, confirmación al aprobar, interfaz administrativa y reporte PDF/DOCX.
Solo el componente MORA realmente conciliado ingresa al fondo. No se transfieren
fondos entre edificios ni se confunde principal, saldo a favor o mora devengada
con caja. Cobros, movimientos y sus compensaciones son inmutables; aplicaciones
solo transitan RESERVADA → CONFIRMADA/LIBERADA. Todos los cambios son auditados y
emiten FondosMorasActualizadosEvent v1, reconocido como evento interno sin enviar
información de tesorería a residentes.

POST de aplicaciones exige versión y clave idempotente. Reserva/liberación
recalcula el neto del borrador e incrementa versión. Al aprobar se confirma sin
otro descuento y se congela el resumen del fondo. PUT conserva los importes
cubiertos registrados, no permite omitir ítems con reservas. Cobertura cero y
presupuestos históricos sin detalle mantienen compatibilidad; PDF/DOCX anteriores
sin datos de fondos siguen exportándose.

GET del fondo reconoce caja en el periodo local de confirmación, no cambia la
fecha bancaria del pago. Incluye disponible inicial/final, cobros netos, reservas,
liberaciones, disponible/reservado actual, aplicado y mora pendiente separada.
El reporte aprobado conserva solo ese resumen agregado, sin movimientos privados.
Una corrección que dejaría disponibilidad negativa responde 409
FONDOS_MORAS_COMPROMETIDOS y revierte pagos, cuotas, crédito, caja, auditoría y
outbox. Puede resolverse liberando reservas o con nuevos cobros reales antes de
reintentar; no existe un botón para inventar financiación.

Adopción prospectiva: cada comprobante/cuota fija su edificio, moneda y base de
mora previamente cobrada no adoptada. Esa base no se importa como caja ni genera
reversos de efectivo inexistente. Septiembre y sus 5400.00 requieren documentación
y conciliación antes de una adopción histórica explícita. No se implementa aquí
edición de cuotas/presupuestos aprobados, exoneraciones manuales, transferencias
entre fondos ni pagos a proveedores. La migración 0020 no se ha aplicado a la
base de la aplicación.

### Avance de implementación — cuarta entrega (0019)

Motor diario persistente y conciliación de pagos nuevos por fecha bancaria
implementados. Se retira el bloqueo `MOTOR_DIARIO_PENDIENTE` de nuevas emisiones.
El worker de pagos recupera fechas omitidas al arrancar y a las 00:05 de Lima.
Cada cuota con snapshot diario devenga desde la mayor de emisión y primer día
posterior a gracia; el día bancario del pago tardío es inclusivo, sin capitalizar.
Se reconstruyen pagos nuevos por `(fecha_operacion, id)` y se compensan devengos e
imputaciones sin borrar los originales. Los pagos/CON-13 previos son base fija.
`conciliaciones_diarias` fija qué cuotas existían al aprobar cada pago, evitando
reutilizar excedentes ya aplicados a cuotas emitidas después, incluso el mismo día.

La pausa provisional toma el reporte EN_REVISION más antiguo y dura 24 h desde
su creación; reintentos, nuevos reportes o subsanaciones no renuevan esa pausa.
Aprobar, observar o rechazar regulariza los días sin esa pausa. Una fecha bancaria
futura responde 422 `FECHA_BANCARIA_FUTURA`; un déficit de crédito utilizado,
409 `CREDITO_RETROACTIVO_CONSUMIDO`. No se aplica parcialmente la operación.
Recibos/revisiones originales permanecen históricos. Las imputaciones vigentes
son la suma firmada del ledger por componente, no SUM de recibos originales.
Nuevos cargos/compensaciones publican eventos v2, con relay y consumidor compatibles.

Migración aditiva 0019, sin reconstruir políticas ni pagos históricos. No aplicada
a la base de la aplicación. Los fondos que quedaron pendientes en esta entrega
se integran en 0020; los ajustes manuales de cuotas aprobadas no están incluidos.

### Avance de implementación — primera entrega

Estado histórico de esa entrega; la cuarta entrega sustituye su bloqueo diario.

Implementados en la rama de trabajo: alta/configuración de MONTO_DIARIO, edición
versionada y auditada de política, defaults 10/0/1.00, visor privado PNG/JPEG/PDF,
consulta de revisiones históricas y descarga compatible. Migración 0016 aditiva:
congela en cuotas existentes la gracia efectiva al adoptar (no se presume que sea
la regla original), y nuevas emisiones anteriores guardan su gracia efectiva.
**El motor diario aún no está integrado**: emitir bajo MONTO_DIARIO devuelve
409 `MOTOR_DIARIO_PENDIENTE` para no producir cuotas sin política/devengo completos.
No confundir configuración preparada con recaudación automatizada operativa.
Pendientes: excepciones individuales, snapshots completos, devengos persistentes,
conciliación por fecha bancaria, prorrateo/fondos y exportaciones PDF/DOCX.

### Avance de implementación — segunda entrega

Estado histórico; consultar arriba el avance de la cuarta entrega.

Condiciones individuales y snapshots completos de nuevas emisiones implementados.
La migración 0017 agrega override nullable al vínculo, responsable único por
departamento, control de versión y JSON de política por cuota. No rellena
snapshots de cuotas antiguas con políticas supuestas. La consulta de solvencia
usa fecha local de Lima en los portales y el guard de reservas; la fecha bancaria
para reconstruir imputaciones sigue pendiente. El motor diario y su bloqueo de
emisión permanecen pendientes, al igual que prorrateo/fondos y exportaciones.
La interfaz de vínculos permite designar/retirar responsable y configurar gracia.
Verificación: suite completa ejecutada en PostgreSQL temporal, más escenarios de
concurrencia y emisión con override. El reparador legacy está ligado a su head
anterior y continúa rechazando el head financiero; no usarlo para adoptar 0017.

## 1. Política financiera y excepciones

La segunda entrega define `GET/PUT /departamentos/{id}/condiciones-pago` para
Junta/SuperAdmin; auditor puede consultar. PUT exige `version_esperada` positiva,
motivo no vacío, vínculo responsable nullable y override nullable 0..30 (sin
responsable, override debe ser null). GET devuelve `version`, responsable
designado, override y `dias_gracia_efectivos`; una designación cuyo vínculo ya no
está activo no aporta gracia. La selección no modifica permisos ni saldos.
Versiones obsoletas responden 409, incluso si el payload coincide.
La revocación de un vínculo elimina su designación como responsable; restaurarlo
no restaura automáticamente privilegios financieros. La emisión conserva
modalidad, importes, versión global, gracia efectiva, responsable y zona Lima.
Para cuotas antiguas, solo se fotografía la gracia de adopción de 0016; no se
fabrican modalidad, importes ni responsables históricos.

Extender alta/consulta de condominio con `MONTO_DIARIO` y `monto_mora_diario`.
Defaults al omitir configuración nueva: día 10, gracia 0, modalidad MONTO_DIARIO
y monto 1.00 para PEN. Campos de otras modalidades nulos; moneda distinta de PEN
exige importe diario explícito. Mantener MONTO_FIJO/PORCENTAJE_SALDO existentes.

`PUT /condominios/{id}/politica-mora`: reemplaza configuración para emisiones
futuras. Solo SuperAdmin/Junta del contexto. Actor y fecha asignados por servidor.

```json
{
  "regla_mora_tipo": "MONTO_DIARIO",
  "monto_mora_diario": "1.00",
  "dia_vencimiento": 10,
  "dias_gracia": 0,
  "motivo": "Política aprobada por la junta"
}
```

`PUT /departamentos/{id}/condiciones-pago`: designa un vínculo activo propietario/
inquilino responsable y su gracia. No acepta usuarios de otra unidad/condominio.
`vinculo_responsable_id: null` elimina designación y hereda globalmente. Exige
motivo, auditoría y unicidad transaccional del responsable. No altera roles/RBAC.

```json
{
  "vinculo_responsable_id": "7b8a1c9e-1234-4567-89ab-cdef01234567",
  "dias_gracia_override": null,
  "motivo": "Responsable vigente de pago"
}
```

Respuestas 200 con configuración efectiva, actor y fecha; 401/403/404 por
identidad/ámbito/ausencia; 422 por importes no finitos, escala, modalidad o vínculo
inválidos; 409 por conflicto de versión. Repetir el mismo cambio es no-op.
Control de versión requerido para no perder cambios concurrentes.

La edición usa `version_esperada` (entero positivo); la respuesta del condominio
incluye `politica_version`. Coincidencia de versión y datos idénticos no crea
auditoría ni incrementa versión. Una versión obsoleta responde 409.
Para consultar evidencia histórica se usa `evidencia_id` de revisión y
`GET /pagos/{comprobante_id}/evidencias` devuelve solo id, tipo y fecha, nunca
notas internas ni nombres de almacenamiento. La versión vigente puede consultarse
sin identificador, incluso para comprobantes anteriores al registro de revisiones.

## 2. Presupuesto detallado y reporte

Implementado en la tercera entrega (0018): catálogo, ítems, reparto, snapshot,
emisión, previsualización y PDF/DOCX. El catálogo se llena explícitamente; no se
importó ni aprobó automáticamente septiembre. Las asignaciones explícitas y
valores de origen se admiten por API; la interfaz facilita los repartos por
pisos y directo, sin un editor avanzado de asignaciones manuales.
La cobertura con fondos se integra en la quinta entrega y motor diario/fecha
bancaria en la cuarta. La revisión posterior de aprobados no está incluida.

### Contrato de la tercera entrega

POST/PUT admiten `items` y `version_esperada`. Sin items se conserva el contrato
legacy (total positivo obligatorio). Con items, el servidor calcula el total;
un total de control enviado debe coincidir. Se admite total cero, nunca cuotas
negativas. PUT de un presupuesto detallado y su aprobación exigen la versión
vigente; aprobación usa query `version_esperada`. No se permite convertir
silenciosamente un presupuesto detallado en uno legacy omitiendo sus ítems.

Cada ítem conserva UUID, `concepto_id`, sección, importe del periodo, cargo/abono,
referencias y método POR_PISOS / DIRECTO_EDIFICIO / ASIGNACION_EXPLICITA. El último
requiere importes por edificio, motivo y documento. El método unitario es
EQUITATIVA (default) o POR_ALICUOTA, normalizado dentro de cada edificio. El padrón
aprobado debe coincidir con el activo al emitir; si cambió se rechaza la emisión,
no se redistribuyen importes históricos. No se confunde este método jerárquico
con una tercera modalidad global de alícuotas: el lote usa `JERARQUICA`.

El catálogo persistido se consulta/crea con GET/POST
`/condominios/{id}/conceptos-presupuestales`. Código estable único por condominio,
categoría, descripción y estado activo. Auditor solo consulta. Ítems solo admiten
conceptos activos del mismo condominio. La cobertura con moras debe coincidir
con aplicaciones vigentes del fondo conciliado, nunca con un número libre.

Persistencia mínima: catálogo relacional; ítems ordenados JSONB en el presupuesto,
snapshot JSONB congelado al aprobar y detalle JSONB por cuota. Reemplaza las tablas
separadas de ítems/asignaciones propuestas inicialmente: el agregado mensual se
guarda transaccionalmente, su versión y auditoría conservan el historial sin
mantener dos representaciones editables del mismo detalle. No se generan nuevos
versionados de un presupuesto aprobado en esta entrega; correcciones posteriores
requieren el proceso de ajuste todavía pendiente.

GET `/presupuestos/{id}/prorrateo` permite previsualizar el borrador con datos
actuales o consultar el snapshot aprobado, filtrando `edificio_id`. Residente
solo consulta versión aprobada y edificio al que está vinculado actualmente;
sin anexo individual de otros departamentos. PDF/DOCX se exportan desde
el mismo reporte autorizado, no desde otro presupuesto paralelo.

La exportación implementada usa `version` explícita positiva, `formato=pdf|docx`
y `edificio_id` opcional para administración (obligatorio para residente). La
versión se comprueba al capturar los datos autorizados; una diferencia responde
409. Generación en memoria con ReportLab/python-docx, sin archivos públicos.
Exportación fallida responde 503 sin modificar el presupuesto ni emitir cuotas.
Las descripciones públicas deben evitar datos personales: el residente recibe
solo el subconjunto público del reporte de su propio edificio.

Extender POST/PUT de presupuestos con `items`. El borrador conserva UUID de ítems;
no se identifican por código origen. Cada ítem contiene campos del dominio,
método de asignación, referencias y, si corresponde, cronograma de financiación.
PUT requiere versión vigente y reemplaza el borrador completo; un presupuesto
aprobado sigue respondiendo 409. GET devuelve detalle y diferencias detectadas.
`monto_total` pasa a ser el total distribuible calculado por servidor; si el
cliente lo informa como control debe coincidir exactamente. `fecha_vencimiento`
es el día 10 para el piloto; la emisión continúa recibiendo solo condominio y
periodo. No aceptar montos sustitutivos desde la emisión.

Para presupuestos históricos sin ítems se mantiene lectura/emisión bajo su
contrato anterior. Una nueva emisión detallada valida y consume el desglose,
sin cambiar la unicidad del lote condominio/periodo ni cuota departamento/periodo.
La ampliación del request está publicada en OpenAPI 2.2.0; la interfaz de Junta
admite ítems y versión sin exigir cambios a clientes legacy sin detalle.

Ejemplo de cobertura calculada desde una aplicación confirmada (no entrada libre):

```json
{
  "concepto_codigo": "COR-02",
  "tipo_movimiento": "CARGO",
  "metodo_asignacion": "DIRECTO_EDIFICIO",
  "monto_periodo": "3900.00",
  "monto_cubierto_moras": "3900.00",
  "monto_distribuible_periodo": "0.00"
}
```

La cobertura no se crea enviando un número: debe referenciar aplicaciones reales
del fondo, bloqueadas y verificadas al aprobar. Aplicaciones de un borrador son
reservas de fondos que reducen disponibilidad para otros borradores; eliminarlas
o anular el borrador libera la reserva. Aprobación confirma la aplicación sin
descontar de nuevo. No incluir una cobertura sin fondos en una versión aprobada.

### Operaciones de fondos y reporte

| Método/ruta | Resultado | Permiso/regla |
|---|---|---|
| `GET /presupuestos/{id}/prorrateo?edificio_id=...` | 200, JSON de previsualización por edificio | Junta/auditor; residente solo versión aprobada de su ámbito |
| `GET /presupuestos/{id}/prorrateo/exportar?edificio_id=...&version=...&formato=pdf` | 200, archivo privado | Mismos permisos; formato `pdf` o `docx` |
| `GET /edificios/{id}/fondos-moras?periodo=YYYY-MM` | 200, movimientos, saldo disponible y reservado | Junta/auditor del contexto |
| `POST /presupuestos/{id}/aplicaciones-moras` | 201, reserva vinculada a ítem/edificio/importe/motivo | Junta, borrador; clave de idempotencia obligatoria |
| `GET /presupuestos/{id}/aplicaciones-moras` | 200, aplicaciones y estados, incluidas liberadas | Junta/auditor del contexto |
| `DELETE /presupuestos/{id}/aplicaciones-moras/{aplicacion_id}` | 204, libera reserva no confirmada | Junta, solo borrador; auditar, no borrar historial |

Aplicaciones confirmadas solo admiten compensación auditada con motivo y
financiación sustituta; no DELETE. Idempotency-Key repetida con el mismo payload
devuelve la misma aplicación; distinto payload responde 409.

Exportar exige versión explícita: nunca descargar silenciosamente otra versión
si cambió el borrador. Aprobados conservan snapshot; corrección crea una revisión
vinculada, no un segundo lote mensual. 409 por versión obsoleta, fondos
insuficientes o descuadre; 422 por formato/periodo/estructura inválidos; 503 si
no se puede generar el archivo. No modificar importes al exportar.

PDF: `application/pdf`. DOCX:
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
`Content-Disposition: attachment`, nombre saneado con periodo/edificio/versión,
`Cache-Control: no-store`. El JSON entrega totales declarados/calculados,
cobertura, padrón y ajustes sin rutas internas ni evidencia privada incrustada.

## 3. Evidencia inline

Extender `GET /pagos/{comprobante_id}/voucher` con:
- `disposicion`: `inline` o `attachment` (default `attachment`).
- `evidencia_id`: UUID opcional; omitir selecciona evidencia vigente.

200 con bytes PNG/JPEG/PDF, MIME real validado, Content-Disposition conforme a
parámetro, no-store y nosniff. Mismos permisos para inline y descarga, incluso
evidencia histórica. La evidencia debe pertenecer al comprobante autorizado;
ausencia o referencia ajena no revela rutas ni nombres. Archivo ausente: error
controlado. No tokens en URL ni rutas arbitrarias. Consulta no muta finanzas.
El historial consultable entrega identificadores autorizados, no URLs públicas.
La evidencia de egresos requiere un contrato privado equivalente, limitado a
tesorería/auditoría; no se expone con el endpoint de pagos de residentes.

## 4. Persistencia objetivo (no migración)

Decisión implementada en 0018: `conceptos_presupuestales` relacional;
`presupuestos_mensuales.items`, `prorrateo_snapshot` y `cuotas_mantenimiento.detalle_prorrateo`
JSONB; `presupuestos_mensuales.version` entero positivo. Las entidades separadas
de ítems/asignaciones/detalles/versiones en la tabla de diseño inicial siguiente
quedan sustituidas por este agregado auditado; fondos y devengos siguen como
diseño pendiente. La entrega 0019 implementa `devengos_mora` (único cuota/fecha),
`ajustes_devengo_mora` (compensaciones firmadas), `conciliaciones_diarias` (padrón
original por comprobante), `movimientos_imputacion_diaria` (componentes firmados)
y `eventos_mora_outbox`. Las cuatro primeras impiden UPDATE/DELETE por trigger.
El downgrade de 0019 rechaza operaciones o cuotas diarias existentes.
0020 crea `cobros_mora_fondo` (origen y base no adoptada),
`movimientos_fondo_moras` (importes firmados con origen único),
`aplicaciones_fondo_moras` (clave por presupuesto y transición protegida) y
`eventos_fondo_moras_outbox`. Su downgrade rechaza cobros o aplicaciones.

| Entidad | Adición / restricción |
|---|---|
| `condominios` | `monto_mora_diario NUMERIC(12,2)`, positivo para MONTO_DIARIO; otras modalidades null; defaults día 10/gracia 0 |
| `usuario_departamentos` | `dias_gracia_override SMALLINT NULL` 0..30; responsable único activo por unidad, designación explícita |
| `cuotas_mantenimiento` | Snapshot de modalidad, monto diario, gracia, responsable y zona; no sustituir por config actual |
| `conceptos_presupuestales` | UUID, condominio, código estable único por condominio, categoría, descripción, activo |
| `presupuesto_items` | UUID, presupuesto, concepto, sección, código/valores origen, tipo movimiento, importe periodo, referencias y financiación |
| `asignaciones_prorrateo` | Ítem, edificio, método, peso numerador/denominador, importes calculados; unicidad ítem/edificio |
| `detalle_cuota_items` | Cuota, ítem, importe con signo, ajuste; snapshot de participantes; suma cierra cuota |
| `devengos_mora` | UUID, cuota, fecha local, importe y política; UNIQUE(cuota_id, fecha_local); reversos referencian cargo |
| `movimientos_fondo_moras` | Edificio/condominio/moneda, tipo, importe positivo, referencia a imputación/ítem, idempotencia, actor, motivo; sin sobregiro |
| `versiones_prorrateo` | Presupuesto, revisión única, estado, detalle/padrón/conceptos congelados, aprobador/fecha; inmutable al aprobar |

Importes no float; cadenas con dos posiciones en API. El DDL base permanece
como referencia de integración existente: esta tabla describe la extensión
futura, no autoriza ejecutar SQL de adopción ni inventa números de migración.

## 5. Eventos y transacciones

Mantener envelopes/outbox e identificadores estables; consumidores deduplican.
`MoraAplicadaEvent` se identifica por cuota y fecha local. Ajustes y aplicaciones
de fondos deben producir eventos versionados nuevos, nunca cambiar payloads
históricos ya publicados. El resumen de cuotas conserva total **distribuible**;
detalle de fondos se consulta por referencia, no se incrustan vouchers en eventos.
Actualizar JSON Schemas solo al cerrar la futura integración de productores y
consumidores; no presentar nuevos payloads como compatibles sin versionado.
