#!/usr/bin/env sh
# PostgreSQL desechable y afinado SOLO para pruebas: datos en RAM y sin durabilidad.
# Nunca usar estos parámetros en un ambiente con datos reales.
#
#   ./scripts/pg_pruebas.sh            # levanta (o recrea) el contenedor
#   eval "$(./scripts/pg_pruebas.sh env)"  # exporta las variables de prueba en la shell
#   uv run --extra dev python -m pytest -q -n auto --dist worksteal
set -eu

NOMBRE="${PG_PRUEBAS_NOMBRE:-condomanager-pg-pruebas}"
PUERTO="${PG_PRUEBAS_PUERTO:-55432}"
URL="postgresql+asyncpg://ci_user:ci_password@127.0.0.1:${PUERTO}/condomanager_ci"

if [ "${1:-}" = "env" ]; then
  echo "export DATABASE_URL=${URL}"
  echo "export DATABASE_URL_SYNC=postgresql://ci_user:ci_password@127.0.0.1:${PUERTO}/condomanager_ci"
  for v in CON3 CON04 CON05 CON06 CON11 CON13 CON39 CON46; do
    echo "export ${v}_TEST_DATABASE_URL=${URL}"
  done
  exit 0
fi

docker rm -f "$NOMBRE" >/dev/null 2>&1 || true
docker run -d --name "$NOMBRE" \
  --tmpfs /var/lib/postgresql/data:rw,size=4g \
  -e POSTGRES_USER=ci_user -e POSTGRES_PASSWORD=ci_password -e POSTGRES_DB=condomanager_ci \
  -p "${PUERTO}:5432" postgres:16-alpine \
  -c fsync=off -c synchronous_commit=off -c full_page_writes=off \
  -c max_connections=300 -c shared_buffers=256MB >/dev/null
i=0
until docker exec "$NOMBRE" pg_isready -h 127.0.0.1 -U ci_user -d condomanager_ci >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "PostgreSQL no respondió" >&2; exit 1; }
  sleep 1
done
# El servidor temporal de inicialización solo escucha por socket: comprobar por TCP.
until docker exec "$NOMBRE" psql -h 127.0.0.1 -U ci_user -d condomanager_ci -Atc "select 1" >/dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL de pruebas listo en 127.0.0.1:${PUERTO} (contenedor ${NOMBRE})."
