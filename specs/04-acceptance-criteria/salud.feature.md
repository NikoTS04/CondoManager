# Salud operativa — 18/11/2026

Escenario: dependencias disponibles
  Dado PostgreSQL y Redis disponibles
  Cuando se consulta GET /api/v1/health/ready
  Entonces responde 200 con ambas dependencias ok

Escenario: caída o timeout de una dependencia
  Dado PostgreSQL o Redis no disponible
  Cuando se consulta readiness
  Entonces responde 503 sin credenciales ni detalles internos
  Y GET /health sigue respondiendo 200 como señal de vida del proceso
