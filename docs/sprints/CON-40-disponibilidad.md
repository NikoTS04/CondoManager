# CON-40 — Disponibilidad de áreas comunes

Rama: `feat/proc-04-con-40-disponibilidad`, desde `develop` con CON-39 y CON-72 integrados.
Contrato: [disponibilidad del Sprint 2](../../specs/05-api/sprint-2-contratos.md).

## Alcance implementado

- Conserva `GET /api/v1/areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD` y las
  validaciones del catálogo: sesión, condominio, acceso por edificio y área activa.
- Rechaza fechas pasadas según America/Lima con `422 FECHA_RESERVA_INVALIDA`.
  Parámetros inválidos o fecha ausente: `422 DATOS_DISPONIBILIDAD_INVALIDOS`.
- Lee reservas `CONFIRMADA` de PostgreSQL cuando existe la tabla `reservas`.
  Incluye todas las unidades del área autorizada, no solo las del usuario.
  Solo devuelve `hora_inicio` y `hora_fin`, con formato `HH:MM:00`, sin datos personales.
- Interpreta los registros históricos sin zona como UTC y convierte su ocupación al
  día de Lima, incluyendo registros del día UTC siguiente que correspondan.
  Los registros con `zona_horaria=America/Lima` conservan su interpretación local.
- Recorta ocupaciones a la apertura/cierre, ordena y fusiona solapamientos.
  Intervalos contiguos permanecen separados y admiten un turno que termine justo
  cuando empieza otro. No altera registros ni horarios guardados.
- Muestra carga, error, ausencia de ocupaciones y acción Actualizar/Reintentar.
  No muestra un calendario fallido o pendiente como si estuviera libre.
- Refresca al cambiar área/fecha/horario del catálogo, crear o cancelar una reserva,
  actualizar manualmente o volver a enfocar la ventana. Las respuestas antiguas
  de otra selección se descartan y la consulta no usa caché.
- El formulario evita enviar turnos ya iniciados o que coincidan con ocupaciones
  consultadas. La creación mantiene su validación propia; la consulta no garantiza
  exclusión frente a solicitudes concurrentes.
- Un residente con mora puede consultar horarios; la creación conserva su bloqueo.

## Compatibilidad y dependencias de cierre

La creación y cancelación actuales siguen utilizando `RESERVAS_REGISTRADAS`, en
memoria. Esta entrega conserva esas operaciones y combina sus ocupaciones con
la lectura SQL. Si un UUID aparece en ambas fuentes, prevalece el estado del flujo
piloto para reflejar sus cancelaciones. Si la tabla SQL no existe aún, consulta el
almacén piloto. Los errores SQL no se sustituyen por una respuesta vacía: la consulta
responde `503 DISPONIBILIDAD_NO_DISPONIBLE`.

La lectura SQL utiliza las columnas existentes de `reservas` y detecta su zona
mediante `to_jsonb`, para admitir la columna adicional de CON-73 sin exigirla a
las tablas históricas. La consulta no crea tablas ni índices.

**Pendiente de CON-73:** persistir las nuevas reservas/cancelaciones y definir la
lectura SQL de bloqueos operativos activos. El normalizador acepta ocupaciones
con fecha, inicio, fin y zona; el repositorio deberá sumar esos bloqueos al
integrarse su modelo. No se implementa una gestión pública de bloqueos.

Hasta esa integración, las operaciones piloto se pierden al reiniciar y no se
comparten entre procesos; leer reservas SQL no vuelve persistente al productor.
La exclusión concurrente corresponde a CON-41/43. El cierre de CON-40 requiere
comprobar el calendario integrado con esas operaciones y los bloqueos reales.

### Arranque con la base compartida

Supabase ya registra `20261020_0011`, mientras que la base inicial de esta rama
solo conocía hasta `20261020_0010`. Eso detenía Alembic antes de iniciar la API,
con `Can't locate revision identified by '20261020_0011'`.

Se incorporaron sin modificaciones las revisiones `20261020_0009_pagos` y
`20261020_0011` de `origin/feat/CORE-sprint-2-anderson` (commit `fdb6e01`). La segunda
une los historiales de pagos y catálogo. Se verificó mediante consultas de lectura
que la base ya registra esa cabeza y contiene las tablas de pagos; no se cambió
`alembic_version`, no se ejecutó downgrade ni se incorporó la lógica de pagos de
esa rama. En una base anterior, el arranque sí aplicará las migraciones pendientes.

## Verificación estática realizada

- Ruff: lint y formato correctos en los archivos Python modificados.
- Compilación de sintaxis Python y carga del esquema OpenAPI de FastAPI correctas.
- Next lint: archivos frontend modificados sin avisos ni errores.
- TypeScript: `tsc --noEmit --incremental false` correcto.
- `git diff --check` correcto.

Estas comprobaciones no ejecutan los recorridos HTTP, SQL ni de navegador.

## Recorrido manual

Con el entorno habitual y las áreas de CON-39 preparadas:

```bash
docker compose up -d --build --wait --wait-timeout 180 backend frontend
```

1. Iniciar sesión como residente con vínculo activo. Abrir Reservas, elegir un área
   y una fecha futura. Ver apertura/cierre y el mensaje de ausencia de ocupaciones,
   o la lista de turnos existentes. No deben aparecer residentes ni unidades ajenas.
2. Crear un turno válido. Debe aparecer como ocupado sin recargar la página.
   Elegir una franja que lo cruce: el formulario debe impedir su confirmación.
   Elegir una que empiece exactamente al terminar el turno: no debe marcar conflicto.
3. Abrir otra sesión autorizada en el mismo backend y consultar esa área/fecha.
   Actualizar o volver a enfocar la ventana después de reservar desde la primera.
   Debe ver el turno ocupado aunque pertenezca a otra unidad.
4. Cancelar una reserva propia con al menos 24 horas de anticipación. El turno debe
   desaparecer de la ocupación sin cambiar el área ni la fecha. La otra sesión
   obtiene el nuevo resultado al actualizar o recuperar el foco.
5. Cambiar rápidamente área o fecha. La respuesta de una selección anterior no debe
   reemplazar la actual. Cortar temporalmente la conexión: debe aparecer un error
   con Reintentar y quedar deshabilitada la confirmación hasta consultar correctamente.
6. Consultar hoy: no debe permitirse enviar un inicio ya pasado. El selector impide
   fechas anteriores. Desde `/docs`, verificar fecha pasada (`422`), fecha inválida
   o ausente (`422`), área inexistente (`404`), inactiva (`409`), área de otro
   condominio o edificio no autorizado (`403`) y petición sin sesión (`401`).
7. Cuando existan reservas históricas SQL, comprobar su conversión UTC/Lima y que
   solo `CONFIRMADA` ocupa el calendario. Su lectura debe conservarse al reiniciar;
   las nuevas operaciones piloto todavía no ofrecen esa garantía.
8. Tras integrar CON-73/41/46, repetir reserva/cancelación y consulta entre procesos
   y después de reiniciar; añadir el caso de bloqueo operativo activo/inactivo.

No se añadieron ni ejecutaron pruebas unitarias o de integración por indicación del
responsable. El 21 de octubre de 2026 Gerardo informó un resultado satisfactorio
de su revisión funcional manual. La persistencia y los bloqueos de CON-73 siguen
pendientes; esa revisión no acredita su integración.
