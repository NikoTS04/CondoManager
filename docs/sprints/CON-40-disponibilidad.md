# CON-40 — Disponibilidad de áreas comunes

Rama: `feat/proc-04-con-40-disponibilidad`, desde `develop` con CON-39 y CON-72 integrados.
Contrato: [disponibilidad del Sprint 2](../../specs/05-api/sprint-2-contratos.md).

Estado consolidado al 21/10/2026: integración en `develop`, incluidos reservas,
cancelaciones y bloqueos SQL de CON-73. La [entrega CON-75](CON-75-entrega-sprint-2.md)
reúne la evidencia posterior del equipo; no se repiten pruebas en esta actualización.

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

La integración de CON-41/43 procedente de `develop` persiste las nuevas reservas;
`RESERVAS_REGISTRADAS` conserva una copia de compatibilidad. CON-46 persiste
las cancelaciones y puede adoptar una reserva piloto anterior. Si un UUID
aparece en ambas fuentes, prevalece SQL, incluidos los estados que liberan el
horario. Si la tabla SQL no existe aún, la consulta de disponibilidad utiliza el
almacén piloto. Los errores SQL no se sustituyen por una respuesta vacía:
la consulta responde `503 DISPONIBILIDAD_NO_DISPONIBLE`.

La lectura SQL utiliza las columnas existentes de `reservas` y detecta su zona
mediante `to_jsonb`, para admitir la columna adicional de CON-73 sin exigirla a
las tablas históricas. La consulta no crea tablas ni índices.

**Integrado con CON-73:** `DisponibilidadRepository._leer_bloqueos` consulta
`bloqueos_area` y suma sus intervalos activos al calendario. La creación de
reservas consulta esas mismas ocupaciones dentro de su transacción. No se
implementa una gestión pública de bloqueos.

La creación SQL de CON-41 y las cancelaciones de CON-46 conservan sus resultados
tras reiniciar. Solo las copias piloto anteriores sin registro SQL siguen
dependiendo de la memoria. La exclusión concurrente corresponde a CON-41/43.
La evidencia posterior de calendario, concurrencia y reinicio se referencia en
[CON-73/74](CON-73-CON-74-integracion.md) y en la
[entrega de notificaciones](CON-32-34-36-37-notificaciones.md), que documenta la
restauración integrada de los bloqueos y eventos.

### Antecedente de arranque con la base compartida

Esta sección conserva el diagnóstico de la rama inicial. El estado posterior
del despliegue está documentado en la
[reconciliación a 20261021_0015](reconciliacion-esquema-legacy.md).

Supabase ya registra `20261020_0011`, mientras que la base inicial de esta rama
solo conocía hasta `20261020_0010`. Eso detenía Alembic antes de iniciar la API,
con `Can't locate revision identified by '20261020_0011'`.

Se incorporaron sin modificaciones las revisiones `20261020_0009_pagos` y
`20261020_0011` de `origin/feat/CORE-sprint-2-anderson` (commit `fdb6e01`). La segunda
une los historiales de pagos y catálogo. Se verificó mediante consultas de lectura
que la base ya registra esa cabeza y contiene las tablas de pagos; no se cambió
`alembic_version`, no se ejecutó downgrade ni se incorporó la lógica de pagos de
esa rama. En una base anterior, el arranque sí aplicará las migraciones pendientes.

El 21 de octubre se integró `origin/develop` en `a60d7d5` (PR #20 de Anderson).
Las dos migraciones ya forman parte de esa base compartida. Se conservan la
validación financiera y la actualización de solvencia incorporadas por ese PR,
junto con la consulta de disponibilidad de CON-40. El conflicto del botón de
confirmación se resolvió exigiendo tanto disponibilidad consultada como solvencia
verificada. La revisión manual inicial de Gerardo corresponde a la versión
anterior a esa integración. Los resultados posteriores del equipo se conservan
en CON-73/74 y en la entrega consolidada; no se atribuyen al recorrido inicial.

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
   las nuevas reservas también se guardan en SQL antes de confirmar su respuesta.
8. Para reproducir la integración CON-73/41/46, consultar entre procesos y después
   de reiniciar; incluir el caso de bloqueo operativo activo/inactivo.

En la entrega inicial no se añadieron ni ejecutaron pruebas unitarias o de
integración por indicación del responsable. El 21/10/2026 Gerardo informó un
resultado satisfactorio de su revisión funcional manual. La persistencia y los
bloqueos se integraron posteriormente y cuentan con evidencia del equipo
enlazada arriba. Esta actualización documental reutiliza esa evidencia.
