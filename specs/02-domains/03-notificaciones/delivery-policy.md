# Política de Entrega y Reintentos de Notificaciones (Delivery Policy)

CON-73 persiste la cola antes de enviar. `intentos=0` significa que todavía no
se ejecutó el transporte; programar un reintento no incrementa este contador.
Cada intento efectivo conserva su ciclo, inicio, fin, error sanitizado y referencia.
El transporte SIMULADO solo acredita aceptación (ENVIADO), nunca ENTREGADO.
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

Cada alerta se asocia a una notificación y a su ciclo; es idempotente por
`(notificacion_id, ciclo, tipo)`, de modo que un nuevo ciclo manual que vuelve a
fallar genera otra alerta. El mensaje no contiene contactos ni datos sensibles.

| Tipo | Origen |
| :--- | :--- |
| `ERROR_DEFINITIVO` | Rebote o error definitivo del proveedor (por ejemplo 550). |
| `INTENTOS_AGOTADOS` | Se agotaron los cuatro intentos de un fallo temporal. |
| `ACEPTACION_INCIERTA` | Intento interrumpido sin resultado conocido; no se reenvía solo. |
| `DESTINATARIO_INVALIDO` | El contacto del destinatario no es utilizable. |
| `PROVEEDOR_NO_CONFIGURADO` | Transporte de proveedor sin configuración. |

Atención: `POST /api/v1/notificaciones/alertas/{alerta_id}/atender` (SuperAdmin o
Junta del contexto; el Auditor solo consulta con `GET /api/v1/notificaciones/alertas`)
es idempotente y registra la auditoría `NOTIFICACION_ALERTA_ATENDIDA`. El reenvío
manual con contacto corregido (`POST /api/v1/notificaciones/reenviar/{log_id}`)
atiende en la misma transacción las alertas abiertas de esa notificación.

## 4. Transporte Simulado Determinista

Con `EMAIL_TRANSPORTE=SIMULADO` (y siempre para WhatsApp, SMS y Push), el transporte `SIMULADO` interpreta el destinatario:
`usuario+falla{n}@dominio` responde 503 mientras los intentos acumulados sean menores
o iguales que `n`, y `usuario+rebote@dominio` responde 550. Solo acredita `ENVIADO`.
Entrega y resultados: [CON-32/34/36/37](../../../docs/sprints/CON-32-34-36-37-notificaciones.md).

## 5. Transporte SMTP real (CON-78)

Implementación: `src/modules/notificaciones/transporte_smtp.py`. Configuración por
entorno (`.env.example`): `EMAIL_TRANSPORTE=SMTP`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_SEGURIDAD` (`STARTTLS`, `SSL` o `NINGUNA`), `SMTP_USUARIO`/`SMTP_PASSWORD`
(ambos o ninguno), `SMTP_REMITENTE`, `SMTP_NOMBRE_REMITENTE` y `SMTP_TIMEOUT_SEGUNDOS`.

**Selección del transporte.** Se fija al encolar en `notificaciones_logs.transporte`:
`PROVEEDOR` solo para `EMAIL` cuando `EMAIL_TRANSPORTE=SMTP`; el resto queda `SIMULADO`.
El worker atiende cada fila con su transporte registrado. Una fila `PROVEEDOR` con el
worker sin configuración completa pasa a `FALLIDO_PERMANENTE` con alerta
`PROVEEDOR_NO_CONFIGURADO`; nunca se acredita con el transporte simulado.

**Resultado normalizado.** SMTP solo acredita aceptación del servidor: el éxito es
`ENVIADO`, no `ENTREGADO` (este último requiere evidencia posterior del proveedor,
fuera de esta entrega).

| Fase / respuesta | Resultado | Efecto en la cola |
| :--- | :--- | :--- |
| 250 tras el contenido | `ENVIADO` | Guarda el `Message-ID` en log e intento. |
| Conexión, TLS, autenticación, `MAIL FROM` o timeout antes de `DATA` | `FALLO_TEMPORAL` (503) | Reintento según §1; si persiste, `INTENTOS_AGOTADOS`. |
| `RCPT TO` 5xx | `550` | `FALLIDO_PERMANENTE` + `ERROR_DEFINITIVO`. |
| `RCPT TO`, `DATA` o respuesta final 4xx | `FALLO_TEMPORAL` | Reintento. |
| `DATA` o respuesta final 5xx | `FALLO_DEFINITIVO` (422) | `FALLIDO_PERMANENTE` + `ERROR_DEFINITIVO`. |
| Desconexión o timeout después de transmitir el contenido | `ACEPTACION_INCIERTA` | `FALLIDO_PERMANENTE` + alerta `ACEPTACION_INCIERTA`; **no se reenvía solo**. |

Los errores registrados son códigos normalizados: no se guardan textos del servidor,
que pueden repetir direcciones o credenciales.

**Idempotencia y reconciliación.** SMTP no ofrece claves de idempotencia. Cada intento
envía `Message-ID: <{log_id}-{ciclo}-{intento}@{dominio del remitente}>` y la cabecera
`X-CondoManager-Notificacion` con la misma clave. Ante una aceptación incierta, la Junta
puede buscar ese identificador en los registros del proveedor antes de decidir un
reenvío manual (nuevo ciclo). Un intento sin terminar por caída del worker se resuelve
igual mediante `recuperar_inciertos` (§3).

**Desarrollo y demo.** Docker Compose usa por omisión Mailpit (`mailpit:1025`, interfaz
en `http://localhost:8025`), que captura los correos sin reenviarlos. El ambiente demo
define el proveedor real en `.env` y envía solo a cuentas de prueba autorizadas.
