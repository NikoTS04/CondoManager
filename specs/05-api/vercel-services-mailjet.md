# Services y preparación Mailjet — 18/11/2026

Configuración confirmada por el usuario: servicios `app` (FastAPI, raíz) y
`frontend` (Next.js, frontend/). Un proyecto desde `main`.
`frontend` llama a `app` mediante binding `APP_URL` leído solo en funciones runtime.
Nunca se configura manualmente APP_URL ni se expone como NEXT_PUBLIC_*.

Routing: `/api/v1/jobs/diario` → app (CRON_SECRET obligatorio); catch-all →
frontend, cuyo handler `/api/v1/[...path]` reenvía métodos HTTP a app. Conserva
`/api/v1`, query, Bearer e Idempotency-Key. No propaga cookies ni hop-by-hop.
Valida segmentos, limita cuerpo a 4 MiB, no sigue redirects ni publica URLs internas.
Respuestas privadas no-cache; fallos de conexión devuelven 503 saneado.
Next.js local usa 127.0.0.1:8000 si no hay binding y no está en Vercel.

## Integración productiva PROC-03 — 21/11/2026

Remitente autorizado: `nicolas.tarqui@unmsm.edu.pe`. `MAILJET_ENABLED` permanece
false hasta aceptación remota. Nuevas notificaciones EMAIL en producción usan
PROVEEDOR incluso si el envío está suspendido; nunca se convierten registros SIMULADO históricos. No se envía
SIMULADO desde el job de producción. Deshabilitar suspende la cola sin consumir intentos.

`POST /api/v1/jobs/notificaciones`: Bearer `CRON_SECRET`, solo producción en Vercel
(preview rechazado), sin sesión de usuario. Supabase Cron lo invoca cada minuto.
Lock SQL, ejecución acotada a 45 segundos y lote máximo de 20 intentos por llamada.
Recupera outbox, intentos inciertos y recordatorios antes del despacho.
No se ejecutan migraciones ni se configuran recursos remotos desde este handler.

`POST /api/v1/notificaciones/mailjet/eventos`: Basic usuario `mailjet` y contraseña
`MAILJET_WEBHOOK_SECRET` (secreto independiente >=32 caracteres). Callback HTTPS de
Mailjet para `sent`, `bounce`, `blocked`, `spam`. Máximo 64 KiB y 100 eventos.
Correlaciona `CustomID` (notificación-ciclo-intento), MessageID y destinatario.
`sent` acredita aceptación del servidor de destino (ENTREGADO, no lectura humana);
rebote/bloqueo/spam generan fallo y alerta. Duplicados y eventos de ciclos anteriores
no cambian el estado actual. El callback puede adelantarse a la respuesta de envío.
Los endpoints públicos tienen rewrite directo a app; no se publican credenciales.

Un rechazo 429 permite reintento; timeout, 5xx o respuesta ambigua quedan para
revisión sin reenvío automático. Recordatorios a las 08:00 de Lima, tres días antes
y el día de vencimiento, con clave determinista por cuota/tipo; se revalida deuda
antes del intento. No se recuperan recordatorios de días pasados.

### Preparación histórica

Mailjet: `MAILJET_API_KEY` y `MAILJET_SECRET` privados; falta remitente
`MAILJET_FROM_EMAIL` verificado. Adapter desactivado por defecto mediante
`MAILJET_ENABLED=false`, sin envíos automáticos en cron/worker en esta entrega.
Se prepara Send API v3.1 sin asumir que CustomID evita duplicados. Un timeout,
respuesta 5xx o aceptación ambigua exige revisión, no reintento ciego.
ENVIADO solo acredita aceptación con MessageID; recepción requiere evidencia aparte.
Hobby diario no satisface los reintentos de 2/10/30 minutos.

El .env local no es un fichero de producción: no se versiona ni se corrige
automáticamente. Rotar JWT predeterminado, apagar DEBUG y completar perfil Hobby
y Storage. Credenciales Mailjet nunca van en binding público ni bundle del navegador.
