# PROC-01: Gestión de Cuotas de Mantenimiento

## 1. Ficha del Proceso
- **Identificador:** PROC-01
- **Responsable del Módulo:** **Anderson**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-02 (Pagos), PROC-03 (Notificaciones), PROC-08 (Reportes)

---

## 2. Propósito y Alcance del Proceso
Automatizar el cálculo, generación masiva y emisión periódica de las cuotas ordinarias y extraordinarias de mantenimiento para cada departamento o unidad habitacional del condominio/edificio. 

El módulo calcula el importe correspondiente a cada unidad según su modelo de reparto (alícuota fija o coeficiente de participación inmobiliario), programa su fecha de vencimiento y mantiene actualizado el estado de cada obligación financiera.

---

## 3. Disparadores y Eventos de Entrada
1. **Cron Programado de Inicio de Mes (Automático):** Disparado el primer día calendario de cada mes a las 00:00:00.
2. **Generación Manual por el Administrador (Bajo Demanda):** Formulario para emitir cuotas extraordinarias (ej. cuota especial para pintura de fachada o reparación de ascensores).
3. **Evento de Corrección Presupuestal:** Actualización del presupuesto mensual aprobado en asamblea.

---

## 4. Reglas de Negocio y Fórmulas

### 4.1 Cálculo del Monto por Departamento
El sistema soporta dos modalidades parametrizables por edificio:
1. **Modalidad Alícuota / Coeficiente de Propiedad:**
   $$\text{Cuota}(d) = \text{Presupuesto Total Ordinario} \times \frac{\text{Coeficiente}(d)}{100}$$
   *Donde $\sum \text{Coeficiente} = 100.000\%$.*
2. **Modalidad Cuota Equitativa Fija:**
   $$\text{Cuota}(d) = \frac{\text{Presupuesto Total Ordinario}}{N \text{ Unidades Activas}}$$

### 4.2 Fechas Clave y Plazos
- **Fecha de Emisión:** Día 1 del mes correspondiente.
- **Fecha Límite de Pago Oportuno (Vencimiento):** Día parametrizable (por defecto: día 20 del mes a las 23:59:59).
- **Periodo de Gracia:** 2 días calendario posteriores a la fecha de vencimiento antes de activar recargos por mora.

### 4.3 Manejo de Saldos a Favor Anteriores
Si un departamento cuenta con un saldo a favor en su cuenta corriente (originado por pagos en exceso previos o notas de crédito):
- El sistema aplica automáticamente dicho saldo para amortizar o liquidar la nueva cuota emitida:
  $$\text{Monto a Pagar} = \max(0, \text{Cuota Emitida} - \text{Saldo a Favor})$$
- Se descuenta el saldo a favor consumido y se registra el movimiento correspondiente.

---

## 5. Ciclo de Automatización

| Fase | Detalle Técnico |
| :--- | :--- |
| **1. Evento** | `CronJob: 0 0 1 * *` dispara la tarea `GenerarCuotasMensuales(condominio_id, periodo)`. |
| **2. Evaluación de Reglas** | Consulta el presupuesto activo del mes, la lista de unidades activas, sus coeficientes de participación y los saldos a favor pendientes. |
| **3. Decisión** | ¿Existe presupuesto aprobado para el periodo? <br>- Sí $\rightarrow$ Continúa con el cálculo individual por departamento. <br>- No $\rightarrow$ Genera alerta urgente al Administrador y aborta emisión masiva. |
| **4. Acción** | 1. Inserta las filas en la tabla `cuotas_mantenimiento` con estado `EMITIDA`. <br>2. Aplica saldos a favor si existiesen. <br>3. Cambia estado a `PENDIENTE` (o `PAGADA` si se cubrió con saldo a favor). <br>4. Emite el evento `CuotasEmitidasEvent(periodo)`. |
| **5. Verificación** | 1. Suma los montos emitidos y comprueba que coincidan con el presupuesto total: $\sum \text{Cuotas} = \text{Presupuesto}$. <br>2. Dispara a PROC-03 (Alejandro) el envío del aviso de nueva cuota a los residentes. |

---

## 6. Máquina de Estados de la Cuota

```
 [ INICIO ]
     │
     ▼
 [ EMITIDA ] ──(Tiene saldo a favor total)──▶ [ PAGADA ] (Cerrada)
     │
     ▼
 [ PENDIENTE ] ──(Pago conciliado a tiempo)─▶ [ PAGADA ]
     │
     ▼ (Llega fecha de vencimiento)
 [ VENCIDA ] ──(Se supera periodo de gracia)──▶ [ EN_MORA ] ──(Pago tardío)─▶ [ PAGADA ]
```

---

## 7. Intervención Humana y Excepciones
- **Aprobación de Cuotas Extraordinarias:** El Administrador ingresa el monto total aprobado en acta de asamblea, la cantidad de cuotas a fraccionar y la descripción del proyecto.
- **Anulación de Cuota:** En caso de error de digitación del presupuesto, solo se permite anular una emisión si ningún residente ha efectuado pagos aún sobre dicho lote; en caso contrario, se procesa vía ajuste contable auditado.

---

## 8. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Identificador de la unidad.
- `timestamp`: Marca de tiempo UTC.
- `accion_ejecutada`: `"EMISION_CUOTA_ORDINARIA"` o `"APLICACION_SALDO_FAVOR"`.
- `motivo`: `"Emisión mensual automatizada periodo 2026-10"`.
- `resultado`: `"EXITOSO"`.
- `estado_anterior`: `{"estado": "SIN_EMISION", "saldo": 0.00}`.
- `estado_posterior`: `{"cuota_id": "uuid", "monto": 165.50, "estado": "PENDIENTE"}`.

---

## 9. Escenarios de Aceptación (BDD)
```gherkin
Escenario: Emisión exitosa de cuota ordinaria mensual
  Dado que existe un condominio con presupuesto mensual aprobado de S/ 20,000
  Y el departamento 301 tiene un coeficiente de participación del 0.85%
  Cuando el reloj del sistema marca las 00:00 del día 1 del mes
  Entonces el sistema emite una cuota de S/ 170.00 para el departamento 301
  Y la cuota queda en estado "PENDIENTE" con fecha de vencimiento el día 20 del mes en curso.
```
