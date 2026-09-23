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
