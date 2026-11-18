# Procedimientos Operativos y Runbooks de Despliegue (Operations & Runbooks)

## 1. CON-81 — ambiente compartido y arranque

El ambiente compartido usa **PostgreSQL en Supabase**, configurado mediante el
`.env` privado del operador. Redis, API, frontend y workers se ejecutan en el host
del despliegue. Compose **no crea PostgreSQL** en su configuración principal.
Los vouchers actuales residen en el volumen privado `uploads/vouchers`,
no en Supabase Storage ni en MinIO. Incluir cualquier otro almacén de documentos
incorporado por CON-79. Tener la base en Supabase no respalda archivos.

Registrar en la entrega: host/URL de API y portal (sin secretos), operador,
commit/imagen, fecha UTC, `alembic heads`, revisión instalada y ubicación privada
del volumen. No publicar `.env`, DSN, tokens, correos ni archivos del padrón.

### Instalación o actualización

Antes de actualizar una demo existente: comprobar respaldo recuperable y revisión
soportada, detener workers y bloquear escrituras de usuarios. Revisar operaciones
que solo existan en memoria de procesos anteriores a CON-80 y reconciliarlas de
forma explícita antes de detenerlos. No invocar reparadores legacy como migración
general. No editar revisiones históricas ni ejecutar downgrades sobre la demo.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Cargar configuración PRIVADA de Supabase; no imprimirla.
alembic heads
alembic current
alembic upgrade head
docker compose up -d --build --wait --wait-timeout 180 redis backend frontend
curl --fail --max-time 7 http://localhost:8000/api/v1/ready
```

El backend también migra antes de iniciar. Ejecutar el paso de migración con un
solo operador antes de arrancar réplicas; no competir desde varios despliegues.
Usar conexión Supabase directa o session pooler compatible con Alembic/asyncpg;
validar TLS según la configuración del proyecto, sin deshabilitar su verificación.
No emplear transaction pooler para pruebas con `search_path` de sesión.

Solo en una **base exclusiva de demostración**, con autorización del operador:

```bash
python -m scripts.seed_usuarios_demo
python -m scripts.seed_areas_demo
# Una segunda ejecución debe informar cero cuentas y áreas nuevas.
python -m scripts.seed_usuarios_demo
python -m scripts.seed_areas_demo
```

El seed del padrón aislado solo genera/verifica datos; no inserta usuarios SQL.
Los seeds financieros requieren confirmación explícita y no deben ejecutarse
para validar idempotencia sobre datos compartidos.

### Salud y workers

- `/api/v1/health` (alias `/health`): solo liveness HTTP.
- `/api/v1/ready` (alias `/ready`): PostgreSQL, única revisión esperada y
  tablas/columnas mapeadas del artefacto; timeout de 5 s, 503 genérico y sin caché.
  No certifica permisos de escritura, constraints, Redis, archivos ni correo.
- Redis: `docker compose exec redis redis-cli ping`.
- Iniciar workers después de migrar:
  `docker compose up -d --build --wait cuotas-worker pagos-worker notificaciones-worker`.
  Su healthcheck actual es **solo de proceso**, no prueba progreso.
- Comprobar progreso con un evento de prueba autorizado: UUID en outbox,
  `publicado_en`, `notificaciones_eventos`, aviso e intentos SQL, antes/después del
  reinicio. Revisar `docker compose logs --since 10m` de los tres workers en
  privado; redactar datos personales antes de adjuntar evidencia.
- SMTP real depende de CON-78; `SIMULADO`/`ENVIADO` no acredita recepción.
  Ensayos de recuperación deben usar transporte simulado o contactos autorizados.

### PostgreSQL exclusivo de pruebas

Nunca definir variables `CON*_TEST_DATABASE_URL` con el DSN de Supabase compartido.
Las fixtures crean y eliminan esquemas; las pruebas de migración cambian tablas.
Crear una instancia/base dedicada y exportar ambas variables con su URL asyncpg:

```bash
export CON3_TEST_DATABASE_URL='postgresql+asyncpg://usuario:clave@localhost:55481/condomanager_test'
export CON13_TEST_DATABASE_URL="$CON3_TEST_DATABASE_URL"
# Evita que alguna dependencia no sobrescrita alcance Supabase.
export DATABASE_URL="$CON3_TEST_DATABASE_URL"
python -m pytest -q --cov --junitxml=pytest.xml
ruff check .
python scripts/verify_sdd_compliance.py
python -c 'import reportlab, docx; print("PDF/DOCX disponibles")'
# Desde frontend/, después de npm ci:
# node --test tests/*.test.mjs
# npm run lint
# npx --no-install tsc --noEmit
# npm run build
```

Probar `alembic upgrade head` desde una base vacía y desde `20261025_0020`
(base soportada previa a invitaciones) con datos semilla; repetir las lecturas y
comprobar que usuarios, UUID y hashes se conservan. Determinar la cabeza con
`alembic heads`, no copiar una revisión vieja de este documento.

## 1.1. Respaldo y restauración separados (CON-81/79/78)

1. **Consistencia:** bloquear nuevas escrituras, detener los tres workers y
   esperar a que terminen las transacciones. No detener PostgreSQL. Capturar
   revisión/commit y conservar `IDENTITY_DELIVERY_KEY` fuera del respaldo SQL,
   en el gestor de secretos: los avisos de identidad cifrados la necesitan.
2. Preparar un directorio nuevo privado fuera del repositorio (`umask 077`).
   Usar `pg_dump`/`pg_restore` de versión compatible. Configurar servicios libpq
   `condomanager_demo` y `condomanager_restore` en `~/.pg_service.conf` privado,
   contraseñas en `~/.pgpass` con permisos 0600. No pasar DSN/contraseñas en argv
   ni pegarlos en terminal compartida. El servicio de restauración debe apuntar
   a una **base local vacía de ensayo**, nunca a Supabase compartido.
3. Desde el directorio privado de respaldo, con los servicios configurados:

```bash
umask 077
pg_dump --dbname=service=condomanager_demo --schema=public \
  --format=custom --no-owner --no-acl --file=database.dump
# En el host que realmente contiene el volumen privado:
tar -C /ruta/privada/uploads -czf vouchers.tar.gz vouchers
sha256sum database.dump vouchers.tar.gz > SHA256SUMS
pg_restore --list database.dump > contenido.txt
sha256sum --check SHA256SUMS
```

4. Restaurar en una base vacía y un directorio nuevo, con workers detenidos:

```bash
# Solo en la base NUEVA de ensayo: retirar el esquema vacío que crea PostgreSQL.
# Sin CASCADE: aborta si contiene objetos; no usar --clean sobre una base existente.
psql --dbname=service=condomanager_restore --set=ON_ERROR_STOP=1 \
  --command='DROP SCHEMA public;'
pg_restore --dbname=service=condomanager_restore --no-owner --no-acl \
  --exit-on-error --single-transaction database.dump
tar -C /ruta/nueva/de/ensayo/uploads -xzf vouchers.tar.gz
```

El dump de `public` no es un respaldo completo de Supabase Auth/Storage ni de
otros esquemas administrados. Si hay políticas que referencian roles/funciones de
Supabase, preparar sus dependencias en el ensayo y documentarlas; **no ignorar
errores de restore** ni crear permisos públicos para que termine.

5. Apuntar una API de ensayo a esa base, al directorio restaurado y al secreto de
   cifrado correspondiente. Usar puertos/Redis diferentes. Comprobar readiness,
   login, mismo UUID/estado de reservas/pagos/avisos, hashes y disponibilidad de
   **cada referencia de archivo vigente e histórica**; descargar con usuario
   autorizado y verificar rechazo ajeno. Un archivo ausente impide acreditar
   recuperación completa, aunque `pg_restore` haya terminado.
6. En el ensayo, habilitar workers de forma controlada. Verificar recuperación
   de outboxes/reintentos sin duplicar efectos. No reenviar intentos inciertos sin
   reconciliación del proveedor. Registrar identificadores anonimizados, comandos,
   conteos, checksums y limitaciones; no publicar el dump.
7. Reanudar el ambiente compartido tras la captura consistente, sin apuntarlo al
   ensayo. Conservar respaldos cifrados con acceso restringido y retención acordada.

---

## 2. Runbook: Contingencia ante Fallo en Notificaciones Masivas
- **Síntoma:** Alerta en panel indicando `NOTIFICACIONES_PENDIENTES_CRON_ERROR`.
- **Diagnóstico:** Verificar conectividad con proveedor SMTP o cuota de API de WhatsApp.
- **Acción de Mitigación:**
  1. Acceder al módulo de reintentos: `POST /api/v1/notificaciones/reintentar-fallidos`.
  2. El despachador tomará los mensajes en estado `REINTENTANDO` aplicando la política de backoff sin duplicar los mensajes ya recibidos (`ENTREGADO`).
# Operación de CON-11: emisión mensual

1. Ejecutar `alembic upgrade head` antes de arrancar API y worker. La revisión
   `20261019_0006` crea cuotas, lotes, outbox y completa la FK de CON-13.
2. Aprobar el presupuesto (CON-9), configurar distribución (CON-10) y comprobar
   departamentos activos (CON-3).
3. Arrancar `python -m src.modules.cuotas.worker` o el servicio Compose
   `cuotas-worker`; usa las mismas `DATABASE_URL` y `REDIS_URL` que la API.
   `CUOTAS_DIA_EMISION=1` (rango 1..28) configura el inicio del ciclo mensual UTC.
4. El worker revisa al inicio y diariamente a las 00:00 los pendientes del mes
   actual desde ese día. Para periodos anteriores usar la ejecución manual
   autenticada `POST /api/v1/cuotas/emitir-lote` con condominio y periodo.
5. Si Redis falla, el lote sigue confirmado y el evento queda pendiente en
   `eventos_lote_outbox WHERE publicado_en IS NULL`; el relay reintenta cada 30 s.
   No borrar lotes ni restituir créditos para reintentar notificaciones.
6. Consultar logs del worker por condominio/periodo. Un fallo SQL revierte todo
   el lote; corregir presupuesto/padrón y reintentar. Un `409 LOTE_YA_EMITIDO`
   confirma que ya fue emitido, sin alterar datos históricos.
7. API y worker pueden competir: el lock del condominio y restricciones únicas
   permiten un único lote. Consumidores de Redis deduplican por `event_id`.
