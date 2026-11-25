# Dominio 06: Egresos, proveedores y contratos

## 1. Ficha

- **Identificador:** DOM-06 / PROC-06
- **Responsables:** Tesorería / Junta Directiva
- **Estado:** CON-51 parcialmente implementado; CON-52 pendiente
- **Versión:** 2.2
- **Módulo de egresos:** `src/modules/egresos/`
- **Proceso normativo:** [PROC-06](../../02-processes-and-automations/proc-06-egresos-y-proveedores.md)
- **Contrato de integración CON-48/49/51/52:** [documento de coordinación](../../../docs/sprints/CON-48-49-51-52-integracion.md)

Este dominio separa siete hechos: ingreso conciliado de residente, comprobante
presentado por residente, concepto/periodo presupuestal, egreso administrativo,
aprobación del egreso, pago real a proveedor y movimientos del fondo de moras.
No son estados ni registros intercambiables.

Las capacidades de conceptos presupuestales y fondos de mora (0018–0020) están
implementadas prospectivamente. Su existencia no significa que CON-51/52, la caja
bancaria de proveedores, ni el pago al proveedor estén implementados.

## 2. Relaciones y contrato con proveedores

- El egreso pertenece a un `condominio_id` y requiere un `concepto_id` existente
  de `ConceptoPresupuestal` del mismo condominio. No hay catálogo de categorías
  duplicado.
- `proveedor_id` es UUID nullable. Si se envía, el proveedor debe existir y
  pertenecer al mismo condominio. El egreso conserva la relación, no copia campos
  editables de razón social/RUC.
- `contrato_id` es UUID nullable. Si se envía, el contrato debe pertenecer al
  mismo condominio y al proveedor indicado. No se exige contrato universalmente.
- Para evitar dependencia de CON-48/49 durante el desarrollo, el módulo puede
  implementar inicialmente los campos UUID y las validaciones de servicio sin FK
  física a tablas aún no integradas. No se crean tablas placeholder. Tras integrar
  el esquema real de proveedor/contrato, una migración posterior añade las FKs y
  valida los datos previos. No se crea una cabeza Alembic paralela.
- La API de proveedores deberá exponer `id`, `condominio_id`, `ruc`,
  `razon_social` y `activo` para el selector y detalle de egreso.

La relación opcional a presupuesto se expresa mediante el presupuesto/periodo e
ítem presupuestal acordados, sin editar el snapshot aprobado ni implicar pago.
Si el concepto no corresponde a un ítem concreto, el egreso conserva `concepto_id`
sin forzar una asociación artificial.

## 3. Registro de egreso (CON-51)

El egreso contiene UUID, condominio, concepto, proveedor/contrato opcionales,
descripción y justificación, moneda, fecha del gasto, importe solicitado y, cuando
corresponda, importe pactado. La categoría se deriva del concepto presupuestal.
La evidencia de sustento se registra como documento privado asociado al egreso.
Actor, timestamps y versión son generados/controlados por servidor.

El alta crea `BORRADOR`; no registra pago, no altera caja y no modifica el
presupuesto. Para presentar, debe haber al menos un sustento y política de
aprobación configurada. Cambios editables incrementan la versión; importes como
cadenas Decimal con dos posiciones, `NUMERIC(12,2)` y nunca `float`.

## 4. Política de aprobación (CON-52)

- Registrador no puede aprobar su propio egreso.
- El umbral se configura por condominio. No existe valor numérico predeterminado.
- Un importe hasta el umbral necesita una aprobación de actor distinto del
  registrador. Un importe superior requiere una aprobación adicional de otro
  actor distinto. Ningún mismo usuario satisface dos aprobaciones.
- Un cambio del importe incrementa la versión y deja sin vigencia las
  aprobaciones anteriores para la decisión actual; no elimina su historial.
- Roles existentes: `ADMIN_JUNTA` y `SUPERADMIN` podrán ejecutar operaciones
  administrativas dentro de las reglas contextuales existentes. `AUDITOR` es
  estrictamente lectura. No se crean roles nuevos en esta historia.
- Configuración faltante bloquea presentación/decisión, pero no alta de borrador,
  consulta o edición permitida. Cambios de política quedan auditados y versionados.
- La asignación de qué rol existente puede administrar el umbral y quién puede
  iniciar una apertura de caja se ratificará con Tesorería; mientras tanto, no se
  permite operar esas acciones por privilegio implícito.

## 5. Pago y caja

Aprobar no significa pagar. Tesorería ejecuta la transferencia fuera del sistema y
después registra el pago real con cuenta, fecha bancaria, importe, referencia y
evidencia. La fecha/actor de confirmación del sistema se conservan por separado.

El diseño admite varios pagos y pagos parciales, pero `pagos_parciales_habilitados`
inicia en `false`. Deshabilitado: el pago debe cubrir todo el saldo aprobado aún
pendiente. Habilitado por configuración ratificada: la suma de pagos confirmados
no puede exceder el importe aprobado. No se admiten pagos sin aprobación vigente.

No se confirma pago hasta que la cuenta tenga una apertura conciliada. No se
fabrica saldo, no se infiere de cuotas emitidas/pendientes, ni se reutiliza el
ledger `movimientos_fondo_moras`. La caja de proveedores tiene cuentas/saldos por
condominio y moneda según el modelo de Tesorería; su saldo es la suma de un ledger
independiente e inmutable. Una apertura requiere saldo, fecha de corte, actor y
sustento conciliado. No hay monto inicial por defecto.

Clave `Idempotency-Key` identifica cada confirmación. Pago, movimiento de caja y
auditoría se insertan en una transacción. El reverso exige motivo y referencia al
pago original, y se representa mediante movimiento compensatorio; no se edita ni
elimina el pago original. Una operación bancaria fallida no genera salida de caja.
El saldo pagado neto se calcula con pagos confirmados menos importes reversados;
un reverso restaura saldo pendiente dentro del mismo monto aprobado y recalcula el
egreso a `APROBADO`, `PAGO_PARCIAL` o `PAGADO` según el neto restante.

## 6. Máquina de estados

### Egreso

```text
BORRADOR --presentar--> PENDIENTE_APROBACION
PENDIENTE_APROBACION --aprobaciones requeridas satisfechas--> APROBADO
PENDIENTE_APROBACION --rechazo con motivo--> RECHAZADO
RECHAZADO --corregir/nueva versión--> BORRADOR
APROBADO --pago menor que saldo (solo si parciales habilitados)--> PAGO_PARCIAL
APROBADO/PAGO_PARCIAL --saldo pagado--> PAGADO
BORRADOR/PENDIENTE_APROBACION/APROBADO --cancelación autorizada sin pagos--> CANCELADO
```

Editar un importe antes de presentar mantiene BORRADOR y suma versión. Un cambio
aprobable después de presentación requiere retorno controlado a BORRADOR, invalida
las aprobaciones activas y crea nueva presentación. Un pago confirmado impide
cancelación ordinaria; su corrección usa reverso compensatorio.

### Pago

`CONFIRMADO` representa una salida confirmada. `FALLIDO` conserva evidencia del
intento sin movimiento de caja. `REVERSADO` indica que existe movimiento
compensatorio; el hecho original permanece. Las transiciones y actores se conservan
en historial inmutable.

## 7. Auditoría, concurrencia y errores

Cada alta, cambio, presentación, aprobación, rechazo, configuración, apertura,
confirmación y reverso registra los siete campos de `AuditoriaPayload`, actor y
contexto de condominio. Se aplican locks deterministas y control de versión en
PostgreSQL; dos aprobaciones/pagos concurrentes no pueden duplicar transiciones o
saldo. Estado, ledger y auditoría son atómicos.

Conflictos financieros devuelven 409: `EGRESO_VERSION_OBSOLETA`,
`EGRESO_ESTADO_INVALIDO`, `APROBACION_DUPLICADA`, `APROBACION_CONFIGURACION_REQUERIDA`,
`APROBACION_INSUFICIENTE`, `IDEMPOTENCIA_CONFLICTO`, `CAJA_NO_CONFIGURADA`,
`CAJA_SALDO_INSUFICIENTE`, `PAGO_EXCEDE_APROBADO` o `PAGO_YA_REVERSADO`.
Pertenencia ajena se responde sin revelar datos (404 contextual según política).

## 8. Documentos y API

Documentos de egreso y de pago son privados, con contenido validado, límite
configurado, identificadores generados por servidor y acceso contextual Junta/
Auditor. Residentes no tienen acceso. Se conservan versiones y hash; no se exponen
URLs públicas ni rutas internas.

Rutas canónicas, esquemas y errores: [contrato API](../../05-api/api-contracts.md#con-51-y-con-52-egresos-aprobaciones-pagos-y-caja)
y [OpenAPI](../../03-contracts/openapi/egresos.paths.yaml). La especificación
describe el objetivo; no acredita implementación.
