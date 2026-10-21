# PROC-03: Gestión de Notificaciones y Comunicaciones Automáticas

## 1. Ficha del Proceso
- **Identificador:** PROC-03
- **Responsable del Módulo:** **Alejandro**
- **Estado:** Implementado (Sprint 2 — CON-32, CON-34, CON-36, CON-37)
- **Versión:** 2.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos y Moras), PROC-04 (Reservas), PROC-05 (Usuarios)

---

## 2. Propósito y Alcance del Proceso
Orquestar la generación idempotente, persistente y trazable de todas las notificaciones operativas y financieras dirigidas a residentes con vínculo activo, propietarios, copropietarios e inquilinos, así como comunicados institucionales emitidos por la Junta Directiva.

El módulo separa estrictamente:
1. **Registro transaccional (`EN_COLA`)** al consumir eventos confirmados desde `condomanager:domain-events`.
2. **Despacho asíncrono (`ACEPTADO` / `ENTREGADO` / `REINTENTANDO` / `FALLIDO_PERMANENTE`)** gobernado por el motor de entrega de CON-37 con arrendamiento en PostgreSQL (`FOR UPDATE SKIP LOCKED`).

> **Alcance diferido (CON-04):** La invitación y verificación por correo electrónico de nuevos usuarios queda diferida para una evolución posterior; en el Sprint 2 el alta de cuentas utiliza habilitación manual por `SUPERADMIN`.

---

## 3. Disparadores, Eventos y Catálogo de Plantillas

| Plantilla | Evento de Dominio | Origen (`origen_tipo`) | Variables Requeridas (sin defaults financieros) | Clave de Deduplicación Lógica |
| :--- | :--- | :--- | :--- | :--- |
| `NOTIF_EMISION_CUOTA` | `CuotasEmitidasEvent` | `CUOTA` | `dpto`, `periodo`, `monto`, `vencimiento` (+ `monto_pendiente`, `cci_banco`) | `CUOTA:{cuota_id}:NOTIF_EMISION_CUOTA:{canal}:{usuario_id}` |
| `NOTIF_PAGO_RECIBIDO` | `PagoReportadoEvent` | `COMPROBANTE` | `dpto`, `monto`, `numero_operacion`, `banco` | `COMPROBANTE:{id}:NOTIF_PAGO_RECIBIDO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_CONCILIADO` | `PagoRevisadoEvent` (`APROBADO`) / `PagoConciliadoEvent` | `COMPROBANTE` | `dpto`, `monto_abonado` (`monto_aplicado`), `saldo_restante` (`saldo_resultante`) | `COMPROBANTE:{id}:NOTIF_PAGO_CONCILIADO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_OBSERVADO` | `PagoRevisadoEvent` (`OBSERVADO`) | `COMPROBANTE` | `dpto`, `motivo`, `instrucciones` | `COMPROBANTE:{id}:NOTIF_PAGO_OBSERVADO:{canal}:{usuario_id}` |
| `NOTIF_PAGO_RECHAZADO` | `PagoRevisadoEvent` (`RECHAZADO`) | `COMPROBANTE` | `dpto`, `motivo_rechazo` (`motivo`), `instrucciones` | `COMPROBANTE:{id}:NOTIF_PAGO_RECHAZADO:{canal}:{usuario_id}` |
| `NOTIF_RESERVA_CONFIRMADA` | `ReservaConfirmadaEvent` | `RESERVA` | `dpto`, `area`, `fecha`, `horario`, `costo`, `normas_convivencia` | `RESERVA:{id}:NOTIF_RESERVA_CONFIRMADA:{canal}:{usuario_id}` |
| `NOTIF_RESERVA_CANCELADA` | `ReservaCanceladaEvent` | `RESERVA` | `dpto`, `area`, `fecha`, `horario`, `motivo` (+ `ajuste_economico`) | `RESERVA:{id}:NOTIF_RESERVA_CANCELADA:{canal}:{usuario_id}` |
| `NOTIF_MORA_APLICADA` | `MoraAplicadaEvent` | `CUOTA` | `dpto`, `monto_mora`, `nuevo_saldo` | `CUOTA:{id}:NOTIF_MORA_APLICADA:{canal}:{usuario_id}` |
| `NOTIF_RECORDATORIO_PREVIO` | `RecordatorioPrevioEvent` | `CUOTA` | `dpto`, `fecha_corte`, `monto_pendiente` | `CUOTA:{id}:NOTIF_RECORDATORIO_PREVIO:{canal}:{usuario_id}` |
| `NOTIF_COMUNICADO_GENERAL` | Comunicado administrativo | `COMUNICADO` | `titulo`, `mensaje` | `COMUNICADO:{id}:{canal}:{usuario_id}` |

---

## 4. Reglas de Negocio y Garantías de Integridad

### 4.1 Resolución de Destinatarios y Aislamiento por Unidad
- Se consultan únicamente vínculos activos (`usuario_departamentos.es_activo IS TRUE`) asociados a cuentas habilitadas (`usuarios.esta_activo IS TRUE`) del `departamento_id` y `condominio_id` del evento.
- Tanto titulares (`PROPIETARIO_TITULAR`, `COPROPIETARIO`) como residentes (`INQUILINO`) con vínculo activo reciben los avisos operativos de su departamento.
- Si una unidad no posee destinatarios activos, el consumidor no crea notificaciones y deja constancia en el log operativo sin abortar el lote.
- Nunca se envían datos de una unidad a usuarios de otro departamento ni de otro condominio.

### 4.2 Lectura de Datos Persistidos y Prohibición de Saldos Inventados
- **CON-32 (`CuotasEmitidasEvent`):** el consumidor lee las filas de `cuotas_mantenimiento` del `periodo` y `condominio_id` emitidos, junto con el número de departamento y el bloque (`edificios.nombre_bloque`). Nunca modifica los importes emitidos. Los medios de pago se toman del payload/configuración (`NOTIFICACIONES_MEDIOS_PAGO` o cuenta recaudadora configurada).
- **CON-34 (`PagoReportadoEvent` / `PagoRevisadoEvent`):** el consumidor verifica si existe `comprobantes_pago` mediante `to_regclass('comprobantes_pago')` sin romper la transacción activa; si existe la fila, contrasta y completa los datos desde la base de datos. En `APROBADO` exige `monto_aplicado` y `saldo_resultante` explícitos (jamás usa `0.00` por defecto). En `OBSERVADO` y `RECHAZADO` exige `motivo` e `instrucciones` de subsanación.
- **CON-36 (`ReservaConfirmadaEvent` / `ReservaCanceladaEvent`):** valida el departamento de la reserva en el condominio y renderiza área, fecha, horario, costo/ajuste económico y normas o motivo de cancelación.

### 4.3 Consumo Transaccional y Worker de Eventos
- El worker `python -m src.modules.notificaciones.worker` consume el stream `condomanager:domain-events` mediante grupo de consumidores (`XREADGROUP`), recupera mensajes pendientes tras reinicios (`XAUTOCLAIM` y lectura de `0`) y confirma (`XACK`) **únicamente después del commit** en PostgreSQL.
- En paralelo ejecuta periódicamente `entrega.despachar_pendientes(...)` para enviar las notificaciones en estado `EN_COLA` o `REINTENTANDO`.

---

## 5. Ciclo de Automatización

```text
 [ Evento Confirmado ] ──▶ [ Redis Stream ] ──▶ [ Consumidor Transaccional ]
   (Outbox / Dominio)      (XREADGROUP)         1. marcar_evento_consumido
                                                2. resolver_destinatarios_departamento
                                                3. registrar_notificacion (EN_COLA)
                                                4. cerrar_evento_consumido + COMMIT
                                                5. XACK en Redis
                                                           │
                                                           ▼
 [ Alerta Admin / Bitácora ] ◀── [ Motor Entrega CON-37 ] ◀┘
   (ACEPTADO / ENTREGADO /        (FOR UPDATE SKIP LOCKED,
    FALLIDO_PERMANENTE)            1 intento + 3 reintentos: 2m, 10m, 30m)
```

---

## 6. Intervención Humana y Excepciones
- **Actualización de Datos de Contacto y Reenvío Manual:** cuando una notificación alcanza `FALLIDO_PERMANENTE`, se genera una alerta administrativa en `alertas_administrativas` y la Junta Directiva puede reprogramar el envío corrigiendo el destinatario.
- **Comunicaciones Generales Masivas:** permite a la Junta Directiva registrar un comunicado oficial para todos los destinatarios con vínculo activo del condominio (`EN_COLA`), cuyo despacho ejecuta el worker.
