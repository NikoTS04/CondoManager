# PROC-03: Gestión de Notificaciones y Comunicaciones Automáticas

## 1. Ficha del Proceso
- **Identificador:** PROC-03
- **Responsable del Módulo:** **Alejandro**
- **Estado:** Implementado (Sprint 2 — CON-32, CON-34, CON-36, CON-37)
- **Versión:** 2.1 (Alineado con CON-70 y CON-72)
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos y Moras), PROC-04 (Reservas), PROC-05 (Usuarios)

---

## 2. Propósito y Alcance del Proceso
Orquestar la generación idempotente, persistente y trazable de todas las notificaciones operativas y financieras dirigidas a residentes con vínculo activo (`PROPIETARIO_TITULAR`, `COPROPIETARIO`, `INQUILINO`), así como comunicados institucionales emitidos por la Junta Directiva.

El módulo separa estrictamente:
1. **Registro transaccional (`EN_COLA`)** al consumir eventos confirmados desde `condomanager:domain-events`.
2. **Despacho asíncrono (`ENVIADO` / `ENTREGADO` / `REINTENTANDO` / `FALLIDO_PERMANENTE`)** gobernado por el motor de entrega de CON-37 con arrendamiento en PostgreSQL (`FOR UPDATE SKIP LOCKED`).

> **Alcance diferido (CON-04):** La invitación y verificación por correo electrónico de nuevos usuarios queda diferida para una evolución posterior; en el Sprint 2 el alta de cuentas utiliza habilitación manual por `SUPERADMIN`.

---

## 3. Disparadores, Eventos y Catálogo de Plantillas

| Plantilla | Eventos de Dominio Soportados | Origen (`origen_tipo`) | Variables Requeridas (sin defaults financieros) | Clave de Deduplicación Lógica |
| :--- | :--- | :--- | :--- | :--- |
| `NOTIF_EMISION_CUOTA` | `CuotasEmitidasEvent` | `CUOTA` | `dpto`, `periodo`, `monto`, `vencimiento` (+ `monto_pendiente`, `cci_banco`) | `CUOTA:{cuota_id}:NOTIF_EMISION_CUOTA:{canal}:{usuario_id}` |
| `NOTIF_PAGO_RECIBIDO` | `PagoReportadoEvent` (CON-70 y CON-72 v1) | `COMPROBANTE` | `dpto`, `monto` (`banco`, `numero_operacion` leídos de `comprobantes_pago` si existen) | `COMPROBANTE:{id}:NOTIF_PAGO_RECIBIDO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_CONCILIADO` | `PagoConciliadoEvent` (CON-70 y CON-72 v1) | `COMPROBANTE` | `dpto`, `monto_abonado` (`monto_imputado`), `saldo_restante` (`nuevo_saldo_departamento`) | `COMPROBANTE:{id}:NOTIF_PAGO_CONCILIADO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_OBSERVADO` | `PagoObservadoEvent` (CON-70) / `PagoRevisadoEvent` (`OBSERVADO`, CON-72 v1) | `COMPROBANTE` | `dpto`, `motivo` (+ `instrucciones`) | `COMPROBANTE:{id}:NOTIF_PAGO_OBSERVADO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_RECHAZADO` | `PagoRechazadoEvent` (CON-70) / `PagoRevisadoEvent` (`RECHAZADO`, CON-72 v1) | `COMPROBANTE` | `dpto`, `motivo_rechazo` (`motivo`) (+ `instrucciones`) | `COMPROBANTE:{id}:NOTIF_PAGO_RECHAZADO:{canal}:{usuario_id}` |
| `NOTIF_RESERVA_CONFIRMADA` | `ReservaConfirmadaEvent` (CON-72 v1) | `RESERVA` | `dpto`, `area`, `fecha`, `horario`, `costo` (`moneda`, `normas_convivencia` opcional) | `RESERVA:{id}:NOTIF_RESERVA_CONFIRMADA:{canal}:{usuario_id}` |
| `NOTIF_RESERVA_CANCELADA` | `ReservaCanceladaEvent` (CON-72 v1) | `RESERVA` | `dpto`, `area`, `fecha`, `horario`, `motivo`, `ajuste_economico` (`NO_APLICA`/`PENDIENTE`/`APLICADO`) | `RESERVA:{id}:NOTIF_RESERVA_CANCELADA:{canal}:{usuario_id}` |
| `NOTIF_MORA_APLICADA` | `MoraAplicadaEvent` | `CUOTA` | `dpto`, `monto_mora`, `nuevo_saldo` | `CUOTA:{id}:NOTIF_MORA_APLICADA:{canal}:{usuario_id}` |
| `NOTIF_RECORDATORIO_PREVIO` | `RecordatorioPrevioEvent` | `CUOTA` | `dpto`, `fecha_corte`, `monto_pendiente` | `CUOTA:{id}:NOTIF_RECORDATORIO_PREVIO:{canal}:{usuario_id}` |
| `NOTIF_COMUNICADO_GENERAL` | Comunicado administrativo | `COMUNICADO` | `titulo`, `mensaje` | `COMUNICADO:{id}:{canal}:{usuario_id}` |

---

## 4. Reglas de Negocio y Garantías de Integridad

### 4.1 Resolución de Destinatarios y Aislamiento por Unidad
- Se consultan únicamente vínculos activos (`usuario_departamentos.es_activo IS TRUE`) asociados a cuentas habilitadas (`usuarios.esta_activo IS TRUE`) del `departamento_id` y `condominio_id` del evento.
- Si una unidad no posee destinatarios activos, el consumidor no crea notificaciones y deja constancia en el log operativo sin abortar el lote.
- Nunca se envían datos de una unidad a usuarios de otro departamento ni de otro condominio.

### 4.2 Lectura de Datos Persistidos y Prohibición de Saldos Inventados
- **CON-32 (`CuotasEmitidasEvent`):** el consumidor lee las filas de `cuotas_mantenimiento` del `periodo` y `condominio_id` emitidos, junto con el número de departamento y el bloque (`edificios.nombre_bloque`). Nunca modifica los importes emitidos.
- **CON-34 (`PagoReportadoEvent`, `PagoConciliadoEvent`, `PagoObservadoEvent`, `PagoRechazadoEvent`, `PagoRevisadoEvent`):** el consumidor prioriza la lectura de `comprobantes_pago` y `revisiones_pago` en PostgreSQL (comprobando su existencia con `to_regclass`) sobre el payload del evento. En conciliación (`APROBADO`), exige `monto_imputado` y `nuevo_saldo_departamento` explícitos desde la revisión persistida o el contrato del evento, jamás inventando `0.00`. En observación o rechazo exige el motivo persistido o del evento.
- **CON-36 (`ReservaConfirmadaEvent` / `ReservaCanceladaEvent`):** valida el departamento de la reserva en el condominio, respeta la moneda (`PEN`/`USD`), considera opcionales las normas de uso (`normas_uso`, dado que CON-39 no define columna de normas) y formatea el estado real del ajuste económico (`NO_APLICA`, `PENDIENTE`, `APLICADO`).

### 4.3 Consumo Transaccional, DLQ y Worker de Eventos
- El worker `python -m src.modules.notificaciones.worker` consume el stream `condomanager:domain-events` en el grupo `notificaciones-workers` (`XREADGROUP`), recupera mensajes pendientes tras reinicios (`XAUTOCLAIM` y lectura de `0`) y confirma (`XACK`) **únicamente después del commit** en PostgreSQL.
- Eventos de otros dominios se confirman sin efecto; eventos que incumplen su contrato revierten la transacción, se registran en `condomanager:domain-events:dlq` y se confirman.
- En paralelo ejecuta periódicamente `entrega.despachar_pendientes(...)` para enviar las notificaciones en estado `EN_COLA` o `REINTENTANDO`.
