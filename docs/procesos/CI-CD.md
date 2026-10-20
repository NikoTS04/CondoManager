# CI/CD y verificaciones de calidad

Todo Pull Request hacia `develop` o `main` pasa por los workflows de `.github/workflows/`. Un PR solo se fusiona con los checks obligatorios en verde y la aprobación de otro integrante, como exige la Definición de Terminado del sprint.

## Workflows

| Workflow | Check (nombre en GitHub) | Qué verifica | ¿Bloquea? |
|---|---|---|---|
| `backend.yml` | Backend / Lint | `ruff check` y `ruff format --check` | Sí |
| | Backend / Pruebas | `pytest` con cobertura mínima (`fail_under` en `pyproject.toml`) | Sí |
| | Backend / Migraciones | `alembic upgrade head` → `downgrade base` → `upgrade head` en PostgreSQL 16 real, pruebas de integración con base de datos y `alembic check` | Sí (el drift de `alembic check` aún no bloquea) |
| `frontend.yml` | Frontend / Lint, tipos y build | `next lint`, `tsc --noEmit`, `next build` | Sí |
| `specs.yml` | Specs / Cumplimiento SDD | `scripts/verify_sdd_compliance.py` | Sí |
| | Specs / OpenAPI | Spectral sobre `specs/03-contracts/openapi/condomanager.openapi.yaml` (`.spectral.yaml`) | Sí |
| | Specs / Contrato API | Schemathesis contra la app FastAPI con PostgreSQL efímero y migraciones aplicadas (`scripts/ci/verify_api_contract.py`) | Parcial (ver deudas) |
| `convenciones-pr.yml` | Convenciones / Título del PR | Conventional Commits en el título del PR | Sí |
| | Convenciones / Nombre de rama | Prefijos de rama de `CONTRIBUTING.md` (+ `ci/`, `test/`, `chore/`, `dependabot/`) | Sí |
| `seguridad.yml` | Seguridad / Revisión de dependencias | Dependencias nuevas con vulnerabilidades altas en el PR | Sí |
| | Seguridad / Auditoría Python | `pip-audit` | Ver deudas |
| | Seguridad / Auditoría npm | `npm audit --audit-level=high` | Ver deudas |
| | Seguridad / Secretos | gitleaks (`.gitleaks.toml`) | Sí |
| | Seguridad / Imágenes | Trivy sobre las imágenes de API y web | No (informa en la pestaña Security) |
| `codeql.yml` | Seguridad / CodeQL (python, javascript-typescript) | Análisis estático de seguridad | Sí |
| `docker.yml` | Docker / Build | Construcción de ambas imágenes con caché | Sí |
| | Docker / Smoke compose | `docker compose` + `docker-compose.ci.yml`, migraciones, datos piloto y verificación HTTP | Sí |
| `cd.yml` | CD / Publicar (api, web) | Publica imágenes en GHCR con procedencia y SBOM (push a `develop`, `main` y tags `v*`) | — |
| | CD / Despliegue pendiente | Placeholder de despliegue a `staging` (`develop`) y `production` (`main`) | — |

Dependabot (`.github/dependabot.yml`) propone cada semana, hacia `develop`, actualizaciones agrupadas de pip, npm, GitHub Actions y Docker con el prefijo `chore(deps)`.

## Ejecutar las verificaciones en local

```bash
uv run --extra dev ruff check .
uv run --extra dev python -m pytest -q --cov
cd frontend && npm ci && npm run lint && npx tsc --noEmit && npm run build
uvx --from actionlint-py actionlint      # sintaxis de los workflows
```

## Branch protection (requiere permisos de administrador del repositorio)

En **Settings → Branches** (o Rulesets), para `develop` y `main`:

1. Exigir Pull Request con al menos 1 aprobación y descartar aprobaciones al subir nuevos commits.
2. Exigir los checks marcados como bloqueantes en la tabla anterior, con la rama actualizada antes de fusionar.
3. Bloquear los push directos y los force push.
4. Crear los environments `staging` y `production` (este último con revisor obligatorio) antes de activar el despliegue.

## Deudas registradas

Cada deuda está marcada con `TODO` en el workflow correspondiente; al resolverla se retira el `continue-on-error`.

- Hay modelos sin migración (departamentos, cuotas, pagos, reservas…), así que `alembic check` informa del drift pero no bloquea.
- El lint histórico no cumple `ruff format`; el check se aplica solo a los archivos cambiados.
- El contrato de la API encontró un error 500 con montos extremos (`monto=1e26` → `InvalidOperation`), así que ese caso aún no bloquea.
- Hay vulnerabilidades conocidas en dependencias; el detalle aparece en el resumen de cada ejecución y en la pestaña Security.
- El despliegue no tiene destino definido: faltan la infraestructura, las credenciales del environment y la estrategia de rollback.
