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
