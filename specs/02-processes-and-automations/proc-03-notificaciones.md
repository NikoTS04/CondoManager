# PROC-03: Gestión de Notificaciones y Comunicaciones Automáticas

## 1. Ficha del Proceso
- **Identificador:** PROC-03
- **Responsable del Módulo:** **Alejandro**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos y Moras), PROC-04 (Reservas)

---

## 2. Propósito y Alcance del Proceso
Orquestar la entrega oportuna, automática y trazable de todas las notificaciones operativas y financieras dirigidas a residentes, propietarios y miembros de la Junta Directiva. 

El módulo gestiona plantillas dinámicas, políticas de reintentos ante fallos en proveedores de transporte (Email SMTP / API WhatsApp) y mantiene una bitácora auditable de cada mensaje despachado.

---

## 3. Disparadores y Catálogo de Notificaciones

| Código de Evento | Disparador / Momento | Canal Principal | Destinatario | Contenido Resumido |
| :--- | :--- | :--- | :--- | :--- |
| `NOTIF_EMISION_CUOTA` | Emisión mensual el día 1 | Email / App | Propietario / Inquilino | Recibo del mes, desglose de conceptos, fecha límite y cuentas bancarias. |
| `NOTIF_RECORDATORIO_PREVIO` | 3 días antes del vencimiento | Email / WhatsApp | Residente | Recordatorio amistoso de vencimiento próximo para evitar moras. |
| `NOTIF_CORTE_HOY` | Día del vencimiento (día 20) | Email / WhatsApp | Residente con saldo pendiente | Aviso de última fecha de pago oportuno. |
| `NOTIF_MORA_APLICADA` | Vencimiento de gracia (día 23) | Email | Residente deudor | Liquidación con recargo de mora y aviso de restricción de áreas comunes. |
| `NOTIF_PAGO_RECIBIDO` | Residente sube voucher | Email | Residente | Confirmación de recepción de comprobante en proceso de conciliación. |
| `NOTIF_PAGO_CONCILIADO` | Junta aprueba comprobante | Email / WhatsApp | Residente | Confirmación de pago exitoso, estado de cuenta actualizado y recibo en PDF. |
| `NOTIF_PAGO_RECHAZADO` | Junta rechaza comprobante | Email | Residente | Motivo del rechazo y enlace para adjuntar nuevo comprobante legible. |
| `NOTIF_RESTRICCION_LEVAN` | Liquidación total de deuda | Email / WhatsApp | Residente | Aviso de solvencia restablecida y rehabilitación de reservas de áreas comunes. |
| `NOTIF_RESERVA_CONFIRM` | Aprobación de área común | Email / WhatsApp | Residente solicitante | Confirmación de reserva, horario, aforo y normas de uso. |

---

## 4. Reglas de Negocio y Políticas de Entrega

### 4.1 Selección de Destinatarios
- Si el departamento está habitado por un inquilino:
  - Notificaciones operativas del día a día (cuotas, recordatorios, reservas, incidencias) se envían tanto al **Inquilino** como al **Propietario** (en copia informativa).
  - Notificaciones legales o de morosidad prolongada se dirigen con prioridad al **Propietario** como responsable legal de la unidad ante la junta.

### 4.2 Resiliencia y Reintentos
- Todo envío despachado por el worker asíncrono se registra inicialmente como `EN_COLA`.
- Si el proveedor de mensajería responde con error (ej. rebote de correo o API de mensajería ocupada):
  - Se activa la cola de reintentos exponenciales: 2 min, 10 min, 30 min.
  - Si el 3er reintento falla, pasa a `ESTADO_FALLIDO` y genera una alerta en el panel del Administrador para verificación manual del contacto.

---

## 5. Ciclo de Automatización

```
 [ Evento en Dominio ] ──▶ [ Despacho a Worker ] ──▶ [ Render Plantilla ] ──▶ [ Enviar por Proveedor ]
   (Ej. PagoConciliado)       (Asíncrono Celery)        (Datos dinámicos)             │
                                                                                      ▼
 [ Registro en Bitácora ] ◀────── [ Verificación ] ◀──────────────────── [ Respuesta del Proveedor ]
   (Estado, ID mensaje)            (¿Status 200 OK?)
```

---

## 6. Esquema del Registro de Notificación (`notificaciones_logs`)

```json
{
  "id": "c1f2e3d4-b5a6-4789-8012-3456789abcde",
  "condominio_id": "villa-bonita-3",
  "departamento_id": "dpto-204",
  "tipo_evento": "NOTIF_PAGO_CONCILIADO",
  "canal": "EMAIL",
  "destinatario": "propietario204@gmail.com",
  "asunto": "CondoManager: Su pago de mantenimiento ha sido validado con éxito",
  "payload_resumen": {
    "monto_pagado": 150.00,
    "recibo_nro": "REC-2026-09-0204",
    "saldo_actual": 0.00
  },
  "intentos": 1,
  "estado": "ENTREGADO",
  "fecha_envio": "2026-09-16T18:02:11Z",
  "proveedor_message_id": "smtp-msg-99882312"
}
```

---

## 7. Intervención Humana y Excepciones
- **Actualización de Datos de Contacto:** Si un correo rebota como inválido, el Administrador puede editar el correo en la ficha del residente y hacer clic en `Reenviar Notificación Pendiente`.
- **Comunicaciones Generales Masivas:** Permite al Administrador redactar un comunicado extraordinario (ej. corte programado de agua por Sedapal) y despacharlo a toda la comunidad con seguimiento de tasa de entrega.

---

## 8. Escenarios de Aceptación (BDD)
```gherkin
Escenario: Despacho automático de alerta preventiva 3 días antes de vencimiento
  Dado que la cuota del departamento 102 vence el día 20 del mes
  Y el departamento mantiene un saldo pendiente de S/ 160.00
  Cuando el reloj del sistema llega a las 08:00 del día 17 del mes
  Entonces el sistema genera y despacha una notificación de recordatorio preventivo al residente
  Y registra el envío con estado "ENTREGADO" en la bitácora de notificaciones.
```
