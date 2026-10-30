# CON-46 — Cancelación de reservas

Rama: `feat/proc-04-con-46-cancelacion-reservas`.
Contrato: [cancelación del Sprint 2](../../specs/05-api/sprint-2-contratos.md#con-46--gerardo).

Estado consolidado al 21/10/2026: integrada con CON-41/43, CON-73 y el consumo
de CON-36. La cabeza actual es `20261021_0015`; la evidencia posterior y los límites
se reúnen en [CON-75](CON-75-entrega-sprint-2.md). Las verificaciones originales
de este documento conservan su corte y no se ejecutan de nuevo en esta actualización.

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

La migración `20261021_0012` parte de `20261020_0012` de CON-73. Adopta las
tablas compartidas y conserva las columnas ampliadas de reservas; incorpora
`cancelaciones_reserva` y `cobros_reserva` sin recrear el outbox ya existente.
La revisión `20261021_0014` une las ramas de cancelación y convergencia; `0015`
incorpora alertas de notificaciones. Creación y cancelación mantienen el orden de locks:
condominio → departamento → área → reserva. No hay un catálogo paralelo.

Antecedente de revisión de Supabase del 21/10/2026, exclusivamente de lectura: `public.reservas`
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
sustituye las integraciones con PostgreSQL de pruebas. La
[reconciliación posterior](reconciliacion-esquema-legacy.md) documenta la adopción
real a `20261021_0015`, el respaldo y la conservación de los registros originales.

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
entre publicación y marcado; el consumidor integrado de CON-36 deduplica y
persiste los avisos. `notificaciones-worker`, incluido en Compose, también publica
el outbox de reservas y recupera eventos desde SQL.
Publicar en Redis no acredita envío de correo. El worker no se inicia desde la API.

## Preparación manual

La entrega inicial de CON-46 no aplicó cambios a Supabase; la reparación posterior
se documenta por separado. Con Docker, reconstruye el
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

Verificación del 21/10/2026 tras integrar `develop` hasta `f104e56`:

- 27 comprobaciones dirigidas aprobadas, incluidas las 10 unitarias nuevas,
  las 2 integraciones PostgreSQL y regresiones de concurrencia, catálogo,
  solvencia y grafo Alembic.
- PostgreSQL 17 temporal: migración completa desde cero hasta `20261021_0012`,
  creación SQL con creador/zona, cancelación y nueva reserva concurrentes,
  persistencia entre sesiones, outbox y rollback. No se modificó Supabase.
- Ruff, TypeScript y lint de los dos archivos frontend modificados correctos.
- Regresión del backend en dos tandas: **437 casos aprobados de 439**. Quedan
  dos fallos previos en `test_vinculos_db.py`: el reporte de pago de
  `test_relaciones_mixtas_portal_real_y_operaciones_autorizadas` devuelve 500
  en lugar de 202, y `test_portal_calcula_deuda_solo_de_cuotas_sql_vencidas`
  obtiene 0.00 en lugar de 60.15. Ambos se reprodujeron ejecutando esos casos
  desde una copia limpia de `origin/develop` (`f104e56`), sin CON-46.

Los resultados anteriores corresponden al corte inicial de CON-46. La entrega
posterior de notificaciones reporta la suite integrada aprobada; ver
[CON-75](CON-75-entrega-sprint-2.md). La revisión del PR mantiene su registro propio.
Publicar el evento en Redis no acredita entrega externa de una notificación.
