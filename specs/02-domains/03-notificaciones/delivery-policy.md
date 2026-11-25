# Política de Entrega y Reintentos de Notificaciones (Delivery Policy)

CON-73 persiste la cola antes de enviar. `intentos=0` significa que todavía no
se ejecutó el transporte; programar un reintento no incrementa este contador.
Cada intento efectivo conserva su ciclo, inicio, fin, error sanitizado y referencia.
El transporte SIMULADO solo acredita aceptación (ENVIADO), nunca ENTREGADO.
Una excepción del simulador es reintentable porque no existe un efecto externo.
Una excepción de PROVEEDOR se trata como aceptación incierta, nunca como rechazo seguro.
Un intento interrumpido con aceptación incierta se conserva para revisión sin
reenviarlo automáticamente. Véase
[persistencia integrada](../04-reservas/persistencia-sprint-2.md).

## 1. Esquema de Reintentos Exponenciales (Exponential Backoff)

Cuando un proveedor de transporte externo (ej. SendGrid o Meta WhatsApp API) devuelve un código de error temporal (`429 Too Many Requests`, `500 Internal Server Error`, `503 Service Unavailable`, o timeout de conexión TCP):

| Intento | Intervalo de Espera | Acción |
| :---: | :--- | :--- |
| **1** | Inmediato | Primer intento de envío síncrono/worker. |
| **2** | +2 minutos | Primer reintento con jitter aleatorio (+- 15s). |
| **3** | +10 minutos | Segundo reintento asíncrono. |
| **4 (Final)** | +30 minutos | Tercer y último reintento. |

---

## 2. Gestión de Errores Definitivos (Hard Bounces / Dead-Letter Queue)

Si el proveedor responde con un error definitivo:
- `550 User unknown / Mailbox does not exist` (Email rebotado).
- `131026 Message undeliverable` (WhatsApp no registrado o bloqueado).

El sistema aborta inmediatamente los reintentos:
1. Marca el estado como `FALLIDO_PERMANENTE`.
2. Registra el detalle del error en `notificaciones_logs`.
3. Crea una alerta administrativa persistente (`ERROR_DEFINITIVO`) en `notificaciones_alertas`, visible en Comunicados de la Junta: *"El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."*

## 3. Alertas Administrativas (CON-37)

Cada alerta se asocia a su origen (`origen_tipo` + `origen_id`, CON-84) y a su ciclo; es
idempotente por `(origen_tipo, origen_id, ciclo, tipo)`, de modo que un nuevo ciclo manual que vuelve a
fallar genera otra alerta. El mensaje no contiene contactos ni datos sensibles.

| Tipo | Origen |
| :--- | :--- |
| `ERROR_DEFINITIVO` | Rebote o error definitivo del proveedor (por ejemplo 550). |
| `INTENTOS_AGOTADOS` | Se agotaron los cuatro intentos de un fallo temporal. |
| `ACEPTACION_INCIERTA` | Intento interrumpido sin resultado conocido; no se reenvía solo. |
| `DESTINATARIO_INVALIDO` | El contacto del destinatario no es utilizable. |
| `PROVEEDOR_NO_CONFIGURADO` | Transporte de proveedor sin configuración. |
| `JOB_FALLO_DEFINITIVO` | Un job agotó sus reintentos (CON-84); origen `JOB`. |

Atención: `POST /api/v1/notificaciones/alertas/{alerta_id}/atender` (SuperAdmin o
Junta del contexto; el Auditor solo consulta con `GET /api/v1/notificaciones/alertas`)
es idempotente y registra la auditoría `NOTIFICACION_ALERTA_ATENDIDA`. El reenvío
manual con contacto corregido (`POST /api/v1/notificaciones/reenviar/{log_id}`)
atiende en la misma transacción las alertas abiertas de esa notificación.

## 3.1 Avisos con destinatario externo o contacto faltante (Sprint 4)

Contrato de CON-47 y CON-55; ver el [catálogo](../../03-contracts/events/domain-events-catalog.md).

- Un aviso a un contacto de proveedor sigue la misma política de reintentos (1, +2, +10
  y +30 min), de aceptación incierta y de alertas que cualquier otro correo.
- Un destinatario sin correo utilizable no se encola ni se inventa: la vista de Junta
  lo informa como `CONTACTO_FALTANTE`. Junta corrige el dato en el directorio o en el
  usuario; el aviso se genera con el flujo de reenvío, no con un duplicado automático.
- Un rebote definitivo conserva `ERROR_DEFINITIVO` y se muestra junto al ticket o
  bloqueo de origen; el mensaje de la alerta no contiene contactos.
- `ENVIADO` solo acredita aceptación del transporte. El resumen de un bloqueo o de
  una asignación nunca lo presenta como entregado.

## 4. Transporte Simulado Determinista

Mientras no exista proveedor real, el transporte `SIMULADO` interpreta el destinatario:
`usuario+falla{n}@dominio` responde 503 mientras los intentos acumulados sean menores
o iguales que `n`, y `usuario+rebote@dominio` responde 550. Solo acredita `ENVIADO`.
Entrega y resultados: [CON-32/34/36/37](../../../docs/sprints/CON-32-34-36-37-notificaciones.md).

## 5. Revalidación del recordatorio al despachar (CON-33)

Los recordatorios (`NOTIF_RECORDATORIO_PREVIO`, `NOTIF_CORTE_HOY`) se encolan con
`recordatorio_vencimiento` y `recordatorio_dias`, pero su elegibilidad se decide al
despachar, antes de registrar el intento y dentro de la misma transacción: el worker lee
la cuota con `FOR SHARE`. Un pago que ya modificó la cuota sin confirmar hace esperar al
worker, que al continuar relee el saldo vigente; así no se avisa una deuda saldada en
paralelo.

| Situación al despachar | Resultado |
| :--- | :--- |
| Política del condominio deshabilitada | `OMITIDO` / `RECORDATORIOS_DESHABILITADOS` |
| Cuota inexistente, sin saldo o con vencimiento distinto al encolado | `OMITIDO` / `RECORDATORIO_SIN_DEUDA` |
| Cuota con saldo vigente | Se re-renderiza el monto pendiente actual y se envía |

`OMITIDO` es terminal: no crea intento de transporte ni alerta, y no se inventa entrega.
