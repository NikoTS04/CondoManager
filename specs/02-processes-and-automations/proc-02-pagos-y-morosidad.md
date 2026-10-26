# PROC-02: Gestión de Pagos, Conciliación y Morosidad

## 1. Ficha del Proceso
- **Identificador:** PROC-02
- **Responsable del Módulo:** **Tarqui**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-03 (Notificaciones), PROC-04 (Reservas)

---

## 2. Propósito y Alcance del Proceso
Ampliación normativa pendiente de implementación:
[mora diaria, fecha bancaria y fondos de moras](../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
También incorpora visor privado PNG/JPEG/PDF sin guardado manual obligatorio.

Gestionar el ciclo completo de recaudación: desde la recepción y validación de comprobantes de pago reportados por los residentes (Yape, transferencias bancarias directas e interbancarias CCI), la bandeja de conciliación de la Junta Directiva, hasta el motor automático de cálculo y aplicación de moras sobre cuotas vencidas.

Para CON-22/CON-70 rige el [contrato de integración del Sprint 2](../02-domains/02-pagos-y-moras/sprint-2-anderson.md):
voucher local temporal, nombre en `url_voucher`, revisión persistente y outbox.
Esta decisión sustituye únicamente el transporte S3 del voucher durante este periodo.

---

## 3. Disparadores y Eventos de Entrada
1. **Reporte de Pago por Residente (UI Web/Móvil):** El residente envía foto del comprobante, banco emisor, número de operación bancaria, fecha y monto pagado.
2. **Cron Nocturno de Vencimientos y Moras:** Diariamente a las 00:05 de `America/Lima`, recuperando fechas omitidas por cuota mensual vencida.
3. **Acción de Conciliación por Administrador:** Aprobación o rechazo manual de comprobantes en la bandeja de tesorería.

---

## 4. Reglas de Negocio

### 4.1 Validación y Registro de Comprobantes (Idempotencia)
- Cada reporte de pago valida que la combinación `(banco, numero_operacion, fecha_emision)` no exista previamente para evitar que el mismo voucher sea usado dos veces o por dos departamentos diferentes.
- Si la validación pasa, el comprobante queda en estado `EN_REVISION` y se notifica a la junta directiva para su conciliación bancaria.

### 4.2 Motor de Moras Automatizado
Entrega 0019: habilitar nuevas emisiones MONTO_DIARIO con su snapshot completo.
El worker de pagos recupera al arrancar y a las 00:05 de Lima los días hasta la
fecha local actual (incluida). Nunca devenga antes de la emisión ni migra cuotas
históricas sin snapshot diario. La pausa de revisión dura 24 h desde el reporte
original, no desde el último intento o subsanación. No habilita reservas.

Devengos únicos por cuota/fecha y compensaciones firmadas son inmutables. El
motor reconstruye pagos nuevos de esta entrega por fecha bancaria y UUID para
empates; las amortizaciones anteriores y CON-13 son una base histórica fija.
Las imputaciones originales y revisiones siguen siendo recibos históricos;
`conciliaciones_diarias` conserva el padrón de cuotas existentes al validar cada
pago: un recálculo no reutiliza su excedente en cuotas emitidas después, ni aunque
compartan fecha con la operación. CON-13 conserva sus amortizaciones originales.
`movimientos_imputacion_diaria` registra componentes y deltas compensatorios
(mora, extraordinaria, ordinaria y crédito). Su suma es la imputación vigente.
Un retroactivo que reduzca crédito ya consumido se rechaza con 409
`CREDITO_RETROACTIVO_CONSUMIDO`, sin cambios, hasta resolver su financiación.
No se inventa saldo ni se redistribuyen amortizaciones históricas de CON-13.
0020 integra fondos utilizables para gastos; ajustes administrativos manuales no
están incluidos. El cobro anterior a esa adopción permanece como base no importada.

- **Fecha de Corte:** Día 10 de cada mes a las 23:59:59 de Lima.
- **Periodo de Gracia:** 0 por defecto; global o excepción del responsable de pago, fotografiada al emitir.
- **Regla de Recargo:** Por cada cuota mensual con principal impago después del vencimiento y gracia:
  - Se evalúa la fórmula configurada para el edificio:
    - *MONTO_DIARIO (predeterminado):* S/ 1.00 editable por cada fecha de atraso y por cada cuota. Sin capitalización. Se incluye el día bancario del pago tardío; cesa al cubrir su principal.
    - *MONTO_FIJO / PORCENTAJE_SALDO:* Modalidades anteriores conservadas para compatibilidad, no predeterminadas para el piloto.
  - Se genera un concepto de cargo por mora vinculado a la cuota.
  - El estado del departamento se marca como `CON_DEUDA_VENCIDA`.
  - Se inhabilita la capacidad del residente para solicitar reservas en áreas comunes (PROC-04).

### 4.3 Imputación de Pagos (Orden de Prelación)
La aprobación valida que la fecha bancaria no sea futura. Con cuotas diarias,
reconstruye devengos e imputaciones por componente antes de calcular el estado
actual. La mora cesa al cubrir principal, no depende del estado textual ni cobra
interés sobre sí misma. Rechazo/observación recuperan los días provisionalmente
postergados. Nuevos eventos MoraAplicadaEvent/MoraAjustadaEvent v2 se confirman
con el ledger y son consumidos idempotentemente; no cambian eventos anteriores.

La fecha efectiva es la operación bancaria validada, no la aprobación. Regularizar
devengos e imputaciones posteriores mediante ajustes auditados, sin borrar historia.
Moras generadas son cuentas por cobrar; solo moras cobradas por pagos conciliados
alimentan el fondo aplicable a gastos (PROC-06). Su aplicación no es un segundo egreso.

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
| **2. Evaluación** | Por fecha local de Lima y política histórica, procesa principal impago incluso en VENCIDA y EN_MORA. Identidad de cargo `(cuota_id, fecha_local)`; recupera días omitidos. |
| **3. Decisión** | Un comprobante EN_REVISION permite pausa provisional de contabilización de 24 h, no gracia ni condonación. Al aprobar se usa fecha bancaria; al rechazar se recuperan todos los días. Reintentos no renuevan indefinidamente la pausa. |
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
  Dado que el departamento 402 tiene una cuota de S/ 150.00 con vencimiento el 10 de octubre
  Y el periodo de gracia es de 0 días y la mora diaria es S/ 1.00
  Y no existe ningún comprobante reportado por el residente
  Cuando el motor procesa el 11 de octubre en hora de Lima
  Entonces el sistema genera un recargo por mora de S/ 1.00
  Y el saldo total exigible del departamento 402 pasa a ser de S/ 151.00
  Y el departamento queda bloqueado para realizar reservas de áreas comunes.
```
# Adopción CON-72

El reporte público es multipart único y no acepta claves de almacenamiento.
Antes de guardar evidencia se valida el reporte y se resuelve la duplicidad
bajo el lock financiero existente. La subsanación solo permite OBSERVADO a
EN_REVISION, conserva archivos privados anteriores y asocia cada revisión con
su evidencia. Repetir decisión, motivo y notas de la revisión vigente devuelve
su resultado persistido; cambiar cualquiera sobre un estado final responde 409.
Las notas internas se conservan separadas del motivo público obligatorio.
Reporte/subsanación, auditoría y outbox se confirman juntos. Los errores antes
del commit eliminan la nueva carga; un commit incierto conserva el objeto para
la limpieza/reconciliación existente. No se reescriben hashes, saldos ni eventos
históricos. Nuevos eventos usan los esquemas canónicos .v1 de CON-72.
