# CON-32, CON-34, CON-36 y CON-37 — Entrega y guion de notificaciones

Rama: `feat/proc-03-notificaciones-sprint-2`, desde `develop` con CON-04/05/06
integrados. Contratos: [dominio](../../specs/02-domains/03-notificaciones/spec.md),
[política de entrega](../../specs/02-domains/03-notificaciones/delivery-policy.md) y
[catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md).

## Qué se entrega

- **Persistencia** (migración `20261021_0012`): `notificaciones`, `notificacion_intentos`,
  `eventos_consumidos` y `alertas_administrativas`. Se distingue registro persistido
  (`EN_COLA`), envío aceptado por el proveedor (`ACEPTADO`) y entrega confirmada
  (`ENTREGADO`); `transporte_simulado` identifica los envíos del transporte simulado.
- **Consumo idempotente** (`consumidores.py`): cada evento se procesa en una transacción
  (marca en `eventos_consumidos`, destinatarios con vínculo y cuenta activos, registro con
  `clave_deduplicacion` única). Reentregar un evento, o reemitirlo con otro `event_id`, no
  crea entregas lógicas duplicadas.
- **CON-32**: consume el `CuotasEmitidasEvent` real del outbox de CON-11 y lee las cuotas
  persistidas del lote (periodo, unidad, monto exigible y pendiente, vencimiento, medios de
  pago). No modifica importes.
- **CON-34**: `PagoReportadoEvent` (recepción) y `PagoRevisadoEvent`
  (`APROBADO`/`OBSERVADO`/`RECHAZADO`). Si `comprobantes_pago` existe se contrasta el
  comprobante persistido; un `APROBADO` sin `saldo_resultante` se rechaza: la plantilla no
  inventa saldos.
- **CON-36**: `ReservaConfirmadaEvent` y `ReservaCanceladaEvent` (área, fecha, horario,
  costo, normas, liberación y ajuste económico) solo para la unidad de la reserva;
  comunicados masivos persistentes desde la Junta. La invitación de CON-04 queda diferida.
- **CON-37** (`entrega.py`): 1 intento + 3 reintentos (2 min ±15 s, 10 min, 30 min),
  clasificación temporal/definitiva, `FALLIDO_PERMANENTE` con alerta administrativa,
  reclamo con `FOR UPDATE SKIP LOCKED` y arrendamiento recuperable tras caída, sin reenvío
  de `ACEPTADO`/`ENTREGADO`. El reenvío manual abre un nuevo `ciclo` y conserva el historial.
- **Worker** `python -m src.modules.notificaciones.worker` (servicio
  `notificaciones-worker`): grupo `notificaciones-workers` sobre
  `condomanager:domain-events`; `XACK` solo tras commit, recuperación con `XAUTOCLAIM`,
  eventos ajenos confirmados sin efecto y errores de contrato a
  `condomanager:domain-events:dlq`.
- **API y frontend**: bitácora persistente con filtros, detalle de intentos por ciclo,
  alertas, reenvío y comunicado (Junta; Auditor solo lectura) y **Mis comunicaciones** en el
  portal del residente (solo las propias y de unidades con vínculo activo).

## Dependencias abiertas para el cierre

Los pagos y reservas siguen en memoria. CON-34 y CON-36 se cerrarán cuando CON-70
(Anderson) y CON-41/CON-46 (Brandon/Gerardo) publiquen sus eventos después del commit
según `pago-reportado`, `pago-revisado`, `reserva-confirmada` y `reserva-cancelada`
(`specs/03-contracts/events/schemas/`). Las pruebas de este sprint usan envelopes de
contrato; no sustituyen la operación real de revisión que exige el sprint.

## Arranque de la demostración

```bash
docker compose up -d --build --wait --wait-timeout 180 backend frontend notificaciones-worker cuotas-worker
```

Por defecto `NOTIFICACIONES_TRANSPORTE=SIMULADO`. Para correo real: `SMTP` con
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` y `SMTP_USE_TLS`.
`NOTIFICACIONES_MEDIOS_PAGO` define las cuentas de recaudación del aviso de cuota.

## Recorrido funcional

1. Como Junta, emitir el lote del periodo (CON-11). El worker de cuotas publica el evento y
   el de notificaciones registra un aviso por destinatario con vínculo activo.
2. En **Comunicados** (Junta) la bitácora muestra cada aviso con estado, intentos,
   transporte simulado, y `Ver intentos` con el historial por ciclo.
3. Fallos controlados del transporte simulado (dependen de `intentos` persistido, por lo
   que se conservan al reiniciar el worker):
   - correo `nombre+falla1@dominio`: 503 en el primer intento → `REINTENTANDO` → aceptado
     en el reintento de ~2 min; `+falla3@` agota hasta el cuarto intento;
   - correo `nombre+rebote@dominio`: 550 → `FALLIDO_PERMANENTE` y alerta
     "El correo del residente del Dpto. N rebotó…".
4. En la alerta, **Reenviar** con un destinatario corregido: la notificación vuelve a
   `EN_COLA` en el ciclo 2; los intentos del ciclo 1 siguen visibles.
5. Como residente, **Mis comunicaciones** lista solo sus avisos; un vínculo revocado deja de
   mostrar los de esa unidad.
6. Reiniciar `notificaciones-worker` con eventos en Redis o notificaciones pendientes: se
   procesan sin duplicados.

## Pruebas automatizadas y evidencia

Con `CON13_TEST_DATABASE_URL` (PostgreSQL) y Redis en `TEST_REDIS_URL`
(por defecto `redis://localhost:56379/0`):

```bash
.venv/bin/python -m pytest -q src/tests/integration/test_notificaciones_*.py \
  src/tests/unit/test_notificaciones_*.py src/tests/bdd/test_notificaciones_bdd.py
```

Resultados de esta entrega:

- Suite backend completa: **372 pruebas aprobadas**, cobertura **89,28 %** (base previa:
  320 pruebas). Pruebas de notificaciones: **61 aprobadas** (unitarias, BDD e integración
  con PostgreSQL y Redis reales).
- Frontend: **16 pruebas Node aprobadas**, lint, tipos y build correctos (Node 22).
- Recorrido real sin simulaciones de evento: emisión de lote con `EmisionCuotasService` →
  outbox → relay de `cuotas.worker` a Redis → `notificaciones.worker` → 3 avisos `ACEPTADO`
  (transporte simulado) con sus intentos y `eventos_consumidos`; ningún mensaje pendiente.
- Con el worker detenido se publicaron un evento ajeno, un `PagoRevisadoEvent` sin
  `saldo_resultante` y un `PagoReportadoEvent` para `+falla1@`. Al reiniciar: evento ajeno
  confirmado sin efecto, el inválido en la DLQ con su error y el aviso en `REINTENTANDO`
  (503), aceptado en el reintento real 110 s después (2 min con jitter).
- `scripts/verify_pilot_e2e.py` (smoke de CI) actualizado al motor persistente.
- Ciclo Alembic `upgrade head → downgrade base → upgrade head`: correcto.
