# PROC-02: Gestión de Pagos, Conciliación y Morosidad

## 1. Ficha del Proceso
- **Identificador:** PROC-02
- **Responsable del Módulo:** **Tarqui**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-03 (Notificaciones), PROC-04 (Reservas)

---

## 2. Propósito y Alcance del Proceso
Gestionar el ciclo completo de recaudación: desde la recepción y validación de comprobantes de pago reportados por los residentes (Yape, transferencias bancarias directas e interbancarias CCI), la bandeja de conciliación de la Junta Directiva, hasta el motor automático de cálculo y aplicación de moras sobre cuotas vencidas.

---

## 3. Disparadores y Eventos de Entrada
1. **Reporte de Pago por Residente (UI Web/Móvil):** El residente envía foto del comprobante, banco emisor, número de operación bancaria, fecha y monto pagado.
2. **Cron Nocturno de Vencimientos y Moras:** Disparado diariamente a las 00:05:00 UTC para evaluar cuotas vencidas que agotaron su periodo de gracia.
3. **Acción de Conciliación por Administrador:** Aprobación o rechazo manual de comprobantes en la bandeja de tesorería.

---

## 4. Reglas de Negocio

### 4.1 Validación y Registro de Comprobantes (Idempotencia)
- Cada reporte de pago valida que la combinación `(banco, numero_operacion, fecha_emision)` no exista previamente para evitar que el mismo voucher sea usado dos veces o por dos departamentos diferentes.
- Si la validación pasa, el comprobante queda en estado `EN_REVISION` y se notifica a la junta directiva para su conciliación bancaria.

### 4.2 Motor de Moras Automatizado
- **Fecha de Corte:** Día 20 de cada mes a las 23:59:59.
- **Periodo de Gracia:** 2 días adicionales (corte definitivo: día 22 a las 23:59:59).
- **Regla de Recargo:** Si una cuota no registra comprobante aprobado al vencer la gracia:
  - Se evalúa la fórmula configurada para el edificio:
    - *Monto Fijo:* Penalidad fija (ej. S/ 20.00).
    - *Porcentaje sobre saldo:* $\text{Mora} = \text{Saldo Pendiente} \times \frac{\% \text{ Tasa}}{100}$
  - Se genera un concepto de cargo por mora vinculado a la cuota.
  - El estado del departamento se marca como `CON_DEUDA_VENCIDA`.
  - Se inhabilita la capacidad del residente para solicitar reservas en áreas comunes (PROC-04).

### 4.3 Imputación de Pagos (Orden de Prelación)
Cuando un pago es aprobado por el Administrador, los fondos se aplican en estricto orden cronológico y de prelación contable:
1. Penalidades y Moras acumuladas más antiguas.
2. Cuotas extraordinarias vencidas más antiguas.
3. Cuotas ordinarias de mantenimiento vencidas más antiguas.
4. Cuota ordinaria del mes en curso.
5. Excedente (si sobra dinero) $\rightarrow$ Pasa a `Saldo a Favor` del departamento.

---

## 5. Ciclo de Automatización

### A. Al Reportar Pago (Residente)
$$\text{Formulario} \longrightarrow \text{Validar Hash Idempotente} \longrightarrow \text{Crear Comprobante} \longrightarrow \text{Notificar a Junta}$$

### B. Al Vencer Cuota (Cron de Moras)
| Fase | Detalle Técnico |
| :--- | :--- |
| **1. Evento** | Cron diario ejecuta `EvaluarMorasVencidasJob()`. |
| **2. Evaluación** | Filtra cuotas con `fecha_vencimiento + dias_gracia < AHORA` y `estado IN ('PENDIENTE', 'PAGO_PARCIAL')`. |
| **3. Decisión** | ¿Existe pago pendiente de conciliar en bandeja? <br>- Si existe comprobante reportado pendiente de revisión $\rightarrow$ Se pospone la mora 24h para no perjudicar al vecino mientras la junta revisa. <br>- Si no hay pago reportado $\rightarrow$ Aplica mora inmediatamente. |
| **4. Acción** | 1. Genera cargo por mora. <br>2. Cambia estado a `EN_MORA`. <br>3. Activa restricción de reservas. <br>4. Emite evento `MoraAplicadaEvent`. |
| **5. Verificación** | Valida que el saldo total exigible del departamento sea actualizado y despacha solicitud a PROC-03 para enviar el aviso de mora. |

---

## 6. Máquina de Estados del Comprobante de Pago

```
 [ SUBIDO POR RESIDENTE ]
             │
             ▼
      [ EN_REVISION ]
             │
     ┌───────┴───────┐
     ▼               ▼
[ RECHAZADO ]   [ APROBADO / CONCILIADO ]
 (Con motivo)        │
                     ▼
           [ IMPUTADO A CUOTA(S) ]
```

---

## 7. Intervención Humana y Excepciones
- **Bandeja de Conciliación:** Panel de dos columnas donde el tesorero ve el extracto bancario a la izquierda y los comprobantes enviados a la derecha para emparejamiento con un clic (`Aprobar` o `Rechazar`).
- **Exoneración de Mora:** El Administrador puede perdonar una mora justificada (ej. corte de energía prolongado o error en canal bancario). Requiere registrar una justificación textual obligatoria y genera un asiento de ajuste contable.

---

## 8. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Identificador del departamento.
- `timestamp`: UTC.
- `accion_ejecutada`: `"CONCILIACION_PAGO"` o `"APLICACION_RECARGO_MORA"`.
- `motivo`: `"Comprobante BCP operacion 49201 aprobado"` / `"Vencimiento sin pago tras gracia"`.
- `resultado`: `"EXITOSO"`.
- `estado_anterior`: `{"estado": "EN_REVISION", "saldo": 150.00}`.
- `estado_posterior`: `{"estado": "APROBADO", "saldo": 0.00}`.

---

## 9. Escenarios de Aceptación (BDD)
```gherkin
Escenario: Aplicación automática de mora tras vencer periodo de gracia
  Dado que el departamento 402 tiene una cuota de S/ 150.00 con vencimiento el 20 de octubre
  Y el periodo de gracia es de 2 días
  Y no existe ningún comprobante reportado por el residente
  Cuando el reloj del sistema llega a las 00:01 del día 23 de octubre
  Entonces el sistema genera un recargo por mora de S/ 20.00
  Y el saldo total exigible del departamento 402 pasa a ser de S/ 170.00
  Y el departamento queda bloqueado para realizar reservas de áreas comunes.
```
