# Diccionario de Datos Exhaustivo (Data Dictionary)

Este documento especifica a nivel de campo y columna todas las tablas relacionales de la base de datos PostgreSQL de **CondoManager**.

---

## 1. Tabla: `condominios`
Almacena las comunidades inmobiliarias o edificios matrices.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único global del condominio. |
| `nombre` | `VARCHAR(150)` | NO | - | - | Nombre comercial del edificio (ej. "Edificio 3 - Villa Bonita 3"). |
| `direccion` | `TEXT` | NO | - | - | Ubicación geográfica formal. |
| `moneda` | `VARCHAR(3)` | NO | `'PEN'` | `CHECK (moneda IN ('PEN', 'USD'))` | Moneda oficial para cobro de cuotas y libros contables. |
| `regla_mora_tipo` | `VARCHAR(20)` | NO | `'MONTO_FIJO'` | `CHECK (regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO'))` | Mecanismo de recargo punitorio por mora. |
| `monto_mora_fijo` | `NUMERIC(12,2)` | SÍ | `20.00` | `CHECK (monto_mora_fijo >= 0.00)` | Importe de penalidad fija si aplica modalidad fija. |
| `tasa_mora_porcentaje`| `NUMERIC(6,4)` | SÍ | `0.0000` | `CHECK (tasa_mora_porcentaje >= 0.0000)` | Tasa mensual de interés punitorio si aplica porcentaje. |
| `dias_corte` | `SMALLINT` | NO | `20` | `CHECK (dias_corte BETWEEN 1 AND 28)` | Día calendario de vencimiento regular de la cuota mensual. |
| `dias_gracia` | `SMALLINT` | NO | `2` | `CHECK (dias_gracia >= 0)` | Días de tolerancia antes de ejecutar la penalidad de mora. |
| `creado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Auditoría de creación de registro. |

---

## 2. Tabla: `departamentos`
Almacena cada unidad inmobiliaria exclusiva (departamento, flat, local).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único de la unidad. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id) ON DELETE CASCADE` | Condominio al que pertenece. |
| `numero` | `VARCHAR(20)` | NO | - | `UNIQUE (condominio_id, numero)` | Número identificador del departamento (ej. "101", "504B"). |
| `piso` | `SMALLINT` | NO | - | `CHECK (piso >= 1)` | Piso o nivel en el que se ubica la unidad. |
| `coeficiente_participacion` | `NUMERIC(7,4)` | NO | - | `CHECK (coeficiente_participacion > 0.0000)` | Alícuota porcentual de participación sobre el 100%. |
| `saldo_a_favor` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (saldo_a_favor >= 0.00)` | Fondo crediticio a favor del departamento por pagos en exceso. |
| `estado_financiero` | `VARCHAR(20)` | NO | `'AL_DIA'` | `CHECK (estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA'))` | Estado de solvencia para control de reservas comunes. |

> **Fuente de la invariante de solvencia (PROC-04):** `POST /api/v1/reservas` lee esta columna
> como primer filtro. Un departamento en `EN_MORA` recibe `403 DEUDA_MORA_ACTIVA` sin importar la
> disponibilidad del horario. El monto que se informa en el mensaje es solo informativo
> (suma del pendiente de `cuotas_mantenimiento` en `VENCIDA`/`EN_MORA`, si existe).

---

## 3. Tabla: `areas_comunes`
Catálogo de espacios compartidos disponibles para reserva (Brandon - PROC-04).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único del área común. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id) ON DELETE CASCADE` | Condominio propietario del espacio. |
| `nombre` | `VARCHAR(100)` | NO | - | - | Nombre visible en el catálogo (único por condominio, controlado por la aplicación). |
| `descripcion` | `TEXT` | SÍ | `NULL` | - | Detalles, reglas de uso o ubicación del espacio. |
| `aforo_maximo` | `INT` | NO | - | `CHECK (aforo_maximo > 0)` | Máximo de personas permitidas. |
| `costo_reserva` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (costo_reserva >= 0.00)` | Canon por turno de uso (ADR-002: cero `float`). |
| `esta_activa` | `BOOLEAN` | NO | `TRUE` | - | Solo las activas se publican en `GET /api/v1/areas`. |

---

## 4. Tabla: `cuotas_mantenimiento`
Almacena las obligaciones devengadas mensuales por cada departamento (Anderson - PROC-01).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador de la cuota. |
| `departamento_id` | `UUID` | NO | - | `REFERENCES departamentos(id) ON DELETE RESTRICT` | Departamento deudor. |
| `periodo` | `VARCHAR(7)` | NO | - | - | Periodo contable en formato `YYYY-MM` (ej. "2026-10"). |
| `monto_ordinario` | `NUMERIC(12,2)` | NO | - | `CHECK (monto_ordinario >= 0.00)` | Monto base correspondiente al presupuesto mensual. |
| `monto_extraordinario` | `NUMERIC(12,2)`| NO | `0.00` | `CHECK (monto_extraordinario >= 0.00)`| Cargos aprobados por obras o imprevistos. |
| `monto_mora` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (monto_mora >= 0.00)` | Recargo punitorio aplicado al vencer la gracia. |
| `monto_descuento` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (monto_descuento >= 0.00)` | Descuentos aplicados por pronto pago o saldos a favor. |
| `monto_total_exigible` | `NUMERIC(12,2)`| NO | - | `CHECK (monto_total_exigible >= 0.00)`| Importe neto exigible: `(ordinario + extra + mora) - descuento`. |
| `monto_pagado` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (monto_pagado BETWEEN 0.00 AND monto_total_exigible)`| Total amortizado mediante pagos conciliados. |
| `fecha_emision` | `DATE` | NO | - | - | Fecha formal de devengo (día 1 del mes). |
| `fecha_vencimiento`| `DATE` | NO | - | - | Fecha límite de pago oportuno (día de corte). |
| `estado` | `VARCHAR(20)` | NO | `'EMITIDA'` | `CHECK (estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA'))` | Ciclo de vida de la obligación. |

---

## 5. Tabla: `comprobantes_pago`
Almacena los reportes de vouchers subidos por los residentes (Tarqui - PROC-02).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador del comprobante. |
| `departamento_id` | `UUID` | NO | - | `REFERENCES departamentos(id)` | Departamento que reporta el pago. |
| `banco_origen` | `VARCHAR(30)` | NO | - | - | Entidad bancaria o billetera (Yape, Plin, BCP, BBVA, etc.). |
| `numero_operacion`| `VARCHAR(50)` | NO | - | - | Código de operación impreso en el voucher bancario. |
| `fecha_operacion` | `DATE` | NO | - | - | Fecha en que se efectuó la transferencia. |
| `monto` | `NUMERIC(12,2)` | NO | - | `CHECK (monto > 0.00)` | Importe total pagado según voucher. |
| `url_voucher` | `TEXT` | NO | - | - | Ruta de almacenamiento del archivo en S3/MinIO. |
| `idempotency_hash` | `VARCHAR(64)` | NO | - | `UNIQUE` | Hash SHA-256 para evitar duplicación del voucher. |
| `estado` | `VARCHAR(20)` | NO | `'EN_REVISION'` | `CHECK (estado IN ('EN_REVISION', 'APROBADO', 'RECHAZADO', 'OBSERVADO'))` | Estado en la bandeja de conciliación. |
| `motivo_rechazo` | `TEXT` | SÍ | `NULL` | - | Justificación obligatoria si el estado es `RECHAZADO`. |
| `conciliado_por` | `UUID` | SÍ | `NULL` | `REFERENCES usuarios(id)` | Miembro de la junta que validó el pago. |
| `conciliado_en` | `TIMESTAMP TZ` | SÍ | `NULL` | - | Fecha y hora UTC de la conciliación. |

---

## 6. Tabla: `reservas`
Almacena las solicitudes y reservas de áreas comunes (Brandon - PROC-04).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador de la reserva. |
| `area_id` | `UUID` | NO | - | `REFERENCES areas_comunes(id)` | Parrilla, salón o zona solicitada. |
| `departamento_id` | `UUID` | NO | - | `REFERENCES departamentos(id)` | Departamento titular de la reserva. |
| `fecha_reserva` | `DATE` | NO | - | - | Día calendario reservado. |
| `hora_inicio` | `TIME` | NO | - | - | Hora de inicio del uso. |
| `hora_fin` | `TIME` | NO | - | `CHECK (hora_fin > hora_inicio)` | Hora de término del uso. |
| `costo_reserva` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (costo_reserva >= 0.00)` | Canon de uso o limpieza asignado. |
| `estado` | `VARCHAR(20)` | NO | `'SOLICITADA'` | `CHECK (estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA'))` | Ciclo de vida de la reserva. |
| `creado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Marca de tiempo UTC de creación. |

---

## 7. Tabla: `auditoria_logs`
Almacena la bitácora inmutable de eventos (7 campos obligatorios).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador del log. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id)` | Condominio en el que ocurrió el evento. |
| `departamento_id` | `UUID` | SÍ | `NULL` | - | Unidad involucrada o NULL si es general. |
| `timestamp` | `TIMESTAMP TZ` | NO | `NOW()` | - | Marca de tiempo UTC inalterable. |
| `accion_ejecutada` | `VARCHAR(100)` | NO | - | - | Código estándar de la operación (ej. `CONCILIACION_PAGO`). |
| `motivo` | `TEXT` | NO | - | - | Justificación de negocio o regla evaluada. |
| `resultado` | `VARCHAR(20)` | NO | - | `CHECK (resultado IN ('EXITOSO', 'FALLIDO'))` | Resultado de la acción. |
| `actor_tipo` | `VARCHAR(30)` | NO | - | - | `SISTEMA_AUTOMATICO`, `ADMINISTRADOR`, `RESIDENTE`. |
| `actor_id` | `VARCHAR(100)` | NO | - | - | ID del usuario o worker. |
| `estado_anterior` | `JSONB` | NO | `'{}'` | - | Fotografía de datos antes de la mutación. |
| `estado_posterior`| `JSONB` | NO | `'{}'` | - | Fotografía de datos después de la mutación. |
| `hash_actual` | `VARCHAR(64)` | NO | - | - | Hash SHA-256 encadenado del registro actual. |
| `hash_previo` | `VARCHAR(64)` | SÍ | `NULL` | - | Hash SHA-256 del registro anterior en la cadena. |
