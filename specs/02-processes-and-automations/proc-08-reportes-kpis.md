# PROC-08: Reportería Financiera, Indicadores (KPIs) y Balances Mensuales

## 1. Ficha del Proceso
- **Identificador:** PROC-08
- **Responsable del Módulo:** **Junta Directiva / Tesorería**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos), PROC-06 (Egresos)

---

## 2. Propósito y Alcance del Proceso
Calcular y consolidar en tiempo real los indicadores clave de desempeño financiero y operativo del condominio, y generar de manera automatizada los balances mensuales y estados de rendición de cuentas descargables en formato PDF para las asambleas de propietarios.

---

## 3. Catálogo de Indicadores Clave (KPIs)

| Indicador | Fórmula Matemática | Frecuencia | Utilidad de Gestión |
| :--- | :--- | :--- | :--- |
| **Tasa de Morosidad Monetaria** | $\frac{\sum \text{Deuda Vencida Exigible}}{\sum \text{Total Cuotas Emitidas Periodo}} \times 100$ | Diaria | Alerta de liquidez inmediata para pago de proveedores críticos. |
| **Porcentaje de Recaudación Oportuna** | $\frac{\sum \text{Cobrado hasta Fecha Corte}}{\sum \text{Total Emitido Periodo}} \times 100$ | Mensual (Día 20) | Mide la efectividad del cobro puntual y cultura de pago del edificio. |
| **Flujo de Caja Neto** | $\sum \text{Ingresos Conciliados} - \sum \text{Egresos Ejecutados}$ | Mensual | Muestra si el condominio opera con superávit o déficit en el periodo. |
| **Fondo de Reserva Acumulado** | $\sum \text{Aportes Reserva} - \sum \text{Gastos Emergencia}$ | Continua | Capital de contingencia disponible ante fallas mayores de infraestructura. |

---

## 4. Generador Automatizado de Balances Mensuales (PDF)
Al cierre del último día calendario de cada mes:
1. El sistema realiza un snapshot contable inmutable con:
   - Resumen ejecutivo de ingresos y egresos.
   - Detalle de recaudación por departamento (identificando unidades al día y deudoras).
   - Detalle de facturas y recibos de proveedores pagados en el mes.
   - Conciliación bancaria contra el extracto de cuenta bancaria.
2. Genera el documento oficial `Balance_Mensual_[Periodo].pdf` accesible para consulta de todos los propietarios en el portal.
