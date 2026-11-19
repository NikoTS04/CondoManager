# Perfil Vercel Hobby + Supabase — 18/11/2026

Un proyecto Vercel Services: `app` raíz (`src/main.py`) y `frontend` Next.js
(`frontend/`), routing/binding en `vercel-services-mailjet.md`.
PostgreSQL y bucket **privado** en Supabase. No Daemons ni Redis
obligatorio en este perfil. No se despliega automáticamente desde esta entrega.

## Archivos

`VOUCHER_STORAGE=supabase` selecciona REST Storage con credencial solo del servidor.
Crear bucket privado manualmente; nunca convertirlo en público. Guardar conserva
validación PNG/JPEG/PDF y nombre UUID; descargar requiere autorización SQL previa,
sin exponer URL ni service-role. No se migra evidencia local automáticamente.
`VOUCHER_MAX_BYTES=3145728` en producción: límite explícito de 3 MiB para cumplir
payload 4,5 MB de Functions. Local mantiene 5 MiB. Descargas remotas también
respetan ese límite: evidencia histórica mayor requiere un flujo específico
de descarga directa autorizada antes de migrarla; no se trunca ni se elimina.

## Trabajo diario

`GET /api/v1/jobs/diario`, Bearer `CRON_SECRET`, sin dependencia de JWT de usuario.
Se rechaza preview. Lock transaccional PostgreSQL excluye solapamiento; emite cuotas,
devenga mora y consume outboxes SQL. Ejecuta motores existentes con errores estrictos.
Timeout 240 s: confirma por operación, conserva lo ya confirmado y permite recuperación
idempotente. 503 no significa rollback de todas las operaciones del lote.
No envía notificaciones simuladas ni promete recepción. No hay reintentos de correo
2/10/30 minutos en Hobby diario. No se prometen 00:05 exactas ni capacidad ilimitada.

## Seguridad

Producción exige JWT propio, debug/demo desactivados, CORS explícito, URL de
activación HTTPS, bucket y clave privada configurados. Pool serverless sin conexiones
persistentes (`DB_NULL_POOL=true`); usar conexión Supabase compatible con asyncpg.
Migraciones en una publicación controlada previa, nunca por arranque/build de preview.
Readiness declara Redis `disabled` cuando `REDIS_REQUIRED=false`; sigue comprobando
PostgreSQL. No es una comprobación de Storage ni de entrega real de correo.
