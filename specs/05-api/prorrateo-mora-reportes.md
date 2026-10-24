# Contrato objetivo: prorrateo, mora diaria, reportes y evidencia

Estado: **especificado, no implementado**. Base `/api/v1`, Bearer Token,
aislamiento por condominio, `Decimal`/`NUMERIC(12,2)` y dinero JSON como cadenas.
Reglas normativas: [dominio](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
Los ejemplos de contratos anteriores no autorizan reescribir datos históricos.

## 1. Política financiera y excepciones

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

## 2. Presupuesto detallado y reporte

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
El cambio de request debe versionarse explícitamente en la futura implementación;
no afirmar que clientes actuales ya soportan esta estructura.

Ejemplo de asignación calculada (no entrada de totales):

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

### Operaciones objetivo

| Método/ruta | Resultado | Permiso/regla |
|---|---|---|
| `GET /presupuestos/{id}/prorrateo?edificio_id=...` | 200, JSON de previsualización por edificio | Junta/auditor; residente solo versión aprobada de su ámbito |
| `GET /presupuestos/{id}/prorrateo/exportar?edificio_id=...&version=...&formato=pdf` | 200, archivo privado | Mismos permisos; formato `pdf` o `docx` |
| `GET /edificios/{id}/fondos-moras?periodo=YYYY-MM` | 200, movimientos, saldo disponible y reservado | Junta/auditor del contexto |
| `POST /presupuestos/{id}/aplicaciones-moras` | 201, reserva vinculada a ítem/edificio/importe/motivo | Junta, borrador; clave de idempotencia obligatoria |
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
