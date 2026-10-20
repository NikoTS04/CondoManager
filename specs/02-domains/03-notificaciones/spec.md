# Dominio 03: Notificaciones y Comunicaciones Multicanal (Alejandro)

## 1. Ficha del Dominio
- **Identificador:** DOM-03 / PROC-03
- **Responsable:** **Alejandro**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/notificaciones/`

---

## 2. Propósito y Límites del Dominio
El dominio de Notificaciones es responsable de:
1. Escuchar eventos asíncronos del bus de eventos (`CuotasEmitidasEvent`, `PagoConciliadoEvent`, `MoraAplicadaEvent`, `ReservaConfirmadaEvent`).
2. Renderizar plantillas dinámicas personalizadas por residente y departamento.
3. Despachar mensajes a través de los canales configurados (Email SMTP / AWS SES y WhatsApp Cloud API).
4. Administrar la política de resiliencia y reintentos ante fallas externas (`delivery-policy.md`).
5. Mantener la bitácora auditable de entregas (`notificaciones_logs`).

---

## 3. Matriz de Eventos y Plantillas

Contrato vigente del Sprint 2: [CON-72](../../05-api/sprint-2-contratos.md#6-notificaciones--alejandro-persistencia-con-73), [catálogo versionado](../../03-contracts/events/domain-events-catalog.md) y [política de entrega](delivery-policy.md). Los eventos ajenos a ese catálogo del sprint se conservan como alcance futuro, sin agregar dependencias nuevas a las historias comprometidas.

| Evento de Entrada | Canal Principal | Canal Secundario | Plantilla | Variables Inyectadas |
| :--- | :---: | :---: | :--- | :--- |
| `CuotasEmitidasEvent` | Email | WhatsApp | `tpl_nueva_cuota` | `nombre`, `dpto`, `periodo`, `monto`, `vencimiento`, `cci_banco` |
| `RecordatorioPrevioEvent` (3 días) | WhatsApp | Email | `tpl_recordatorio_corte` | `nombre`, `dpto`, `monto_pendiente`, `fecha_corte` |
| `MoraAplicadaEvent` | Email | App Push | `tpl_mora_notificacion` | `nombre`, `dpto`, `monto_mora`, `nuevo_saldo`, `aviso_bloqueo_reservas` |
| `PagoConciliadoEvent` | Email | WhatsApp | `tpl_pago_exitoso` | `nombre`, `dpto`, `monto_abonado`, `saldo_restante`, `recibo_url` |
| `PagoReportadoEvent` | Email | WhatsApp | Confirmación de recepción | Comprobante persistido y estado en revisión; no cancela deuda. |
| `PagoRevisadoEvent` | Email | WhatsApp | Resultado observado o rechazado | `nombre`, `dpto`, `motivo_rechazo`, instrucciones según estado. |
| `ReservaConfirmadaEvent` | Email | WhatsApp | `tpl_reserva_aprobada` | `nombre`, `area`, `fecha`, `horario`, `normas_convivencia` |
| `ReservaCanceladaEvent` | Email | WhatsApp | Confirmación de cancelación | Reserva, horario liberado y estado real del ajuste económico. |

---

## 4. Estructura de Datos del Log de Notificaciones

Cada aviso lógico conserva un registro en `notificaciones_logs` y un historial separado de ciclos e intentos. El resumen del contrato objetivo incluye:
- `id`: UUIDv4
- `condominio_id`: UUID
- `departamento_id`: UUID
- `tipo_evento`: String
- `canal`: Enum (`EMAIL`, `WHATSAPP`, `SMS`, `PUSH`)
- `destinatario`: String (correo o teléfono internacional `+51...`)
- `usuario_destinatario_id`: UUID del usuario destinatario, o nulo en una comunicación administrativa externa autorizada.
- `evento_id`: UUID del evento de origen o nulo en despacho administrativo manual.
- `estado`: Enum (`EN_COLA`, `ENVIADO`, `ENTREGADO`, `REINTENTANDO`, `FALLIDO_PERMANENTE`).
- `ciclo`: Int >= 1; `intentos`: Int (0 a 4 por ciclo).
- `transporte`: `SIMULADO` o `PROVEEDOR`.
- `proximo_reintento`: timestamp persistido o nulo.
- `proveedor_message_id`: String nullable (Message-ID del proveedor).
- `error_mensaje`: Text nullable
