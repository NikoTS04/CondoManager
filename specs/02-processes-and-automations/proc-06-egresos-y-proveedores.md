# PROC-06: Control de Egresos, Proveedores y Repositorio de Contratos

## 1. Ficha del Proceso
- **Identificador:** PROC-06
- **Responsable del Módulo:** **Tesorería / Administración**
- **Estado:** En Especificación
- **Versión:** 1.0
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
