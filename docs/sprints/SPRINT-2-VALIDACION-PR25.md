# Validación del candidato del PR #25

Fecha de preparación: 28/10/2026, America/Lima. Base de código: `f49dc55` de `develop`. Destino: [PR #25, develop → main](https://github.com/NikoTS04/CondoManager/pull/25). Las correcciones se preparan en `ci/sprint2-release-checks`, para revisión antes de integrarlas en `develop`.

## Alcance del candidato

Incluye los 20 elementos del [Sprint 2](SPRINT-2.md), completando usuarios, pagos, reservas y comunicaciones, y la ampliación financiera posterior del PR #28: gracia por responsable, política diaria, presupuesto por conceptos, prorrateo y PDF/DOCX privados, conciliación por fecha bancaria y fondos por edificio. La cabeza de migraciones es `20261025_0020`.

Los límites prospectivos y la recuperación del despliegue anterior están en [contratos financieros](../../specs/05-api/prorrateo-mora-reportes.md) y [reconciliación del 26 de octubre](reconciliacion-esquema-20261026.md). El procedimiento legacy no es una adopción genérica para cualquier base existente.

## Diagnóstico de los checks originales

En el head `f49dc55` del PR #25 fallaban título, OpenAPI, formato backend, pruebas backend y Dependency Review. La API de GitHub permitió comprobar los checks y descargar el log autenticado del job de pruebas.

El job original usó pytest 9.2.0 y pytest-bdd 9.0.0: **57 escenarios BDD fallaron**, con `FixtureManager` sin el atributo `_arg2fixturedefs`. Los otros **593 casos pasaron** y la cobertura fue **92,13 %**; el fallo del job no se debía a incumplir el mínimo del 80 %. Este resultado es diagnóstico del head original, no aprobación del candidato corregido.

## Correcciones preparadas

- pytest acotado a `>=8.1.0,<9.1` mientras pytest-bdd dependa de la API retirada. No se parchean internals del runner ni se desactivan escenarios.
- Condiciones de esquemas OpenAPI con `items` explícito. La descripción con comas de la respuesta 422 se cita para que YAML no la interprete como propiedades adicionales.
- Formato Ruff de 42 archivos que introducían deuda respecto de `main`; comparación de AST antes/después para comprobar que el formato conserva el código ejecutable. Las migraciones conservan revisiones, relaciones y operaciones.
- Workflow CON-72 con `CON13_TEST_DATABASE_URL`, reconocida por los fixtures compartidos. La configuración anterior con `CON73_TEST_DATABASE_URL` omitía integraciones SQL.
- Los 158 análisis y cachés `graphify-out` dejan de versionarse. Se conservan localmente y siguen ignorados. Se ignoran también artefactos locales de instalación y verificación.
- README, CHANGELOG y documentos de entrega distinguen el cierre original de S2, el corte financiero actual y sus respectivas evidencias.
- Título del PR #25 corregido a Conventional Commits. El cuerpo del PR debe explicar el alcance actual y el estado de la rama de correcciones.
- Fallo funcional encontrado en Chromium: aprobar un pago legacy podía insertar el movimiento del fondo antes de su imputación y responder 500 por clave foránea. Se persisten primero sus padres mediante `flush`, sin commit intermedio. La nueva prueba usa un intérprete limpio, porque las importaciones del resto de la suite ocultaban el fallo por el orden de registro de modelos; falló antes del cambio y pasó después. También comprueba la fuente persistida y que repetir la aprobación no duplica el fondo. Es un cambio funcional separado del formato de los 42 archivos.

## Entornos de verificación

La ejecución de referencia usa Python 3.12 en Linux y PostgreSQL 16 desechable, con pytest 9.0.3 y pytest-bdd 9.0.0. Bases separadas para suite, contratos y ciclo de migraciones. Las URLs de prueba se proporcionan explícitamente; no se copia ni carga el `.env` del proyecto ni se accede a su base operativa.

El frontend se comprueba con su `package-lock.json`. Se construyen las imágenes de producción API/web y se arranca un stack de smoke con nombres, red y puertos exclusivos, PostgreSQL efímero y transporte simulado.

Los intentos iniciales en Windows y la primera colección Linux sobre cachés Windows se descartaron como evidencia de aceptación. Se retiraron únicamente las cachés Python del worktree antes de la ejecución Linux de referencia. Ningún caso se excluye para superar los checks.

## Resultados de esta revisión

| Verificación | Resultado |
|---|---|
| Backend completo y cobertura con PostgreSQL, antes de la corrección funcional | 650 aprobadas, 0 omitidas; cobertura 92,18 % (mínimo 80 %). No incluye la nueva regresión ni acredita por sí sola la versión final. Los checks del PR deben validar el árbol final. |
| Fondos con la corrección funcional y la regresión nueva | 15 aprobadas, 0 omitidas, sobre PostgreSQL. La regresión aislada falló antes del cambio y pasó después. |
| Ciclo de migraciones | `upgrade head → downgrade base → upgrade head` correcto sobre una base vacía y desechable; cabeza final 0020. |
| Contrato ASGI / Schemathesis | 68 aprobadas, 0 fallidas, 0 omitidas. |
| Respuestas y eventos CON-72 con PostgreSQL | 24 aprobadas, 0 fallidas, 0 omitidas. |
| Lint de archivos modificados contra main | Correcto para 167 archivos Python. Deuda de formato anterior visible y sin incrementos de avisos. |
| SDD | Correcto. Es una verificación estática y no sustituye pruebas funcionales. |
| Spectral 6.15.0 | 0 errores, 71 advertencias documentales visibles; no se reducen severidades para eliminar los errores. |
| Frontend | 22 pruebas JavaScript aprobadas; ESLint, TypeScript y build Next.js correctos. |
| Imágenes Docker | API y web construidas correctamente. |
| Smoke Docker | API, web, PostgreSQL, Redis y tres workers saludables; scripts piloto y migración repetida correctos. Health y portal HTTP 200; login SQL devuelve ADMIN_JUNTA. |
| Chromium: pagos | Correcto: subida y descarga privada, observación, subsanación conservando UUID, aprobación, aviso canónico, solvencia posterior y recarga. Comprobante `703cd63c-03f1-4bc9-bb3b-b3c6a4875455` en la base efímera. |
| Chromium: reservas | Correcto: creación, recarga, aviso del worker y cancelación sin ajuste económico aplicable. Reserva `233b3a51-ffba-4caf-a165-efb855e12d85` en la base efímera. |
| Persistencia tras reiniciar API y workers | Ambos guiones recuperaron el mismo comprobante y reserva desde PostgreSQL. Se reiniciaron procesos de aplicación; no se destruyó la base efímera. Transporte de avisos simulado. |

Los reportes JUnit, cobertura, logs y capturas son artefactos de la ejecución y no código del producto. En el worktree local están bajo `tmp/release-checks/`; CI conserva sus propios XML como artifacts. Para revisar el PR se deben usar los resultados de su revisión final, no asumir que la ejecución local representa un check remoto.

## Comandos reproducibles

Instalar los manifiestos del candidato y utilizar PostgreSQL exclusivo de pruebas. `CON3_TEST_DATABASE_URL` y `CON13_TEST_DATABASE_URL` deben apuntar a esa base; los fixtures crean y eliminan esquemas de prueba.

```bash
python -m pip install -e '.[dev]'
python -m pytest -q --cov --cov-report=xml:coverage.xml --junitxml=pytest.xml
python scripts/verify_sdd_compliance.py
python -m pytest -q src/tests/integration/test_convergencia_con72.py

# En una base vacía y desechable diferente, nunca en la operativa:
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head

# Contrato ASGI, después de migrar y sembrar el entorno exclusivo de pruebas:
python -m pytest -q scripts/ci/verify_api_contract.py

# Desde frontend/:
npm ci
node --test tests/*.test.mjs
npm run lint
npx --no-install tsc --noEmit
npm run build
```

El contrato ASGI requiere adicionalmente `schemathesis==4.22.1`, como indica el workflow. Para OpenAPI se usa el comando Spectral de `.github/workflows/specs.yml`. Los guiones Chromium existentes requieren Playwright/Chromium y el indicador explícito de entorno demo; deben apuntar solo al stack de pruebas.

## Condiciones externas de aceptación

1. **Dependency Graph:** el administrador debe habilitarlo para que Dependency Review funcione. La cuenta conectada tiene permiso de publicación, pero no administración. El control se conserva bloqueante; no se sustituye por un éxito artificial.
2. **Revisión de las correcciones:** [CONTRIBUTING.md](../../CONTRIBUTING.md) exige una aprobación de otro integrante para cualquier PR hacia `develop` y squash de ramas de trabajo. Estas correcciones se publican en un PR independiente; no se introducen por push directo a `develop` ni se autoaprueban.
3. **Entrega a main:** integrar las correcciones revisadas en `develop`, esperar sus checks actualizados y obtener aprobación del PR #25. Este documento no acredita un merge ni una Release.

## Límites conservados

Vouchers privados locales; habilitación manual por SuperAdmin; invitaciones y correo real diferidos; `ENVIADO` simulado no acredita entrega externa; ajuste de cancelación PENDIENTE no acredita devolución. No se importa caja histórica, no se implementa el Sprint 3 y no se configura despliegue automático a producción.

Los diagnósticos de drift y las auditorías de seguridad que ya eran no bloqueantes mantienen sus advertencias y deuda documentada. Un check verde de esos jobs no demuestra ausencia de vulnerabilidades o drift. La evidencia histórica de [CON-75](CON-75-entrega-sprint-2.md) conserva sus números y cortes originales.
