# CON-73 / CON-74 — Persistencia e integración funcional

Responsable: Nicolás. Rama: `feat/CORE-con73-con74-integracion`.
Estado consolidado al 21/10/2026: integrada en `develop`, con evidencia previa
del equipo y reconciliación del esquema desplegado documentada. La aprobación
final se registra en el PR de entrega. El rediseño visual queda diferido.

Actualización: la posterior [convergencia CON-72](CON-72-convergencia.md) sustituye
las limitaciones de multipart, subsanación y alias CONCILIADO descritas aquí.
Los resultados de este documento son evidencia histórica de la entrega inicial.
El [cierre CON-75](CON-75-entrega-sprint-2.md) reúne la evidencia posterior de
notificaciones y la [reconciliación legacy](reconciliacion-esquema-legacy.md).

## Entrega

- Conserva catálogo/usuarios/roles/vínculos existentes y el flujo real de pagos de
  Anderson, incluidos upload privado y consulta transaccional de solvencia.
- Alembic `20261020_0012` adopta reservas históricas sin reinterpretar UTC ni
  perder tarifa/identificador. Guarda contexto, actor, moneda, nombre histórico
  del área y resultado de cancelación. Esquemas incompatibles o históricos
  solapados requieren conciliación antes de migrar; no se eliminan registros.
- Calendario SQL con intervalos semiabiertos, bloqueos persistentes, conversión
  UTC/Lima y exclusión entre sesiones mediante el lock estable del área.
- Reserva/cancelación, auditoría encadenada y outbox en la misma transacción;
  cancelación repetida conserva su respuesta original. Sin cobro efectivo de
  reserva el ajuste es NO_APLICA, no un reembolso de la tarifa.
- Cola de avisos SQL, destinatarios del padrón real, deduplicación de consumo e
  intentos persistentes. Reintentos 2/10/30 minutos con jitter inicial. Un intento
  interrumpido queda visible para revisión, sin un reenvío de aceptación incierta.
- Relay de reservas y consumidor de cuotas/pagos/reservas, compatibles con el
  envelope histórico de Anderson. Recuperación desde outbox SQL incluso sin
  Redis; los eventos inválidos quedan como incidencias y descartes identificables.
- Interfaz actual: avisos de residente, estados/transporte/errores visibles,
  corrección y reencolado administrativo, refresco de disponibilidad tras cancelar,
  errores estructurados y modo demo únicamente optativo. No añade dependencias
  de frontend ni un nuevo sistema visual.

## Arranque

Usar una base de pruebas o una copia verificada; no ejecutar seeds demo sobre
producción. La migración habilita RLS sin políticas públicas; el acceso es por
la API con conexión privilegiada, no desde el navegador a las tablas.

```bash
python -m alembic upgrade head
docker compose up -d --build backend cuotas-worker pagos-worker notificaciones-worker frontend
```

`NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_DEMO_MODE` se fijan al **compilar** Next.js;
cambiar solo el entorno del contenedor no modifica el JavaScript ya construido.
`NEXT_PUBLIC_DEMO_MODE=false` no realiza login automático ni muestra credenciales.
El backend conserva su opción `DEMO_MODE` independiente para seeds/pruebas.

Worker sin Docker:

```bash
python -m src.modules.notificaciones.worker
```

## Verificación reproducible

Los fixtures crean esquemas aislados y los eliminan al finalizar. Configurar
`CON73_TEST_DATABASE_URL` y `CON13_TEST_DATABASE_URL` con PostgreSQL de pruebas.
El fixture de la prueba de condominios ya crea un esquema aislado migrado, según
la corrección integrada en el cierre de notificaciones.

```bash
pytest -q
pytest -q src/tests/integration/test_reservas_notificaciones_db.py src/tests/integration/test_migracion_con73.py src/tests/bdd/test_persistencia_sprint2_bdd.py
```

En `frontend/`:

```bash
node --test tests/*.test.mjs
npx tsc --noEmit
npm run lint
npm run build
```

Recorrido Chromium con Playwright instalado, API/worker/Redis activos y seeds
`scripts.seed_usuarios_demo` y `scripts.seed_areas_demo` en un entorno aislado:

```bash
python -m scripts.verificar_reservas_navegador --url http://localhost:3000 --confirmar-entorno-demo
```

El script comprueba crear, recargar, consultar avisos y cancelar. Devuelve el UUID
de la reserva; después de reiniciar API/worker/PostgreSQL, verificar sin mutar:

```bash
python -m scripts.verificar_reservas_navegador --url http://localhost:3000 --confirmar-entorno-demo --reserva-reinicio UUID_DEVUELTO
```

Para repetir creación en la misma fecha/turno, la ejecución previa debe haber
cancelado la reserva; no borrar registros para preparar la demostración.

## Evidencia y límites

Verificación del 21/10/2026:

| Check | Resultado |
|---|---|
| Última suite completa con PostgreSQL | 440 pruebas aprobadas; cobertura 91,50 % (mínimo 80 %). |
| Suite específica actualizada CON-73/74 | 29 pruebas aprobadas, incluido el lease durante un envío en curso. |
| Cliente API/sesión JavaScript | 16 pruebas aprobadas. |
| TypeScript, ESLint y build Next.js | Correctos. |
| Chromium crear/recargar/avisos/cancelar | Correcto sobre API, Redis y PostgreSQL reales aislados. |
| Chromium tras reiniciar API/worker/PostgreSQL | Mismo UUID e historial recuperados. |
| Contratos y configuración | Eventos de reserva validados contra JSON Schema; YAML y Compose válidos. |

- Verificación local con PostgreSQL y Redis aislados, sin modificar Supabase ni
  los contenedores existentes del usuario. Evidencia temporal en
  `/tmp/opencode/con73-evidencia/` y `/tmp/opencode/con73-evidencia-reinicio/`.
- Reserva de navegador: `eaab8f94-d315-4ca7-aa82-61976ad76032`; se conserva tras
  reiniciar API, worker y PostgreSQL. Incluye captura del aviso y transporte.
- Las pruebas nuevas cubren rollback, diez solicitudes concurrentes, intervalos
  contiguos, UTC histórico, frontera de 24 horas, consumo duplicado, workers
  concurrentes, aceptación incierta, fallos/reintentos y contacto revocado.
- Ruff de los archivos de la entrega pasa. Ruff global mantiene 49 hallazgos en
  archivos no modificados; no se amplió el cambio con limpieza ajena al alcance.
- **SIMULADO no es entregado:** el proveedor externo y su confirmación
  autenticada quedan diferidos. La entrega de Alejandro incorpora reintentos y
  alertas administrativas persistentes, sin acreditar envío real.
- La convergencia posterior CON-72 reemplaza el upload en dos pasos por multipart
  único, incorpora subsanación y utiliza `APROBADO` como estado público. La
  limitación inicial de adopción de contratos ya no describe el corte integrado.
- El esquema real documentado se reconcilió a `20261021_0015`, con respaldo y
  comparación de datos. El procedimiento no inició workers ni reprodujo eventos
  históricos. El detalle operativo está en la reconciliación enlazada arriba.
