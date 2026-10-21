# Diccionario de Datos Exhaustivo (Data Dictionary)

Este documento especifica a nivel de campo y columna todas las tablas relacionales de la base de datos PostgreSQL de **CondoManager**.

---

## Identidad persistente — CON-04

Contrato: [alta administrativa](../../02-domains/05-usuarios-rbac/alta-administrativa.md).

`usuarios` conserva sus campos originales y añade:

| Columna | Tipo | Nulo | Default | Regla |
|---|---|---|---|---|
| `esta_activo` | BOOLEAN | NO | `false` | Solo SuperAdmin cambia su estado mediante API. |
| `auth_revision` | INTEGER | NO | `1` | Positivo; cambia atómicamente con el estado o los permisos e invalida JWT previos. |
| `es_superadmin` | BOOLEAN | NO | `false` | Concesión global provisionada por CLI, no por API. |

`email` usa índice único `lower(btrim(email))`; `documento_identidad` usa índice
único `upper(btrim(documento_identidad))`. Se validan duplicados históricos al adoptar
las tablas. `password_hash` guarda PBKDF2-SHA256 y nunca se expone.
`usuario_roles` mantiene una asignación por `(usuario_id, condominio_id)` y
`usuario_departamentos` un vínculo por `(usuario_id, departamento_id)`, ambos
con claves foráneas y checks de los catálogos canónicos.

## Asignaciones revocables — CON-06

`usuario_roles.es_activo BOOLEAN NOT NULL DEFAULT true` distingue asignación
vigente y revocada sin eliminar filas ni vínculos. La migración `20261020_0008`
conserva las asignaciones existentes como activas. La unicidad del par y el check
de cuatro roles SQL se mantienen; la API solo concede ADMIN_JUNTA/AUDITOR/RESIDENTE.
Cambios reales actualizan `usuarios.auth_revision` y registran auditoría en la
misma transacción. El downgrade elimina únicamente la columna de actividad y
rechaza bajar si existen asignaciones revocadas, ya que la revisión anterior no
representa esa revocación. Las filas y auditorías se conservan. Contrato:
[roles y permisos](../../02-domains/05-usuarios-rbac/roles-y-permisos.md).

## Vínculos de tenencia — CON-05

Se reutiliza `usuario_departamentos`: UUID estable, FK de usuario y departamento,
relación canónica y `es_activo`. PUT conserva la unicidad del par; la revocación no
borra filas. Cada cambio real incrementa revisión y audita en la misma transacción.
La regla del último titular se comprueba bajo bloqueo del usuario/contexto/unidad,
incluidas carreras entre usuarios. La migración `20261020_0009` añade
`idx_vinculos_titulares_activos` sobre `(departamento_id, tipo_relacion)` donde
`es_activo IS TRUE`; no reescribe datos históricos. Contrato:
[vínculos](../../02-domains/05-usuarios-rbac/vinculos-departamentos.md).

## 1. Tabla: `condominios`
Almacena las comunidades inmobiliarias o edificios matrices.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único global del condominio. |
| `nombre` | `VARCHAR(150)` | NO | - | - | Nombre comercial del edificio (ej. "Edificio 3 - Villa Bonita 3"). |
| `direccion` | `TEXT` | NO | - | - | Ubicación geográfica formal. |
| `moneda` | `VARCHAR(3)` | NO | `'PEN'` | `CHECK (moneda IN ('PEN', 'USD'))` | Moneda oficial para cobro de cuotas y libros contables. |
| `regla_mora_tipo` | `VARCHAR(20)` | NO | - | `CHECK (regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO'))` | Mecanismo de recargo punitorio por mora. |
| `monto_mora_fijo` | `NUMERIC(12,2)` | SÍ | `NULL` | `CHECK (monto_mora_fijo >= 0.00)` | Importe de penalidad fija; obligatorio solo para `MONTO_FIJO`. |
| `tasa_mora_porcentaje`| `NUMERIC(7,4)` | SÍ | `NULL` | `CHECK (tasa_mora_porcentaje BETWEEN 0.0000 AND 100.0000)` | Tasa mensual; obligatoria solo para `PORCENTAJE_SALDO`. |
| `dia_vencimiento` | `SMALLINT` | NO | - | `CHECK (dia_vencimiento BETWEEN 1 AND 28)` | Día calendario de vencimiento regular. Nombre canónico que reemplaza `dias_corte`. |
| `dias_gracia` | `SMALLINT` | NO | - | `CHECK (dias_gracia BETWEEN 0 AND 30)` | Días calendario de tolerancia antes de ejecutar la penalidad de mora. |
| `activo` | `BOOLEAN` | NO | `TRUE` | - | Habilita el contexto del condominio; el cliente no lo establece durante el alta. |
| `creado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Auditoría de creación de registro. |

Restricción condicional `ck_condominio_configuracion_mora`:

```sql
CHECK (
    (regla_mora_tipo = 'MONTO_FIJO'
        AND monto_mora_fijo IS NOT NULL
        AND tasa_mora_porcentaje IS NULL)
    OR
    (regla_mora_tipo = 'PORCENTAJE_SALDO'
        AND tasa_mora_porcentaje IS NOT NULL
        AND monto_mora_fijo IS NULL)
)
```

---

## 2. Tabla: `presupuestos_mensuales`

Almacena el presupuesto ordinario de cada condominio y periodo (CON-9).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único del presupuesto. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id) ON DELETE RESTRICT` | Condominio propietario del presupuesto. |
| `periodo` | `VARCHAR(7)` | NO | - | Formato `YYYY-MM`; `UNIQUE (condominio_id, periodo)` | Mes contable del presupuesto. |
| `moneda` | `VARCHAR(3)` | NO | - | `CHECK (moneda IN ('PEN', 'USD'))` | Debe coincidir con `condominios.moneda`; la aplicación valida esta regla transrelacional. |
| `monto_total` | `NUMERIC(12,2)` | NO | - | `CHECK (monto_total > 0.00)` | Total ordinario aprobado para distribuir. |
| `fecha_vencimiento` | `DATE` | NO | - | Debe pertenecer a `periodo` | Fecha límite de pago de las cuotas resultantes. |
| `estado` | `VARCHAR(20)` | NO | `'BORRADOR'` | `CHECK (estado IN ('BORRADOR', 'APROBADO'))` | Estado del ciclo de vida. |
| `creado_por` | `VARCHAR(100)` | NO | - | - | Claim `sub` del actor que creó el borrador. |
| `creado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Fecha y hora UTC de creación. |
| `aprobado_por` | `VARCHAR(100)` | SÍ | `NULL` | - | Claim `sub` del actor que aprobó. |
| `aprobado_en` | `TIMESTAMP TZ` | SÍ | `NULL` | - | Fecha y hora UTC de aprobación. |
| `actualizado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Última modificación UTC. |

Restricciones adicionales:

- `ck_presupuesto_periodo`: valida el patrón `YYYY-MM` y un mes entre `01` y `12`.
- `ck_presupuesto_vencimiento_periodo`: compara año y mes de
  `fecha_vencimiento` con `periodo`.
- `ck_presupuesto_aprobacion`: exige ambos campos de aprobación en estado
  `APROBADO` y ambos nulos en `BORRADOR`.
- La coincidencia de moneda con el condominio y la inmutabilidad posterior a la
  aprobación se aplican transaccionalmente en el servicio.

---

## Tabla: `configuraciones_distribucion` (CON-10)

Una configuración vigente por condominio, sin versionado por periodo.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador de configuración. |
| `condominio_id` | `UUID` | NO | - | FK `condominios(id) ON DELETE RESTRICT`; `uq_distribucion_condominio` UNIQUE | Contexto propietario. |
| `metodo` | `VARCHAR(20)` | NO | - | `ck_distribucion_metodo`: `POR_ALICUOTA` o `EQUITATIVA` | Modalidad vigente. |
| `actualizado_por` | `VARCHAR(100)` | NO | - | - | Claim `sub` del último actor que cambió el método. |
| `actualizado_en` | `TIMESTAMP TZ` | NO | - | - | Fecha UTC asignada por el servicio. |

El servicio valida departamentos y suma porcentual, registra auditoría en la misma
transacción y bloquea el condominio para serializar PUT concurrentes. Un PUT sin
cambio no modifica actor, fecha ni auditoría. Migración `20261014_0003`, sobre
`20261008_0002`. No se modifica el modelo Departamento en esta historia.

---

## Tabla: `edificios` (CON-3)

| Columna | Tipo | Nulo | Restricción |
|---|---|---|---|
| `id` | UUID | NO | PK, generado por servidor |
| `condominio_id` | UUID | NO | FK condominios(id), ON DELETE CASCADE |
| `nombre_bloque` | VARCHAR(100) | NO | Único por condominio; índice único normalizado lower(btrim(nombre_bloque)) |
| `total_pisos` | INTEGER | NO | CHECK >=1; API máximo 32767 |

## 3. Tabla: `departamentos`
Almacena cada unidad inmobiliaria exclusiva (departamento, flat, local).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único de la unidad. |
| `edificio_id` | `UUID` | NO | - | `REFERENCES edificios(id) ON DELETE CASCADE` | El condominio se obtiene a través del edificio. |
| `numero` | `VARCHAR(20)` | NO | - | `UNIQUE (edificio_id, numero)` e índice único normalizado | Número identificador del departamento (ej. "101", "504B"). |
| `piso` | `SMALLINT` | NO | - | `CHECK (piso >= 1)` | Piso o nivel en el que se ubica la unidad. |
| `coeficiente_participacion` | `NUMERIC(7,4)` | NO | - | `CHECK (>0 AND <=100)` | Alícuota porcentual; cadena decimal en API. |
| `saldo_a_favor` | `NUMERIC(12,2)` | NO | `0.00` | `CHECK (saldo_a_favor >= 0.00)` | Fondo crediticio a favor del departamento por pagos en exceso. |
| `estado_financiero` | `VARCHAR(20)` | NO | `'AL_DIA'` | `CHECK (estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA'))` | Estado de solvencia para control de reservas comunes. |
| `activo` | `BOOLEAN` | NO | `TRUE` | - | Estado operativo; inactivos se excluyen de futuras distribuciones sin perder el historial. |

Migración `20261018_0005`: adopta el esquema existente de Supabase tras verificarlo,
o lo crea en instalaciones nuevas. El piso máximo se valida contra el edificio en
el servicio. Los registros y cambios de actividad se auditan transaccionalmente.

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

## Tabla: `aplicaciones_saldo_favor` (CON-13)

Evidencia histórica de la amortización inicial, incluso si el crédito aplicado es cero.
El departamento y condominio se obtienen mediante la cuota; no se duplican claves.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador de aplicación. |
| `cuota_id` | `UUID` | NO | - | UNIQUE; FK diferida a CON-11 | Clave de idempotencia. |
| `saldo_previo` | `NUMERIC(12,2)` | NO | - | >= 0 | Crédito antes del consumo. |
| `monto_aplicado` | `NUMERIC(12,2)` | NO | - | >= 0 | Pago con crédito, no descuento. |
| `monto_pendiente` | `NUMERIC(12,2)` | NO | - | >= 0 | Neto después de amortizar. |
| `saldo_restante` | `NUMERIC(12,2)` | NO | - | >= 0 | Remanente conservado. |
| `estado_anterior` | `VARCHAR(20)` | NO | - | EMITIDA | Estado antes de amortizar. |
| `estado_posterior` | `VARCHAR(20)` | NO | - | PAGADA / PENDIENTE | Estado resultante. |
| `creado_en` | `TIMESTAMP TZ` | NO | `NOW()` | - | Fecha UTC de aplicación. |

Checks: `saldo_previo = monto_aplicado + saldo_restante`; `PAGADA` exige pendiente
cero y `PENDIENTE` exige pendiente positivo. La cuota conserva el bruto exigible y
descuento cero; su `monto_pagado` aumenta por el crédito aplicado. Esta regla de
CON-13 prevalece sobre la descripción histórica de descuentos por saldo a favor.
Cuota, departamento, registro y auditoría se escriben en una sola transacción.

La migración `20261014_0004` no declara la FK porque todavía no existe la tabla
`cuotas_mantenimiento` en las migraciones. La migración de CON-11 que la cree debe
añadir `fk_aplicacion_saldo_cuota` (`cuota_id` → `cuotas_mantenimiento.id`,
`ON DELETE RESTRICT`). El modelo ORM conserva esta relación. Los bloqueos siguen
el orden condominio → departamento → cuota para mantener lineal la cadena auditada.

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
# Extensión CON-11 — lotes y eventos

- `lotes_cuotas`: `id UUID PK`, `condominio_id UUID FK RESTRICT`,
  `presupuesto_id UUID FK RESTRICT`, `periodo VARCHAR(7)`, `metodo VARCHAR(20)`,
  `actor_id VARCHAR(150)`, `total_cuotas_emitidas INTEGER`,
  `monto_total_facturado NUMERIC(12,2)`, `cuotas_cubiertas_saldo_favor INTEGER`,
  `fecha_emision TIMESTAMPTZ`, `fecha_vencimiento DATE`. Campos obligatorios;
  unicidad `(condominio_id, periodo)`, cantidad y total positivos. Resumen histórico.
- `eventos_lote_outbox`: `id UUID PK` (event_id estable), `lote_id UUID UNIQUE FK
  RESTRICT`, `payload JSONB NOT NULL` (envelope), `publicado_en TIMESTAMPTZ NULL`.
  NULL indica publicación pendiente. Se guarda junto al lote.
- CON-11 crea `cuotas_mantenimiento` y completa `fk_aplicacion_saldo_cuota` con
  `ON DELETE RESTRICT`; `monto_total_exigible` conserva el bruto y `monto_pagado`
  incluye el crédito aplicado por CON-13. Migración `20261019_0006`.

---

## Extensión CON-32 / CON-34 / CON-36 / CON-37 / CON-73 — Notificaciones Persistentes (Migración `20261020_0010`)

### 8. Tabla: `notificaciones`
Almacena cada entrega lógica de notificación por destinatario, canal y operación de origen.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador único de la notificación. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id) ON DELETE RESTRICT` | Condominio propietario del aviso. |
| `departamento_id` | `UUID` | SÍ | `NULL` | `REFERENCES departamentos(id) ON DELETE RESTRICT` | Unidad inmobiliaria vinculada (si aplica). |
| `usuario_id` | `UUID` | SÍ | `NULL` | `REFERENCES usuarios(id) ON DELETE RESTRICT` | Usuario destinatario autorizado (si aplica). |
| `evento_id` | `UUID` | NO | - | - | Identificador del evento de dominio u operación que originó el aviso. |
| `tipo_evento` | `VARCHAR(60)` | NO | - | - | Nombre canónico del evento de origen (ej. `CuotasEmitidasEvent`). |
| `plantilla` | `VARCHAR(50)` | NO | - | - | Código de plantilla renderizada (ej. `NOTIF_EMISION_CUOTA`). |
| `origen_tipo` | `VARCHAR(20)` | NO | - | `CHECK (origen_tipo IN ('CUOTA', 'COMPROBANTE', 'RESERVA', 'COMUNICADO', 'USUARIO'))` | Tipo de entidad de origen. |
| `origen_id` | `UUID` | NO | - | - | UUID del recurso de origen (cuota, comprobante, reserva, comunicado). |
| `clave_deduplicacion` | `VARCHAR(255)` | NO | - | `UNIQUE (uq_notificacion_entrega_logica)` | Clave determinista de idempotencia lógica por entrega. |
| `canal` | `VARCHAR(10)` | NO | `'EMAIL'` | `CHECK (canal IN ('EMAIL', 'WHATSAPP', 'SMS', 'PUSH'))` | Canal de comunicación. |
| `destinatario` | `VARCHAR(150)` | NO | - | - | Correo electrónico o número de contacto. |
| `asunto` | `VARCHAR(200)` | SÍ | `NULL` | - | Asunto renderizado del mensaje. |
| `cuerpo` | `TEXT` | NO | - | - | Contenido renderizado del mensaje. |
| `contexto` | `JSONB` | NO | `'{}'::jsonb` | - | Variables utilizadas en el renderizado de la plantilla. |
| `estado` | `VARCHAR(20)` | NO | `'EN_COLA'` | `CHECK (estado IN ('EN_COLA', 'REINTENTANDO', 'ACEPTADO', 'ENTREGADO', 'FALLIDO_PERMANENTE'))` | Estado actual del ciclo de entrega. |
| `intentos` | `INTEGER` | NO | `0` | `CHECK (intentos BETWEEN 0 AND 4)` | Cantidad de intentos de despacho ya ejecutados en el ciclo vigente. |
| `ciclo` | `INTEGER` | NO | `1` | `CHECK (ciclo >= 1)` (`ck_notificacion_ciclo`) | Ciclo de entrega vigente; se incrementa en cada reenvío manual conservando el historial de intentos previos. |
| `proximo_intento_en` | `TIMESTAMPTZ` | SÍ | `NULL` | - | Marca temporal UTC en que la notificación es elegible para despacho. |
| `bloqueado_hasta` | `TIMESTAMPTZ` | SÍ | `NULL` | - | Expiración del arrendamiento tomado con `FOR UPDATE SKIP LOCKED`. |
| `bloqueado_por` | `VARCHAR(80)` | SÍ | `NULL` | - | Identificador del worker que posee el arrendamiento activo. |
| `transporte` | `VARCHAR(40)` | SÍ | `NULL` | - | Nombre del adaptador de transporte empleado (`SIMULADO`, `SMTP`). |
| `transporte_simulado` | `BOOLEAN` | SÍ | `NULL` | - | `TRUE` si el envío se realizó con transporte simulado (evidencia explícita). |
| `proveedor_message_id` | `VARCHAR(150)` | SÍ | `NULL` | - | Identificador devuelto por el proveedor externo o simulado. |
| `error_codigo` | `VARCHAR(40)` | SÍ | `NULL` | - | Último código de fallo registrado (`503`, `550`, `131026`, etc.). |
| `error_mensaje` | `TEXT` | SÍ | `NULL` | - | Detalle sanitizado del último error. |
| `creado_en` | `TIMESTAMPTZ` | NO | `NOW()` | - | Fecha UTC de registro. |
| `actualizado_en` | `TIMESTAMPTZ` | NO | `NOW()` | - | Fecha UTC de última actualización. |
| `aceptado_en` | `TIMESTAMPTZ` | SÍ | `NULL` | - | Fecha UTC en que el proveedor aceptó el envío. |
| `entregado_en` | `TIMESTAMPTZ` | SÍ | `NULL` | - | Fecha UTC de confirmación de entrega. |

Índices: `idx_notificaciones_pendientes` parcial sobre `(proximo_intento_en)` donde `estado IN ('EN_COLA', 'REINTENTANDO')`; `idx_notificaciones_condominio` `(condominio_id, creado_en)`; `idx_notificaciones_departamento` `(departamento_id, creado_en)`; `idx_notificaciones_origen` `(origen_tipo, origen_id)`.

### 9. Tabla: `notificacion_intentos`
Bitácora de intentos de envío por notificación (CON-37).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador del intento. |
| `notificacion_id` | `UUID` | NO | - | `REFERENCES notificaciones(id) ON DELETE CASCADE` | Notificación a la que pertenece el intento. |
| `ciclo` | `INTEGER` | NO | `1` | `UNIQUE (notificacion_id, ciclo, numero)` (`uq_intento_numero`) | Ciclo de entrega al que pertenece el intento (se incrementa con `reprogramar_manual`). |
| `numero` | `INTEGER` | NO | - | `CHECK (numero BETWEEN 1 AND 4)`; `UNIQUE (notificacion_id, ciclo, numero)` (`uq_intento_numero`) | Número correlativo del intento dentro del ciclo (1..4). |
| `worker_id` | `VARCHAR(80)` | NO | - | - | Identificador del worker que ejecutó el intento. |
| `transporte` | `VARCHAR(40)` | NO | - | - | Adaptador utilizado (`SIMULADO`, `SMTP`). |
| `transporte_simulado` | `BOOLEAN` | NO | - | - | Indica si el intento fue simulado. |
| `resultado` | `VARCHAR(20)` | NO | - | `CHECK (resultado IN ('ACEPTADO', 'FALLO_TEMPORAL', 'FALLO_DEFINITIVO'))` | Clasificación del resultado del intento. |
| `codigo` | `VARCHAR(40)` | SÍ | `NULL` | - | Código devuelto por el transporte en caso de fallo. |
| `detalle` | `TEXT` | SÍ | `NULL` | - | Detalle sanitizado del error. |
| `proveedor_message_id` | `VARCHAR(150)` | SÍ | `NULL` | - | Message-ID si fue aceptado. |
| `iniciado_en` | `TIMESTAMPTZ` | NO | - | - | Inicio UTC de la llamada al transporte. |
| `finalizado_en` | `TIMESTAMPTZ` | NO | - | - | Fin UTC de la llamada al transporte. |

### 10. Tabla: `eventos_consumidos`
Control de idempotencia de consumo de eventos de dominio por consumidor.

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `consumidor` | `VARCHAR(60)` | NO | - | `PRIMARY KEY (consumidor, event_id)` (`pk_eventos_consumidos`) | Nombre del consumidor lógico. |
| `event_id` | `UUID` | NO | - | `PRIMARY KEY (consumidor, event_id)` | UUID del evento consumido. |
| `event_type` | `VARCHAR(60)` | NO | - | - | Tipo de evento procesado. |
| `notificaciones_creadas` | `INTEGER` | NO | `0` | - | Cantidad de notificaciones generadas en la transacción. |
| `procesado_en` | `TIMESTAMPTZ` | NO | `NOW()` | - | Fecha UTC de procesamiento. |

### 11. Tabla: `alertas_administrativas`
Alertas operativas para la administración cuando una notificación alcanza `FALLIDO_PERMANENTE` (CON-37).

| Columna | Tipo de Dato | Nulo | Default | Restricciones / Checks | Descripción |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `UUID` | NO | `gen_random_uuid()` | `PRIMARY KEY` | Identificador de la alerta. |
| `condominio_id` | `UUID` | NO | - | `REFERENCES condominios(id) ON DELETE RESTRICT` | Condominio de la alerta. |
| `notificacion_id` | `UUID` | NO | - | `REFERENCES notificaciones(id) ON DELETE CASCADE` | Notificación fallida origen de la alerta. |
| `tipo` | `VARCHAR(40)` | NO | `'NOTIFICACION_FALLIDA'` | `UNIQUE (notificacion_id, tipo)` (`uq_alerta_notificacion_tipo`) | Categoría de la alerta. |
| `severidad` | `VARCHAR(10)` | NO | `'BAJA'` | `CHECK (severidad IN ('BAJA', 'MEDIA', 'ALTA'))` | Nivel de severidad. |
| `mensaje` | `TEXT` | NO | - | - | Mensaje operativo sin datos sensibles. |
| `creado_en` | `TIMESTAMPTZ` | NO | `NOW()` | - | Fecha UTC de creación. |
| `atendida_en` | `TIMESTAMPTZ` | SÍ | `NULL` | - | Fecha UTC de atención o reprogramación manual. |
| `atendida_por` | `UUID` | SÍ | `NULL` | - | Usuario administrador que atendió la alerta. |

Índice parcial `idx_alertas_abiertas` sobre `(condominio_id, creado_en)` donde `atendida_en IS NULL`.
