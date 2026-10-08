# Política de Entrega y Reintentos de Notificaciones (Delivery Policy)

## 1. Esquema de Reintentos Exponenciales (Exponential Backoff)

Cuando un proveedor de transporte externo (ej. SendGrid o Meta WhatsApp API) devuelve un código de error temporal (`429 Too Many Requests`, `500 Internal Server Error`, `503 Service Unavailable`, o timeout de conexión TCP):

| Intento | Intervalo de Espera | Acción |
| :---: | :--- | :--- |
| **1** | Inmediato | Primer intento de envío síncrono/worker. |
| **2** | +2 minutos | Primer reintento con jitter aleatorio (+- 15s). |
| **3** | +10 minutos | Segundo reintento asíncrono. |
| **4 (Final)** | +30 minutos | Tercer y último reintento. |

### Ejecución de un reintento programado

- Solo se despacha un registro en estado `REINTENTANDO` cuya fecha `proximo_reintento` haya llegado. Los demás registros permanecen sin cambios.
- El contador existente identifica el intento programado; no se reinicia como en un reenvío manual.
- Si el envío resulta exitoso, pasa a `ENTREGADO`, registra el identificador del proveedor y limpia el error y la fecha de reintento. No vuelve a enviarse en una ejecución posterior.
- Si falla, aplica la misma política de errores temporales o definitivos. Una excepción del transporte se considera un fallo temporal.
- Este paso del servicio no incorpora todavía un worker, persistencia ni protección frente a ejecuciones concurrentes.

---

## 2. Gestión de Errores Definitivos (Hard Bounces / Dead-Letter Queue)

Si el proveedor responde con un error definitivo:
- `550 User unknown / Mailbox does not exist` (Email rebotado).
- `131026 Message undeliverable` (WhatsApp no registrado o bloqueado).

El sistema aborta inmediatamente los reintentos:
1. Marca el estado como `FALLIDO_PERMANENTE`.
2. Registra el detalle del error en `notificaciones_logs`.
3. Emite una alerta de baja severidad en el panel del Administrador: *"El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."*
