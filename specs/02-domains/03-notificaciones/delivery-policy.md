# Política de Entrega y Reintentos de Notificaciones (Delivery Policy)

Base de implementación CON-32/34/36/37/73: [CON-72](../../05-api/sprint-2-contratos.md#6-notificaciones--alejandro-persistencia-con-73). Esta política distingue persistencia, aceptación del transporte y confirmación de entrega.

## Estados y evidencia de entrega

| Estado | Significado |
|---|---|
| `EN_COLA` | Aviso lógico persistido, sin aceptación del proveedor. |
| `ENVIADO` | El proveedor aceptó el mensaje; todavía no hay evidencia de entrega. |
| `ENTREGADO` | Confirmación identificable y autenticada del proveedor, procesada idempotentemente. |
| `REINTENTANDO` | Fallo temporal, próximo intento persistido y presupuesto de intentos disponible. |
| `FALLIDO_PERMANENTE` | Fallo definitivo o presupuesto del ciclo agotado; requiere intervención trazada. |

El log identifica `transporte=SIMULADO|PROVEEDOR`. Un mock no acredita entrega y no debe marcar `ENTREGADO`; su aceptación simulada puede representarse como `ENVIADO`, expresamente identificada. Un HTTP 200/202 del transporte tampoco prueba entrega física.

## 1. Esquema de Reintentos Exponenciales (Exponential Backoff)

Cuando un proveedor de transporte externo (ej. SendGrid o Meta WhatsApp API) devuelve un código de error temporal (`429 Too Many Requests`, `500 Internal Server Error`, `503 Service Unavailable`, o timeout de conexión TCP):

| Intento | Intervalo de Espera | Acción |
| :---: | :--- | :--- |
| **1** | Inmediato | Primer intento de envío síncrono/worker. |
| **2** | +2 minutos | Primer reintento con jitter aleatorio (+- 15s). |
| **3** | +10 minutos | Segundo reintento asíncrono. |
| **4 (Final)** | +30 minutos | Tercer y último reintento. |

Los intervalos se miden desde el intento fallido anterior, no desde el primer envío. Persistir el instante elegido, incluido el jitter de -15 a +15 segundos del primer reintento. `intentos` cuenta ejecuciones efectivas del ciclo (0 en cola nueva, hasta 4); programar un intento no incrementa ese contador antes de ejecutarlo.

Conservar un aviso lógico y un historial de intentos por ciclo con inicio, fin, resultado, error y referencia del proveedor. El worker recupera pendientes tras reiniciar y reclama el aviso mediante lock/lease persistente para que dos procesos no lo envíen simultáneamente. La unicidad lógica sigue el [catálogo de eventos](../../03-contracts/events/domain-events-catalog.md).

No reenviar un aviso `ENVIADO` o `ENTREGADO`. Una respuesta ambigua/timeout se reconcilia mediante la referencia o clave idempotente del proveedor antes de reenviar; si el proveedor no permite deduplicar, registrar esa limitación sin afirmar entrega física exactamente una vez. La deduplicación local sí debe impedir avisos lógicos duplicados.

---

## 2. Gestión de Errores Definitivos (Hard Bounces / Dead-Letter Queue)

Si el proveedor responde con un error definitivo:
- `550 User unknown / Mailbox does not exist` (Email rebotado).
- `131026 Message undeliverable` (WhatsApp no registrado o bloqueado).

El sistema aborta inmediatamente los reintentos:
1. Marca el estado como `FALLIDO_PERMANENTE`.
2. Registra el detalle del error en `notificaciones_logs`.
3. Emite una alerta de baja severidad en el panel del Administrador: *"El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."*

## Reenvío administrativo

`POST /notificaciones/reenviar/{log_id}` valida rol y condominio. Una tarea ya en cola/programada se reutiliza; un aviso aceptado o entregado devuelve el mismo log sin otro envío. Un fallo agotado/definitivo sin corrección del contacto responde `409 INTENTOS_AGOTADOS`. Un nuevo destinatario autorizado puede iniciar otro ciclo, incrementando `ciclo`, reiniciando su contador en cero y conservando todos los intentos anteriores. No borrar ni sobrescribir el historial.

Errores y logs excluyen credenciales del proveedor y contenido sensible. La consulta de residentes se filtra por identidad destinataria y vínculos activos, no únicamente por conocer un UUID de departamento.
