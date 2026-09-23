# Dominio 06: Control de Egresos, Proveedores y Repositorio de Contratos

## 1. Ficha del Dominio
- **Identificador:** DOM-06 / PROC-06
- **Responsable:** **Tesorería / Junta Directiva**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/egresos/`

---

## 2. Propósito y Alcance
Centralizar el registro de egresos operativos (luz, agua, ascensores, seguridad, limpieza) clasificados por partida presupuestal, gestionar el directorio de contratistas y mantener la custodia digital de contratos con alertas tempranas automáticas de vencimiento a los 60 y 30 días.

---

## 3. Alertas Preventivas de Contratos
- Cron diario a las 01:00 UTC evalúa `contratos_proveedor.fecha_fin`.
- A los 60 días: Alerta informativa para abrir proceso de cotización o renovación.
- A los 30 días: Alerta prioritaria en el dashboard para firma de addenda o nuevo contrato marco.
