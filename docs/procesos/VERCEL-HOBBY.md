# Vercel Hobby + Supabase

Actualización PROC-03: el despacho de correo y sus reintentos usan un programador
externo autorizado, **Supabase Cron cada minuto**, sin añadir crons por minuto a
Vercel Hobby. Activación y secretos: [Mailjet producción](MAILJET-PRODUCCION.md).
La preparación histórica inferior no acredita configuración remota actual.

## Correcciones al .env importado en Vercel

Revisión local sin copiar secretos: DEBUG estaba true, JWT era el predeterminado,
Redis apuntaba a localhost y faltaban variables Hobby/Storage. DATABASE_URL usa
asyncpg y declara TLS; no se comprobó su conectividad. No desplegar hasta corregir:

| Variable | Valor/acción en Vercel Production |
|---|---|
| APP_ENV / DEBUG / DEMO_MODE | production / false / false |
| JWT_SECRET | Nuevo secreto aleatorio >=32 caracteres; no usar el del ejemplo |
| DB_NULL_POOL / REDIS_REQUIRED | true / false |
| VOUCHER_STORAGE / VOUCHER_MAX_BYTES | supabase / 3145728 |
| SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY | URL HTTPS y clave privada del proyecto; no anon key |
| SUPABASE_STORAGE_BUCKET | Bucket privado vouchers |
| CRON_SECRET | Secreto aleatorio >=32 caracteres |
| IDENTITY_DELIVERY_KEY | Fernet estable de API; no regenerar en cada deploy |
| CORS_ORIGINS | JSON con URL HTTPS del dominio final |
| ACTIVACION_WEB_URL | https://DOMINIO/activar |
| NEXT_PUBLIC_API_URL | /api/v1, o eliminar variable |
| NEXT_PUBLIC_DEMO_MODE | false |
| APP_URL | Eliminar valor manual si existe; binding la inyecta |
| MAILJET_ENABLED | false (confirmado: preparar sin envíos) |
| MAILJET_API_KEY / MAILJET_SECRET | Mantener secretos solo en servidor |
| MAILJET_FROM_EMAIL | Remitente verificado pendiente; no se inventó uno |

MINIO_* y REDIS_URL local no sirven como infraestructura Vercel. Pueden retirarse
del proyecto si no se usan; no hace falta borrar la configuración local de Docker.
Separar valores de Production y Preview; nunca compartir la base operativa con PRs.
Rotar JWT invalida sesiones firmadas con la clave anterior.

El adapter Mailjet no se conecta automáticamente al worker/cron. La activación
requiere completar remitente, revisar aceptación incierta e integración operacional
y autorizar una prueba real. CustomID no se considera idempotencia del proveedor.

## Alcance

Un proyecto con Services `app` (raíz FastAPI) y `frontend` (carpeta frontend,
Next.js); `vercel.json` raíz es la configuración única confirmada por el usuario.
Frontend público, app interno salvo `/api/v1/jobs/diario` protegido. El binding
`frontend → app` inyecta `APP_URL` en runtime. No se ejecuta Docker Compose en Vercel. No hay workers continuos
ni Redis obligatorio: un cron diario protegido reutiliza emisión/mora y consumo
SQL. Correo sigue pendiente; este perfil no cumple reintentos de 2/10/30 minutos.
Hobby tiene precisión horaria, no garantiza el minuto 00:05.
Revisar elegibilidad de uso personal/no comercial de Hobby antes de usar datos reales.

## Preparación (sin modificar una base activa automáticamente)

1. Crear entorno Supabase separado para ensayo y un bucket **privado** `vouchers`.
   Sin políticas públicas de lectura/escritura. Verificar acceso anónimo denegado.
2. Configurar conexión PostgreSQL SSL en `DATABASE_URL`, compatible con asyncpg.
   Preferir endpoint directo o pooler en modo sesión; no asumir compatibilidad
   del pooler de transacciones con prepared statements sin probarlo.
3. Aplicar migraciones con revisión/respaldo en un paso controlado (`alembic upgrade head`).
   Nunca durante build/preview ni desde cada arranque de Function.
4. Importar repo en **un proyecto**, raíz del repositorio, Production Branch `main`.
   Conservar root directory raíz; no seleccionar `frontend/` como raíz del proyecto.
5. Variables API en Production:
   `APP_ENV=production`, `DEBUG=false`, `DEMO_MODE=false`, `DB_NULL_POOL=true`,
   `REDIS_REQUIRED=false`, `JWT_SECRET` propio >=32 caracteres,
   `CRON_SECRET` aleatorio >=32, `IDENTITY_DELIVERY_KEY` estable,
   `VOUCHER_STORAGE=supabase`, `VOUCHER_MAX_BYTES=3145728`,
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET=vouchers`,
   `CORS_ORIGINS=["https://<portal>.vercel.app"]`,
   `ACTIVACION_WEB_URL=https://<portal>.vercel.app/activar`.
6. Frontend: eliminar `NEXT_PUBLIC_API_URL` o poner `/api/v1`;
   `NEXT_PUBLIC_DEMO_MODE=false`. **No configurar APP_URL**: la inyecta el binding.
   Nunca claves privadas como `NEXT_PUBLIC_*`. Las claves Mailjet/Supabase solo se
   leen en código servidor y no se importan desde componentes cliente.
7. Preview usa una base/bucket exclusivos de pruebas; no configurar cron ni
   apuntar a producción. El handler además rechaza `VERCEL_ENV=preview`.

## Aceptación antes de publicar

- Readiness PostgreSQL ok, Redis disabled, login/autorización por dos condominios.
- Voucher PNG/JPEG/PDF <=3 MiB: subir, reiniciar instancia, descargar autorizado,
  rechazar ajeno y contenido inválido. Probar límite real de request multipart.
- Storage sin red/credencial inválida produce 503, nunca fallback local.
- Cron sin secreto 401, preview 403, simultáneo 409 y timeout 503 recuperable.
- El cron no envía correos ni declara entrega. Su capacidad debe medirse con el padrón.
- Reservas, bloqueo preventivo, cancelación y recuperación de datos.
- Ensayar restauración SQL y archivos. No marcar despliegue aceptado solo por build.

## Límites pendientes

Los archivos locales existentes no se migran solos. Subidas remotas cuya respuesta
se pierda antes de registrar SQL pueden dejar objetos huérfanos: revisar inventario
de Storage antes de borrarlos. La limpieza actual solo elimina subidas registradas
sin comprobante; no enumera ni borra objetos remotos desconocidos.
Evidencias históricas >3 MiB requieren descarga directa autorizada separada.
No se incluyen egresos, extraordinarias, cargos de reservas ni cierre contable.
Los bloqueos preventivos rechazan reservas afectadas; no cancelan ni notifican
automáticamente. La implementación no configura cuentas, buckets, secretos o DNS.
