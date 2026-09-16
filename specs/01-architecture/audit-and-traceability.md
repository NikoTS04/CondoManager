# Auditoría y Trazabilidad Transaccional (Audit & Traceability)

## 1. Principio de Inmutabilidad del Libro Mayor

En cumplimiento con los requerimientos de integridad contable y transparencia financiera:

1. **Prohibición de Eliminación Física (Zero Hard-Deletes):**
   - Ningún registro de cobro, cuota, egreso, penalidad o conciliación puede ser eliminado (`DELETE`) de la base de datos una vez emitido o confirmado.
2. **Correcciones mediante Asientos Compensatorios (Notas de Crédito / Ajustes):**
   - Si un pago fue aprobado por error o un monto fue mal calculado, se registra una transacción de ajuste inverso (ej. `NotaDeCredito` o `AjusteCompensatorio`) vinculada al registro original.
   - El motivo de la corrección y el usuario que la autorizó son campos obligatorios.
3. **Firmas de Integridad (Audit Hashing):**
   - Cada entrada de auditoría genera un hash criptográfico encadenado (`SHA-256`) que incluye el hash de la entrada anterior, garantizando que los registros no puedan ser alterados directamente en la base de datos sin romper la cadena.

---

## 2. Los 7 Campos Mínimos Obligatorios de Trazabilidad

Cualquier evento de negocio o acción automática/manual genera obligatoriamente un registro en la tabla `auditoria_logs` con la siguiente estructura:

| Campo | Tipo de Dato | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `1. departamento_id` | `UUID / String` | Departamento o unidad habitacional involucrada | `"Dpto-501 (Torre B)"` |
| `2. timestamp` | `TIMESTAMP WITH TZ` | Fecha y hora exacta en UTC | `2026-09-16T17:30:00Z` |
| `3. accion_ejecutada` | `VARCHAR(100)` | Código estándar de la operación | `"APLICAR_MORA_CORTE"` |
| `4. motivo` | `TEXT` | Justificación de negocio o regla aplicada | `"Vencimiento sin pago verificado tras 2 días de gracia"` |
| `5. resultado` | `VARCHAR(50)` | Estado final de la acción | `"EXITOSO"` / `"FALLIDO"` |
| `6. estado_anterior` | `JSONB` | Fotografía del estado antes de la acción | `{"saldo": 150.00, "estado": "VENCIDO"}` |
| `7. estado_posterior` | `JSONB` | Fotografía del estado resultante | `{"saldo": 170.00, "estado": "MOROSO"}` |

### Metadatos Complementarios:
- `actor_tipo`: `SISTEMA_AUTOMATICO` | `ADMINISTRADOR` | `RESIDENTE`
- `actor_id`: Identificador del usuario que ejecutó la acción (o `"SYSTEM_WORKER"`).
- `ip_origen` y `user_agent`: Para acciones originadas desde la interfaz web/móvil.

---

## 3. Formato del Payload de Auditoría (Schema JSON)

```json
{
  "id": "a9b7c8d6-4f3e-4b2a-9e1d-8c7a6b5e4d3c",
  "condominio_id": "villa-bonita-3",
  "departamento_id": "dpto-501",
  "timestamp": "2026-09-16T17:30:00Z",
  "accion_ejecutada": "CONCILIACION_PAGO_APROBADA",
  "motivo": "Comprobante verificado con abono en cuenta BCP operacion 0098231",
  "resultado": "EXITOSO",
  "actor": {
    "tipo": "ADMINISTRADOR",
    "usuario_id": "usr-admin-01",
    "nombre": "Tesorero Junta Directiva"
  },
  "estado_anterior": {
    "cuota_id": "cuota-2026-09",
    "estado_cuota": "PENDIENTE",
    "saldo_pendiente": 150.00,
    "acceso_reservas": "HABILITADO"
  },
  "estado_posterior": {
    "cuota_id": "cuota-2026-09",
    "estado_cuota": "PAGADA",
    "saldo_pendiente": 0.00,
    "acceso_reservas": "HABILITADO",
    "comprobante_id": "comp-7842"
  },
  "hash_actual": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "hash_previo": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
}
```

---

## 4. Auditoría de Finanzas y Libro Mayor Unificado

El libro mayor unificado consolida cronológicamente todas las entradas y salidas financieras:
1. **Ingresos Ordinarios:** Pagos de cuotas mensuales de mantenimiento.
2. **Ingresos Extraordinarios:** Cuotas para obras o fondos de reserva.
3. **Ingresos por Penalidades:** Recargos por mora o multas por convivencia.
4. **Ingresos por Áreas Comunes:** Tarifas de uso o alquiler de salón/parrillas.
5. **Egresos Operativos:** Pagos a empresas de servicios (agua, luz común, ascensor, seguridad, limpieza).
6. **Egresos Extraordinarios:** Reparaciones no presupuestadas o contingencias.

Cada línea del libro mayor está vinculada al comprobante digital correspondiente (foto de voucher bancario, recibo de servicios públicos o factura electrónica de proveedor), impidiendo transacciones "fantasma" o no sustentadas.
