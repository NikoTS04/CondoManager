# CON-39 / RES-01 — Catálogo persistente de áreas comunes

## Modelo y condiciones

`areas_comunes` es la fuente de verdad: UUID, condominio, edificio opcional,
nombre, descripción, aforo, costo por reserva, duración máxima y estado activo.
CON-39 incorpora apertura y cierre diarios. Los atributos de edificio y duración
ya presentes en el SQL histórico se respetan al adoptar la tabla.

- Nombre normalizado con `strip()`, 1–100 caracteres; descripción opcional hasta
  4000 caracteres. Los UUID distinguen áreas con igual nombre.
- Aforo entero estricto 1–2147483647. No se recibe cantidad de asistentes al reservar;
  el aforo es una condición publicada del área.
- Costo no negativo `NUMERIC(12,2)`, recibido como cadena decimal de hasta diez
  dígitos enteros y dos decimales. Se calcula con Decimal, nunca float. La moneda
  es la del condominio (PEN/USD) y se devuelve de solo lectura.
- `hora_apertura` y `hora_cierre`: `HH:MM`, sin zona, segundos ni cruce de medianoche;
  apertura < cierre. Se interpretan todos los días en **America/Lima**. Las reservas
  nuevas usan esas mismas horas locales y conservan esa zona para aplicar la regla
  de cancelación de 24 horas (incluido el límite exacto). Los registros anteriores
  sin marca de zona mantienen su interpretación UTC histórica.
- `tiempo_maximo_horas`: entero estricto 1–24 en nuevas configuraciones. El costo es
  por turno, no por hora. La reserva debe quedar dentro de apertura/cierre y no
  superar la duración máxima; los límites exactos son válidos.
- `edificio_id=null`: uso compartido del condominio. Si existe, el edificio debe
  pertenecer al mismo contexto. Un residente solo consulta áreas exclusivas de
  edificios con alguna unidad activa vinculada; una reserva debe utilizar una
  unidad de ese edificio. Los administrativos respetan también esa compatibilidad
  entre área y departamento al reservar.
- Crear deja `esta_activa=true`. Editar conserva el estado. Desactivar impide nuevas
  reservas y excluye el área del catálogo activo, pero no borra ni cancela reservas.
  Un cambio de costo o nombre no reescribe la instantánea de reservas anteriores.
  La respuesta de una reserva nueva incluye su moneda para presentar correctamente
  la tarifa, incluso cuando el área se desactiva o cambia de precio después.

## Autoridad y API

Todas las rutas requieren Bearer validado contra PostgreSQL y usan `/api/v1`.
SuperAdmin administra cualquier condominio activo; Junta solo el suyo. Auditor
consulta el catálogo administrativo de su contexto; Residente solo el catálogo activo.

| Método | Recurso | Entrada / resultado |
|---|---|---|
| GET | `/condominios/{cid}/areas` | Todas, incluidas inactivas; `limit` 1–100 (50), `offset` >=0 y `esta_activa` opcional. 200 |
| POST | `/condominios/{cid}/areas` | Configuración completa; 201 |
| GET | `/condominios/{cid}/areas/{aid}` | Consulta administrativa, incluso inactiva; 200 |
| PUT | `/condominios/{cid}/areas/{aid}` | Reemplaza configuración; conserva UUID, contexto y estado; 200 |
| PATCH | `/condominios/{cid}/areas/{aid}/estado` | `{"esta_activa":true|false}` estricto; 200 |
| GET | `/areas?condominio_id={cid}` | Catálogo SQL activo autorizado del portal; 200 |

POST/PUT requieren `nombre`, `aforo_maximo`, `costo_reserva`, `hora_apertura`,
`hora_cierre`, `tiempo_maximo_horas`; `descripcion` y `edificio_id` son opcionales
(null). Rechazan campos extra, incluido estado, contexto o actor. No hay DELETE.
La respuesta añade a esos campos `id`, `condominio_id`, `esta_activa`, `moneda`,
`zona_horaria` y `edificio_nombre` (null en áreas compartidas). Horas `HH:MM` y
costos con dos posiciones decimales.

Errores: `401 NO_AUTENTICADO` / `SESION_REVOCADA`, `403 ACCESO_DENEGADO`,
`404 CONDOMINIO_NO_ENCONTRADO`, `AREA_NO_ENCONTRADA`, `EDIFICIO_NO_ENCONTRADO`,
`422 DATOS_AREA_INVALIDOS`. Reservar/consultar disponibilidad de un área inactiva
devuelve `409 AREA_INACTIVA`. Un turno fuera del horario o duración devuelve
`400 HORARIO_INVALIDO`, sin ocupar el calendario. Ningún error revela datos de
otro condominio o acepta costo/estado enviados como sustituto del catálogo SQL.

## Transacciones e integración con reservas

Crear/editar/cambiar estado bloquea el condominio y el área, revalida la sesión del
actor tras los bloqueos y confirma con su auditoría en una sola transacción. Registra
`AREA_CREADA`, `AREA_ACTUALIZADA`, `AREA_ESTADO_CAMBIADO`, actor real y fotografías
anterior/posterior sin secretos; la cadena comparte el bloqueo contextual de PROC-05.
Repetir configuración o estado es un no-op, sin nueva auditoría.

La creación de reserva toma los mismos bloqueos antes de leer las condiciones SQL
y mantiene el bloqueo hasta terminar la petición. Una desactivación confirmada
primero impide la reserva; si la reserva se admite primero, el cambio de estado
posterior conserva su historial. Se prueban ambas condiciones con sesiones reales.
Las consultas de reservas históricas autorizadas no exigen que el área siga activa.

**Coordinación CON-73:** esta entrega crea/adopta y persiste el catálogo. Las próximas
migraciones de reservas/notificaciones parten de esta revisión y reutilizan la
tabla, sin duplicarla. La persistencia completa de reservas y su exclusión entre
procesos pertenecen a CON-73/CON-43; el calendario actual conserva su implementación.

## Migración y datos demo

`20261020_0010` crea o valida/adopta `areas_comunes`, sus FK y checks compatibles.
Añade edificio/duración cuando falten y horas con defaults `00:00`–`23:59` para
preservar la amplitud de uso de registros históricos. No cambia costos, estados,
identidades, asociaciones ni reservas existentes. Valida compatibilidad y pertenencia
del edificio antes de continuar; no corrige datos históricos silenciosamente.

El downgrade retira las horas y el índice de esta entrega. Solo elimina una tabla
creada por esta migración si está vacía y sin referencias externas; conserva tablas
adoptadas o con datos/referencias y sus atributos base, incluido edificio/duración.

`python -m scripts.seed_areas_demo`, después de migrar y preparar el condominio demo,
carga explícitamente las cuatro áreas conocidas con sus UUID de demostración. No hay
fallback de catálogo en memoria. Reejecutar no cambia condiciones/estados de áreas
existentes ni reasigna un UUID de otro contexto. Los tests y el guion de demostración
preparan estas áreas explícitamente.

## Evidencia

BDD: `features/catalogo_areas.feature`. PostgreSQL real: CRUD, permisos, dos contextos,
edificio exclusivo, dinero exacto, horarios/límites, estado y no-op, rollback de
auditoría, bloqueo concurrente y adopción/downgrade conservadores. Navegador:
crear/editar/desactivar desde administración, condiciones visibles y reserva válida
en el portal, rechazo de área inactiva, lectura por Auditor, móvil y reinicio de API.
