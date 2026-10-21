# Dominio 03: Notificaciones y Comunicaciones Multicanal (Alejandro)

## 1. Ficha del Dominio
- **Identificador:** DOM-03 / PROC-03
- **Responsable:** **Alejandro**
- **Estado:** Aprobado para Implementación (Sprint 2 — CON-32, CON-34, CON-36, CON-37, CON-73)
- **Versión:** 2.2 (Persistencia transaccional, ciclos de reenvío y protección de arrendamiento)
- **Módulos de Código:** `src/modules/notificaciones/`

---

## 2. Propósito y Límites del Dominio
El dominio de Notificaciones es responsable de:
1. Consumir de forma idempotente eventos confirmados del bus de eventos (`CuotasEmitidasEvent`, `PagoReportadoEvent`, `PagoRevisadoEvent`, `ReservaConfirmadaEvent`, `ReservaCanceladaEvent`) registrando cada evento en `eventos_consumidos`.
2. Resolver destinatarios autorizados a partir de vínculos activos (`usuario_departamentos.es_activo`) y cuentas activas (`usuarios.esta_activo`), protegiendo el aislamiento entre departamentos y condominios.
3. Renderizar plantillas dinámicas validando las variables requeridas por contrato y registrar la entrega lógica en `notificaciones` (`uq_notificacion_entrega_logica` sobre `clave_deduplicacion`) en estado `EN_COLA` dentro de la misma transacción del consumidor, sin realizar envíos externos dentro de la transacción.
4. Despachar mensajes fuera de la transacción mediante adaptadores de transporte (`TransporteSimulado` por defecto, identificado con `transporte_simulado = true`, o `TransporteSMTP` real configurado por entorno).
5. Distinguir explícitamente entre registro persistido (`EN_COLA`), envío aceptado por el proveedor (`ACEPTADO`), espera de reintento (`REINTENTANDO`), entrega confirmada (`ENTREGADO`) y fallo terminal (`FALLIDO_PERMANENTE`).
6. Aplicar la política de resiliencia, clasificación de errores, arrendamiento entre workers (`FOR UPDATE SKIP LOCKED`), protección de vencimiento de arrendamiento antes de enviar, reenvío manual por ciclos (`ciclo`) conservando el historial en `notificacion_intentos`, y alertas administrativas (`delivery-policy.md`).

> **Alcance diferido:** La invitación y verificación por correo del alta de usuarios (CON-04) queda diferida para una evolución posterior.

---

## 3. Matriz de Eventos y Plantillas

| Evento de Entrada | Origen | Canal Principal | Plantilla | Clave de Deduplicación | Variables Requeridas |
| :--- | :---: | :---: | :--- | :--- | :--- |
| `CuotasEmitidasEvent` | `CUOTA` | `EMAIL` | `NOTIF_EMISION_CUOTA` | `CUOTA:{cuota_id}:NOTIF_EMISION_CUOTA:{canal}:{usuario_id}` | `nombre`, `dpto`, `periodo`, `monto`, `vencimiento`, `cci_banco` |
| `PagoReportadoEvent` | `COMPROBANTE` | `EMAIL` | `NOTIF_PAGO_RECIBIDO` | `COMPROBANTE:{id}:NOTIF_PAGO_RECIBIDO:{canal}:{usuario_id}` | `nombre`, `dpto`, `monto`, `numero_operacion`, `banco` |
| `PagoRevisadoEvent` (`APROBADO`) | `COMPROBANTE` | `EMAIL` | `NOTIF_PAGO_CONCILIADO` | `COMPROBANTE:{id}:NOTIF_PAGO_CONCILIADO:{canal}:{usuario_id}` | `nombre`, `dpto`, `monto_abonado`, `saldo_restante`, `recibo_url` |
| `PagoRevisadoEvent` (`OBSERVADO`) | `COMPROBANTE` | `EMAIL` | `NOTIF_PAGO_OBSERVADO` | `COMPROBANTE:{id}:NOTIF_PAGO_OBSERVADO:{canal}:{usuario_id}` | `nombre`, `dpto`, `motivo_rechazo`, `enlace_subir_nuevo` |
| `PagoRevisadoEvent` (`RECHAZADO`) | `COMPROBANTE` | `EMAIL` | `NOTIF_PAGO_RECHAZADO` | `COMPROBANTE:{id}:NOTIF_PAGO_RECHAZADO:{canal}:{usuario_id}` | `nombre`, `dpto`, `motivo_rechazo`, `enlace_subir_nuevo` |
| `MoraAplicadaEvent` | `CUOTA` | `EMAIL` | `NOTIF_MORA_APLICADA` | `CUOTA:{cuota_id}:NOTIF_MORA_APLICADA:{canal}:{usuario_id}` | `nombre`, `dpto`, `monto_mora`, `nuevo_saldo`, `aviso_bloqueo_reservas` |
| `ReservaConfirmadaEvent` | `RESERVA` | `EMAIL` | `NOTIF_RESERVA_CONFIRMADA` | `RESERVA:{id}:NOTIF_RESERVA_CONFIRMADA:{canal}:{usuario_id}` | `nombre`, `dpto`, `area`, `fecha`, `horario`, `normas_convivencia` |
| `ReservaCanceladaEvent` | `RESERVA` | `EMAIL` | `NOTIF_RESERVA_CANCELADA` | `RESERVA:{id}:NOTIF_RESERVA_CANCELADA:{canal}:{usuario_id}` | `nombre`, `dpto`, `area`, `fecha`, `horario`, `motivo` |
| Comunicado Masivo API | `COMUNICADO` | `EMAIL` | `NOTIF_COMUNICADO_GENERAL` | `COMUNICADO:{id}:{canal}:{usuario_id}` | `titulo`, `mensaje`, `remitente` |

---

## 4. Modelo Persistente de Datos (CON-73 / Migración `20261020_0010`)

### 4.1 Tabla `notificaciones`
Representa cada entrega lógica única por destinatario y operación:
- `id`: `UUID` PK.
- `condominio_id`, `departamento_id` (nullable), `usuario_id` (nullable): contexto de autorización y aislamiento.
- `evento_id`, `tipo_evento`, `plantilla`, `origen_tipo` (`CUOTA`, `COMPROBANTE`, `RESERVA`, `COMUNICADO`, `USUARIO`), `origen_id`.
- `clave_deduplicacion`: `VARCHAR(255)` con restricción única `uq_notificacion_entrega_logica`.
- `canal`: `EMAIL`, `WHATSAPP`, `SMS`, `PUSH`.
- `destinatario`, `asunto`, `cuerpo`, `contexto` (`JSONB`).
- `estado`: `EN_COLA`, `REINTENTANDO`, `ACEPTADO`, `ENTREGADO`, `FALLIDO_PERMANENTE`.
- `intentos`: entero entre `0` y `4` (intentos ya ejecutados en el ciclo vigente).
- `ciclo`: entero `>= 1` (`DEFAULT 1`, `ck_notificacion_ciclo`). Cada reprogramación manual (`reprogramar_manual`) incrementa `ciclo` en 1 y reinicia `intentos = 0` sin borrar el historial previo.
- `proximo_intento_en`, `bloqueado_hasta`, `bloqueado_por`: planificación de backoff y arrendamiento de worker.
- `transporte`, `transporte_simulado`, `proveedor_message_id`, `error_codigo`, `error_mensaje`.
- `creado_en`, `actualizado_en`, `aceptado_en`, `entregado_en`: marcas de tiempo UTC.

### 4.2 Tabla `notificacion_intentos`
Bitácora inmutable de cada intento de despacho por ciclo (`ciclo >= 1`, `numero` 1..4):
- `notificacion_id` (`FK CASCADE`), `ciclo` (`INTEGER DEFAULT 1`), `numero` (`1..4`), único por `(notificacion_id, ciclo, numero)` en `uq_intento_numero`.
- `worker_id`, `transporte`, `transporte_simulado`.
- `resultado`: `ACEPTADO`, `FALLO_TEMPORAL`, `FALLO_DEFINITIVO`.
- `codigo`, `detalle`, `proveedor_message_id`, `iniciado_en`, `finalizado_en`.

### 4.3 Tabla `eventos_consumidos`
Idempotencia de consumo de eventos por consumidor (`PRIMARY KEY (consumidor, event_id)`).

### 4.4 Tabla `alertas_administrativas`
Alertas de baja severidad generadas al alcanzar `FALLIDO_PERMANENTE`, únicas por `(notificacion_id, tipo)` (`uq_alerta_notificacion_tipo`), sin exponer datos sensibles.
