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
Todo egreso debe imputarse obligatoriamente a una categoría presupuestal predefinida:
- `SERVICIOS_BASICOS`: Agua común (Sedapal), Electricidad común (Luz del Sur/Enel).
- `MANTENIMIENTO_PREVENTIVO`: Ascensores (Otis, Schindler, etc.), Bombas de agua hidroneumáticas, Puertas levadizas.
- `SEGURIDAD_Y_VIGILANCIA`: Empresa de conserjería / vigilancia 24/7.
- `LIMPIEZA_Y_JARDINERIA`: Insumos y servicio de aseo.
- `GASTOS_ADMINISTRATIVOS`: Comisiones bancarias, software, asesoría contable o legal.
- `IMPREVISTOS_Y_CONTINGENCIAS`: Reparaciones extraordinarias por fallas súbitas.

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
