# Política de Idempotencia y Desduplicación (Idempotency & Deduplication)

## 1. Justificación y Alcance

En operaciones de recaudación vecinal mediante canales como Yape, Plin o transferencias interbancarias CCI, es sumamente frecuente que:
1. El usuario presione repetidamente el botón "Reportar Pago" en su teléfono móvil por lentitud de conexión.
2. Un residente intente utilizar un mismo comprobante o voucher bancario para justificar cuotas de meses distintos o departamentos diferentes.
3. El worker asíncrono reintente una tarea de aplicación de cuota o mora tras un timeout de red, arriesgando duplicar el cargo.

Para proteger la integridad financiera, CondoManager aplica **garantía de procesamiento exactamente una vez (Exactly-Once Semantics a nivel lógico)** mediante claves de idempotencia deterministas.

---

## 2. Generación del Hash de Idempotencia de Comprobantes (CON-22/23)

Para cada comprobante de pago reportado, el backend calcula obligatoriamente un hash criptográfico SHA-256 normalizado:

$$\text{IdempotencyHash} = \text{SHA256}(\text{condominio\_id} + "|" + \text{banco\_normalizado} + "|" + \text{numero\_operacion} + "|" + \text{fecha\_operacion} + "|" + \text{monto\_formateado})$$

### Normalización de Atributos:
- `banco_normalizado`: Mayúsculas sin espacios (`"YAPE"`, `"BCP"`, `"INTERBANK"`, `"PLIN"`, `"BBVA"`).
- `numero_operacion`: Eliminación de ceros a la izquierda no significativos y espacios (`"0089214"` $\rightarrow$ `"89214"`).
- `fecha_operacion`: Formato `YYYY-MM-DD`.
- `monto_formateado`: Representación decimal con 2 decimales exactos (`"150.00"`).

El monto debe ser positivo y representable en `NUMERIC(12,2)` antes de formar el hash; rechazar precisión adicional y notación exponencial. La cadena es UTF-8. Si la operación queda compuesta solo por ceros, su forma canónica es `0`. La unicidad sobre `idempotency_hash` es persistente y resuelve también carreras entre procesos.

---

## 3. Comportamiento del Sistema ante Duplicados

```
[ POST /api/v1/pagos/reportar ]
               │
               ▼
[ Calcular IdempotencyHash ]
               │
               ▼
[ Consultar índice único en comprobantes_pago(idempotency_hash) ]
               │
       ┌───────┴───────┐
       ▼               ▼
(Hash Ya Existe)    (Hash Nuevo)
       │               │
       ├─────────────────────────────────┐
       ▼                                 ▼
(Estado == 'APROBADO')       (Estado == 'EN_REVISION')
Retorna 409 Conflict         Retorna 200 OK
"VOUCHER_YA_CONCILIADO"      "VOUCHER_EN_EVALUACION"
                             (Retorna DTO previo sin duplicar)
```

---

### Contrato HTTP del Sprint 2

La [base CON-72](../05-api/sprint-2-contratos.md#5-pagos--anderson-y-brandon-persistencia-con-70) concreta el comportamiento: nuevo `202 COMPROBANTE_RECIBIDO`; reintento propio en revisión `200 VOUCHER_EN_EVALUACION`; aprobado `409 VOUCHER_YA_CONCILIADO`; otra unidad `409 VOUCHER_UNIDAD_DISTINTA` sin exponer su registro. `codigo` se devuelve en la recepción exitosa; los conflictos usan `error_code` en raíz.

Un observado responde `409 VOUCHER_REQUIERE_SUBSANACION` y se corrige mediante `PUT /pagos/{comprobante_id}/voucher`, conservando UUID/hash e historial. Un rechazado responde `409 VOUCHER_RECHAZADO`, sin reapertura automática. Consultar el hash no sustituye la restricción única SQL ni autoriza a reutilizar la operación en otra unidad. La reentrega equivalente no sube otro archivo ni publica otro evento.

## 4. Idempotencia en Tareas Programadas (Crons)

Las tareas automáticas de corte de mora y emisión mensual incorporan una clave de ejecución idempotente basada en el periodo:
- Clave de emisión: `EMISION_CUOTAS_{condominio_id}_{periodo}` (ej. `EMISION_CUOTAS_vb3_2026-10`).
- Si la tarea se ejecuta dos veces por error del scheduler, la consulta verifica si ya existen registros en `cuotas_mantenimiento` para ese periodo y condominio, abortando inmediatamente la duplicación.
