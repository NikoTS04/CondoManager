# Procedimientos Operativos y Runbooks de Despliegue (Operations & Runbooks)

## 1. Procedimiento de Arranque Local y Pruebas
```bash
# 1. Crear y activar entorno virtual Python
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias backend y testing
pip install -e ".[dev]"

# 3. Levantar servicios de soporte (PostgreSQL + Redis + MinIO)
docker compose up -d

# 4. Aplicar migraciones de base de datos
alembic upgrade head

# 5. Cargar dataset semilla piloto (Villa Bonita 3 - 139 departamentos)
python scripts/seed_condominio_piloto.py

# 6. Iniciar servidor FastAPI
uvicorn src.main:app --reload --port 8000
```

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
