# PROC-06: Control de Egresos, Proveedores y Repositorio de Contratos

## 1. Ficha del Proceso
- **Identificador:** PROC-06
- **Responsable del Módulo:** **Tesorería / Administración**
- **Estado:** Contrato CON-51/52 definido; CON-51 parcial, CON-52 pendiente
- **Versión:** 1.2
- **Módulos Vinculados:** PROC-03 (Notificaciones), PROC-08 (Reportes)

---

## 2. Propósito y Alcance del Proceso
Centralizar el registro clasificado de todas las salidas de dinero del condominio (servicios básicos, empresas de seguridad, limpieza, mantenimiento preventivo de ascensores y bombas), administrar el directorio único de contratistas y custodiar digitalmente los contratos con alertas preventivas de vencimiento y renovación.

---

## 3. Disparadores y Eventos de Entrada
1. **Registro de Factura / Orden de Pago:** La administración carga una factura electrónica de un proveedor vinculada a un contrato vigente.
2. **Cron Diario de Vencimiento de Contratos:** Disparado diariamente a las 01:00 UTC para verificar contratos próximos a expirar en 30 o 60 días.
3. **Ejecución de Pago a Proveedor:** Egreso de fondos desde la cuenta bancaria del condominio respaldado con constancia de transferencia.

---

## 4. Reglas de Negocio

### 4.1 Categorización Estructurada de Gastos
Catálogo normalizado, correspondencia de las 29 filas de septiembre y reglas de
cobertura: [prorrateo y fondos de mora](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
Los códigos originales se conservan como evidencia, nunca como identificador único.

Todo egreso debe imputarse obligatoriamente a una categoría presupuestal predefinida:
- `SERVICIOS_BASICOS`: Agua común (Sedapal), Electricidad común (Luz del Sur/Enel).
- `MANTENIMIENTO_PREVENTIVO`: Ascensores (Otis, Schindler, etc.), Bombas de agua hidroneumáticas, Puertas levadizas.
- `SEGURIDAD_Y_VIGILANCIA`: Empresa de conserjería / vigilancia 24/7.
- `LIMPIEZA_Y_JARDINERIA`: Insumos y servicio de aseo.
- `GASTOS_ADMINISTRATIVOS`: Comisiones bancarias, software, asesoría contable o legal.
- `IMPREVISTOS_Y_CONTINGENCIAS`: Reparaciones extraordinarias por fallas súbitas.
- `OBLIGACIONES_FINANCIADAS`: Cuotas de financiamientos, con capital total,
  número/total de cuotas, importe del periodo y sustento; no cobrar dos veces capital.

### 4.1.1 Cobertura con moras cobradas

Entrega 0020: ledger por edificio/moneda con cobros conciliados posteriores a la
adopción, reservas para ítems y liberaciones. No se importa caja histórica ni se
considera disponible el principal, crédito del residente o mora sin cobrar.
Los cobros diarios conservan una base no adoptada por comprobante/cuota para no
fabricar fondos a partir del ledger anterior. La atribución al edificio/moneda
del cobro queda fija; un retroactivo compensa en ese mismo fondo.

La reserva exige borrador detallado, versión vigente, Idempotency-Key y motivo.
Reduce disponibilidad al instante; aprobación confirma sin descontar otra vez.
Retirar cobertura solo libera reservas, nunca aplicaciones confirmadas. PUT del
borrador no puede omitir ítems cubiertos ni alterar su cobertura arbitrariamente.
Una corrección bancaria que dejaría disponibilidad negativa responde 409
FONDOS_MORAS_COMPROMETIDOS y revierte toda la conciliación. Nuevos cobros reales
o liberar otras reservas pueden resolver la insuficiencia; no hay ingreso manual
sin sustento, transferencias entre edificios ni edición de cuotas emitidas.

Saldo disponible = cobros netos - reservas vigentes - aplicaciones confirmadas.
La reserva y liberación recalculan el neto del presupuesto, incrementan versión y
auditan. Se resta cobertura después del reparto bruto entre edificios y antes
del reparto unitario; no se traslada el beneficio a otra torre. Reportes guardan
bruto/cobertura/distribuible y resumen de fondos capturado al aprobar.
Fecha de reconocimiento de caja: confirmación local Lima; fecha bancaria del
comprobante se conserva separada. El pago a proveedor sigue siendo otro hecho.

Registrar por edificio y moneda moras cobradas, aplicaciones parciales/totales a
gastos y saldo disponible. Solo pagos conciliados e imputados a mora financian
gastos; moras devengadas no constituyen caja. Unitario cero conserva gasto y
movimiento de cobertura. Bloquear sobregiros, doble aplicación y cruces de fondos
entre edificios no autorizados. Aplicación al gasto y pago al proveedor son hechos
distintos: no duplicar egreso. Comprobantes privados consultables en visor por
tesorería/auditoría, no por residentes ajenos; conservar versiones históricas.

### 4.2 Repositorio de Contratos y Alertas de Renovación (30 / 60 Días)
- Cada contrato almacena: RUC del proveedor, fecha de inicio, fecha de término, pólizas de seguro, importe mensual, archivo PDF del contrato firmado y persona de contacto de emergencia.
- **Alertas Automáticas:**
  - A los **60 días** antes del vencimiento: Notificación preventiva a la Junta para evaluar renovación o cotización con otros postores.
  - A los **30 días** antes del vencimiento: Alerta prioritaria en el dashboard administrativo para gestión de addenda o nuevo acuerdo.

### 4.3 Contrato CON-51/52: egreso, aprobación, pago y caja

El contrato detallado está en [Dominio 06](../02-domains/06-egresos-proveedores/spec.md),
los escenarios en [egresos.feature](../02-domains/06-egresos-proveedores/features/egresos.feature) y los contratos de API/OpenAPI en
[`api-contracts.md`](../05-api/api-contracts.md#con-51-y-con-52-egresos-aprobaciones-pagos-y-caja).
La integración con CON-48/49 se rige por
[`CON-48-49-51-52-integracion.md`](../../docs/sprints/CON-48-49-51-52-integracion.md).

- Egresos viven en `src/modules/egresos/`, separados de la conciliación de
  ingresos residentes (`src/modules/pagos/`), del presupuesto aprobado y del
  ledger de fondos de moras.
- `concepto_id` referencia el `ConceptoPresupuestal` existente. No se crea otro
  catálogo. La referencia a un ítem/periodo presupuestal es opcional y no implica
  que el gasto esté pagado ni modifica el presupuesto aprobado.
- `proveedor_id` UUID nullable y `contrato_id` UUID nullable. El servicio valida
  contexto y relación proveedor-contrato. El desarrollo del módulo no espera la
  integración de CON-48/49: inicialmente estas referencias no tienen FK física;
  su FK se incorpora en migración posterior a integrar las tablas proveedoras.
  No se crean tablas ficticias ni cabezas Alembic paralelas.
- El registrador no puede aprobar su propio egreso. La política de aprobación se
  configura por condominio, no tiene umbral numérico predeterminado y requiere
  aprobación distinta del registrador. Sobre el umbral requiere una aprobación
  adicional de otra persona distinta. No se introducen roles nuevos: se usan los
  roles existentes `ADMIN_JUNTA`/`SUPERADMIN`; `AUDITOR` solo consulta. La
  autorización concreta de configuración queda auditable y contextual.
- Si falta configuración de aprobación, se permite crear/editar borradores y
  consultar, pero no presentar para aprobación ni decidir hasta configurar la
  política. El importe aprobado queda ligado a su versión; editarlo invalida las
  aprobaciones vigentes sin borrar su historia.
- Aprobar no afecta caja. Después de la ejecución bancaria, Tesorería registra
  fecha efectiva, importe, referencia, cuenta y evidencia. Confirmar se bloquea
  hasta que exista apertura conciliada de caja para esa cuenta/moneda.
- Caja operativa usa ledger independiente de `movimientos_fondo_moras`. El saldo
  se deriva de movimientos; el saldo inicial exige apertura explícita, actor,
  fecha de corte y sustento conciliado. No se infiere de cuotas emitidas ni de
  fondos de moras.
- Pagos parciales están soportados en el diseño, pero la configuración inicial
  es deshabilitada. Mientras esté deshabilitada, solo se acepta el saldo total
  aprobado pendiente. Si se habilita, los pagos acumulados no pueden exceder el
  aprobado. Claves de idempotencia, locks y transacción atómica impiden doble
  afectación. Reversos son movimientos compensatorios; nunca borrado de pagos o
  ledger.
- Registro de egreso no crea movimiento de caja. Una cobertura de moras modifica
  exclusivamente su fondo y presupuesto según PROC-01; no genera un pago al
  proveedor ni un segundo egreso.

### 4.4 Estados de CON-51/52

**Egreso:** `BORRADOR`, `PENDIENTE_APROBACION`, `APROBADO`, `RECHAZADO`,
`PAGO_PARCIAL`, `PAGADO`, `CANCELADO`.

- Crear: `BORRADOR`.
- Presentar con sustento requerido y política configurada: `BORRADOR` →
  `PENDIENTE_APROBACION`.
- Aprobar: conserva `PENDIENTE_APROBACION` hasta reunir el número de aprobaciones
  requerido; entonces pasa a `APROBADO`.
- Rechazar con motivo: `PENDIENTE_APROBACION` → `RECHAZADO`.
- Reabrir para corrección: `RECHAZADO` → `BORRADOR`, con nueva versión y
  preservación del rechazo.
- Confirmar pago: `APROBADO` → `PAGO_PARCIAL` o `PAGADO`, según saldo pendiente y
  política de pagos parciales.
- Cancelar: solo un egreso sin pagos confirmados puede pasar a `CANCELADO`, con
  motivo. Egresos pagados se corrigen mediante reverso compensatorio.
- Editar importe incrementa versión, invalida decisiones vigentes y exige volver
  a presentar. El historial anterior permanece inmutable.

**Pago:** `CONFIRMADO`, `FALLIDO`, `REVERSADO`. Un fallo externo se registra sin
salida de caja; un reverso produce movimiento compensatorio referenciado al pago
original. El pago confirmado y el movimiento de caja son atómicos.

**Conflictos:** versión/estado obsoleto, aprobaciones suficientes/duplicadas,
clave de idempotencia incompatible, caja sin apertura, saldo insuficiente y
exceso del monto aprobado responden `409` con códigos estables documentados en
el contrato API.

#### 4.2.1 Alertas contractuales de 60 y 30 días (CON-50)

Detalle completo, estados y recuperación en
[alertas de contratos](../02-domains/06-egresos-proveedores/alertas-contratos.md);
escenarios en [alertas-contratos.feature.md](../04-acceptance-criteria/alertas-contratos.feature.md).

- **Destinatarios:** la Junta (`ADMIN_JUNTA`) del condominio dueño del contrato. Nunca otra Junta.
- **Prioridad:** el aviso de 60 días es `INFORMATIVA` (preventivo); el de 30 días es `PRIORITARIA`.
- **Calendario por vigencia:** cada vigencia del contrato tiene su propio calendario. Una
  renovación abre una vigencia nueva y conserva intacto el historial de la anterior.
- **Deduplicación:** un único aviso por (contrato, vigencia, umbral), sea `GENERADO` u `OMITIDO`.
- **Recuperación:** un umbral se considera vencido cuando faltan `<=` 60 (o 30) días y no tiene
  registro. Si el job se perdió y vuelve con 59 días, emite el de 60 una sola vez. Si vuelve con
  29 días y ambos están pendientes, emite solo el de 30 y registra el de 60 como `OMITIDO`
  por prioridad. Un contrato ya vencido (menos de 0 días) no genera avisos nuevos.
- **Auditoría:** cada aviso registra `ALERTA_VENCIMIENTO_CONTRATO` en `auditoria_logs` con actor
  `SISTEMA_AUTOMATICO`.

---

## 5. Ciclo de Automatización

```
 [ Cron Diario: Evaluar Contratos ]
                 │
                 ▼
 [ ¿Contrato expira en 30 o 60 días? ]
                 │
        ┌────────┴────────┐
        ▼                 ▼
      [ SÍ ]            [ NO ]
        │                 │
        ▼                 ▼
 [ Despachar Alerta a ] [ Sin acción ]
 [ Junta Directiva    ]
```

---

## 6. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: `"CONDOMINIO_GENERAL"`
- `timestamp`: UTC.
- `accion_ejecutada`: `"REGISTRO_EGRESO_PROVEEDOR"` o `"ALERTA_VENCIMIENTO_CONTRATO"`.
- `motivo`: `"Pago mensual de mantenimiento de ascensores según Factura F001-209"`.
- `resultado`: `"EXITOSO"`.
- `estado_anterior`: `{"saldo_banco": 25400.00}`.
- `estado_posterior`: `{"saldo_banco": 24200.00, "monto_egreso": 1200.00, "proveedor_ruc": "20512345678"}`.
