# Dominio 08: Reportería Financiera, KPIs y Balances Mensuales

## 1. Ficha del Dominio
- **Identificador:** DOM-08 / PROC-08
- **Responsable:** **Junta Directiva / Tesorería**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/reportes/`

---

## 2. Indicadores en Tiempo Real y Generación de Balances
Ampliación objetivo pendiente de implementación:
[llenado, aprobación y exportación de prorrateo](../01-cuotas/prorrateo-y-mora-diaria.md#7-reporte-mensual-llenado-consulta-pdf-y-docx).
PDF y DOCX se generan desde la misma versión. Incluye desglose jerárquico,
financiación con moras, fondos, cronograma y anexo de centavos, sin exponer datos
personales ajenos. Recaudación oportuna cierra el día 10 en Lima, según fecha
bancaria validada. Gracia no amplía ese indicador. Borradores marcados; aprobados
inmutables; correcciones no modifican automáticamente cuotas emitidas.

1. **Tasa de Morosidad (%):** Relación porcentual entre la deuda vencida exigible y el total emitido del periodo.
2. **Flujo de Caja Neto:** Ingresos efectivamente conciliados menos egresos ejecutados en el mes.
3. **Generador de Balances:** Al cierre de cada mes, genera un archivo PDF formal de rendición de cuentas inmutable con desglose de recaudación y cuentas por cobrar.
