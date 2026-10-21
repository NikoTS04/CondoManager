# CON-46 — Cancelación de reservas

Rama: `feat/proc-04-con-46-cancelacion-reservas`.
Contrato: [cancelación del Sprint 2](../../specs/05-api/sprint-2-contratos.md#con-46--gerardo).

## Implementación

- `POST /api/v1/reservas/{id}/cancelar`, con motivo opcional de 1–500 caracteres.
  Valida sesión, rol, condominio y vínculo activo; `es_admin` del cliente no concede permisos.
- Residente: anticipación mínima de 24 horas, incluida la frontera exacta.
  Administración autorizada puede exceptuar el plazo. Se conserva America/Lima
  para reservas locales y UTC para históricos sin marca de zona.
- Estado `CANCELADA`, actor, motivo, instante original, respuesta, auditoría y
  `ReservaCanceladaEvent` se guardan en una transacción. La respuesta HTTP se
  devuelve después del commit. Un fallo revierte también los efectos asociados.
- Un reintento autorizado devuelve la respuesta original. La clave primaria de
  `cancelaciones_reserva` y el bloqueo SQL evitan repetir ajustes y eventos.
  Una cancelación histórica sin resultado registrado responde
  `422 ESTADO_RESERVA_INVALIDO`; no se inventa una fecha original.
- El listado y el calendario dan precedencia a SQL. Una copia piloto obsoleta
  no vuelve a ocupar un turno cancelado, incluso al solicitar una nueva reserva.
- La interfaz reutiliza la confirmación, admite motivo, presenta el error dentro
  del diálogo y refresca reservas/disponibilidad. Una compensación pendiente se
  identifica sin afirmar que ya hubo devolución.

## Persistencia e integración

La migración `20261021_0012` parte del merge `20261020_0011`. Crea o adopta
`reservas`, conserva sus registros y añade `zona_horaria` cuando falta. Crea
`cancelaciones_reserva`, `cobros_reserva` y `eventos_reserva_outbox`. CON-73 debe
reutilizar estas tablas y CON-41/43 mantener el orden de locks:
condominio → departamento → área → reserva. No hay un catálogo paralelo.

Revisión de Supabase del 21/10/2026, exclusivamente de lectura: `public.reservas`
ya existe, con `usuario_id UUID NOT NULL` y FK a usuarios, `motivo_rechazo`
opcional y sin `zona_horaria`. Alembic registra `20261020_0011`. El ORM y la
adopción del piloto conservan el creador original; no se sustituye por el actor
que cancela. Una copia piloto sin creador verificable responde `409
RESERVA_REQUIERE_RECONCILIACION`, sin inventar identidad ni alterar SQL.
La migración valida columnas obligatorias adicionales antes de modificar la tabla.
Las tablas nuevas habilitan RLS, como las existentes. La revisión no aplicó DDL
ni modificaciones de datos en Supabase; las integraciones recrean ese esquema
en su base de pruebas para comprobar la adopción.
El plan de `upgrade()` se contrastó con los metadatos reales dentro de una
transacción de solo lectura, interceptando las escrituras: validación estructural
correcta. Operaciones previstas: añadir zona y check a `reservas`, crear las tres
tablas auxiliares, su índice y activar RLS. Se comprobó después que Alembic seguía
en `20261020_0011`, sin la columna ni las tablas nuevas. Esta simulación no
sustituye las integraciones con PostgreSQL de pruebas.

Tras integrar `origin/develop` con CON-41/43, la creación utiliza
`ReservasRepository` y conserva `usuario_id` y `zona_horaria`. El repositorio
hace flush dentro de la transacción de solvencia y catálogo; la respuesta y la
copia de compatibilidad en memoria se actualizan después del commit. Creación
y cancelación comparten el orden de locks. Los solapamientos se comparan como
instantes para admitir históricos UTC y turnos de Lima.

CON-46 cancela directamente las reservas SQL. Conserva el puente para una
reserva piloto anterior: la incorpora a `reservas` y la cancela en la misma
transacción. Las pruebas históricas sin SQL utilizan un adaptador explícito;
un error de base de datos del productor real no genera éxito en memoria.

Una tarifa no acredita un pago. Sin un cobro efectivo vinculado, el resultado es
`NO_APLICA`, monto `0.00`. `cobros_reserva` representa un único cobro por reserva,
con comprobante exclusivo, aprobado y conciliado, de la misma unidad. Su productor
queda a cargo del flujo financiero integrado; CON-46 no crea cobros ni cambia
estados de comprobantes. Si el cobro es reembolsable, solicita por única vez el
importe efectivamente pagado y no compensado, como `PENDIENTE` dentro del resultado
persistido. La ejecución y el asiento financiero quedan fuera de esta operación.

El relay `python -m src.modules.reservas.worker` publica eventos confirmados en
`condomanager:domain-events`. Puede reentregar el mismo `event_id` si se interrumpe
entre publicación y marcado; CON-36 debe deduplicar y persistir la entrega real.
Publicar en Redis no acredita envío de correo. El worker no se inicia desde la API.

## Preparación manual

No se aplicaron cambios a Supabase desde el agente. Con Docker, reconstruye el
backend y frontend para incorporar el código: el backend ejecuta
`alembic upgrade head` al arrancar. Comprueba la revisión antes del recorrido:

```powershell
docker compose up -d --build --wait --wait-timeout 180 backend frontend
docker compose exec backend python -m alembic current
```

1. Inicia el backend y frontend con tu configuración habitual e ingresa como
   residente con una unidad autorizada. Crea una reserva a más de 24 horas.
2. En Mis reservas, cancela indicando un motivo. Comprueba estado `CANCELADA`,
   horario libre y posibilidad de solicitar otra reserva en ese turno.
3. Repite el POST de cancelación del primer UUID: debe devolver la misma fecha
   y respuesta, sin una segunda auditoría ni evento.
4. Cancela una reserva a menos de 24 horas: el residente recibe `422`; un
   administrador autorizado puede cancelarla. Otra unidad, otro condominio y
   un auditor reciben rechazo. Enviar `es_admin=true` no cambia el permiso.
5. Reinicia el backend y consulta el historial: tanto la creación SQL como la
   cancelación deben conservarse. Verifica también una reserva aún confirmada.

Para verificar publicación de eventos, ejecuta el relay anterior en tu entorno
con Redis disponible. La entrega final de notificaciones se valida con CON-36/73.

## Pruebas

Se añadieron **10 casos unitarios y 2 pruebas de integración** del backend:

- Unitarios: las tres fronteras de 24 horas, UTC histórico, excepción
  administrativa, intento de elevar privilegios, estado completado y tres
  resultados de ajuste económico.
- Integración PostgreSQL: cancelaciones concurrentes con resultado/ajuste/evento
  únicos, permisos, consulta desde sesiones independientes, calendario y relay;
  fallo tras el flush con rollback completo y posterior reintento.

Las integraciones crean un esquema aislado por prueba; no deben apuntarse a una
base de producción. Configura `CON46_TEST_DATABASE_URL` con PostgreSQL de pruebas:

```powershell
.venv/Scripts/python.exe -m pytest src/tests/unit/test_cancelaciones.py src/tests/integration/test_cancelaciones_db.py -q -rs
```

Verificación local del 21/10/2026: 28 comprobaciones aprobadas (10 unitarias nuevas,
12 unitarias existentes, 3 contratos HTTP existentes de reservas/permisos y 3 BDD).
Las 2 integraciones PostgreSQL se omitieron por falta de URL de pruebas.
Ruff y TypeScript sin errores. La comprobación manual queda a cargo de Gerardo.
