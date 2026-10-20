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

| Evento de Entrada | Canal Principal | Canal Secundario | Plantilla | Variables Inyectadas |
| :--- | :---: | :---: | :--- | :--- |
| `CuotasEmitidasEvent` | Email | WhatsApp | `tpl_nueva_cuota` | `nombre`, `dpto`, `periodo`, `monto`, `vencimiento`, `cci_banco` |
| `RecordatorioPrevioEvent` (3 días) | WhatsApp | Email | `tpl_recordatorio_corte` | `nombre`, `dpto`, `monto_pendiente`, `fecha_corte` |
| `MoraAplicadaEvent` | Email | App Push | `tpl_mora_notificacion` | `nombre`, `dpto`, `monto_mora`, `nuevo_saldo`, `aviso_bloqueo_reservas` |
| `PagoConciliadoEvent` | Email | WhatsApp | `tpl_pago_exitoso` | `nombre`, `dpto`, `monto_abonado`, `saldo_restante`, `recibo_url` |
| `PagoRechazadoEvent` | Email | WhatsApp | `tpl_pago_rechazado` | `nombre`, `dpto`, `motivo_rechazo`, `enlace_subir_nuevo` |
| `ReservaConfirmadaEvent` | Email | WhatsApp | `tpl_reserva_aprobada` | `nombre`, `area`, `fecha`, `horario`, `normas_convivencia` |

---

## 4. Estructura de Datos del Log de Notificaciones

Cada intento de envío persiste un registro en `notificaciones_logs`:
- `id`: UUIDv4
- `condominio_id`: UUID
- `departamento_id`: UUID
- `tipo_evento`: String
- `canal`: Enum (`EMAIL`, `WHATSAPP`, `SMS`, `PUSH`)
- `destinatario`: String (correo o teléfono internacional `+51...`)
- `estado`: Enum (`EN_COLA`, `ENTREGADO`, `REINTENTANDO`, `FALLIDO_PERMANENTE`)
- `intentos`: Int (1 a 4)
- `proveedor_response_id`: String (Message-ID del proveedor)
- `error_mensaje`: Text nullable
