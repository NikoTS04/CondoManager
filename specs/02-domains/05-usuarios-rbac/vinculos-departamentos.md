# CON-05 / USR-04 — Vínculos persistentes con departamentos

## Identidad, autoridad y tenencia

La administración (`SUPERADMIN` o `ADMIN_JUNTA` de su condominio) vincula una
identidad existente con departamentos reales de ese contexto. El usuario destino
debe tener una asignación de rol en ese condominio; para crear/cambiar/restaurar
un vínculo, esa asignación debe estar vigente. Una cuenta puede estar inactiva
durante su incorporación: vincularla no cambia su estado ni su rol. Auditor y
Residente no administran vínculos. No se crean identidades ni roles implícitos.

Cada par `(usuario_id, departamento_id)` tiene una sola fila en
`usuario_departamentos`. Sus relaciones son `PROPIETARIO_TITULAR`,
`COPROPIETARIO`, `INQUILINO`. Un usuario puede tener varias unidades y relaciones
distintas. Desactivar un vínculo conserva su UUID, relación e historial. Restaurar
reutiliza esa fila. La desactivación sigue permitida si se revocó el rol del usuario.

### Propietario titular

- Una unidad nueva o histórica sin titulares se completa durante el onboarding:
  su primer vínculo activo debe ser `PROPIETARIO_TITULAR`.
- Crear/cambiar/restaurar un copropietario o inquilino exige un titular activo.
- No se puede desactivar ni cambiar la relación del último titular activo.
  Para un traspaso se registra primero otro titular y luego se retira el anterior.
- Puede haber varios titulares. La regla cuenta relaciones activas registradas,
  independientemente del estado de acceso de sus cuentas o roles; tenencia y
  autorización son conceptos distintos.
- Los datos históricos se conservan: consultar una unidad sin titular no inventa
  vínculos; retirar un vínculo histórico no titular permite limpiar el padrón.

Los departamentos inactivos admiten consulta/desactivación de vínculos, pero no
altas ni restauraciones. Todos los identificadores son UUID; ni el número de
unidad ni un valor del cuerpo concede acceso.

## Contrato HTTP

Prefijo `/api/v1`, Bearer obligatorio. Base administrativa:
`/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos`.

| Método | Recurso | Entrada | Respuesta |
|---|---|---|---|
| GET | Base | Sin cuerpo | 200, vínculos activos e inactivos del usuario en ese contexto |
| PUT | Base + `/{departamento_id}` | `{"tipo_relacion":"PROPIETARIO_TITULAR"}` o COPROPIETARIO/INQUILINO; sin campos extra | 200, crea/cambia/restaura el vínculo activo |
| DELETE | Base + `/{departamento_id}` | Sin cuerpo | 200, vínculo con `es_activo=false` |

Cada vínculo devuelve `id`, `usuario_id`, `condominio_id`, `departamento_id`,
`numero`, `edificio_id`, `edificio_nombre`, `tipo_relacion`, `es_activo` y
`departamento_activo`. La consulta exige identidad asignada al condominio; no
expone vínculos de otros contextos. DELETE sin vínculo devuelve 404. PUT idéntico
y DELETE repetido son no-op: no duplican filas ni auditoría, ni cambian revisión.
Los no-op validan la autorización y las precondiciones correspondientes al método.

Errores: 401 de autenticación/sesión revocada; `403 ACCESO_DENEGADO` por actor o
contexto; `404 CONDOMINIO_NO_ENCONTRADO`, `USUARIO_NO_ENCONTRADO`,
`DEPARTAMENTO_NO_ENCONTRADO`, `VINCULO_NO_ENCONTRADO`;
`409 TITULAR_REQUERIDO`, `ROL_NO_VIGENTE`, `DEPARTAMENTO_INACTIVO` o
`VINCULO_DUPLICADO`; `422 DATOS_VINCULO_INVALIDOS`. Nunca se reciben actor,
estado de cuenta, revisión o rol desde el cuerpo.

## Transacciones, auditoría y sesiones

La operación bloquea el usuario destino, sus condominios asociados más el
solicitado en orden UUID y el departamento. Revalida al actor tras los bloqueos.
El bloqueo del contexto coordina cambios de rol/estado/estructura y serializa las
mutaciones de titulares de usuarios distintos. La unicidad del par es durable.

Cada cambio real incrementa `usuarios.auth_revision` y registra
`VINCULO_CREADO`, `VINCULO_CAMBIADO` o `VINCULO_REVOCADO` con departamento, actor
autenticado y estados anterior/posterior. Vínculo, revisión y auditoría confirman
o revierten conjuntamente. No se eliminan cuotas, pagos, reservas ni auditorías.
Los tokens anteriores de cualquier contexto quedan revocados; un nuevo login y
`/auth/me` resuelven los vínculos desde PostgreSQL. Un vínculo o unidad inactivos
no autorizan operaciones. Administrativos sin tenencia siguen siendo válidos.

## Unidades reales en el portal y operaciones

`GET /cuotas/departamentos` utiliza PostgreSQL, ya no el catálogo piloto. Filtra
condominio/unidad activos y, para Residente, sus vínculos activos. Devuelve los
campos previos y añade `edificio_id`, `edificio_nombre` para distinguir unidades
con igual número en edificios distintos. El cliente selecciona siempre por UUID.

La lectura del departamento en reporte/conciliación de pagos y creación de reservas
usa el mismo catálogo SQL y valida pertenencia y estado, también para unidades
recién creadas en Estructura. Los recursos de pagos/reservas conservan los contratos
de sus historias; la autorización por vínculos se aplica antes de operarlos.
`deuda_vencida` suma con Decimal el pendiente de cuotas SQL vencidas existentes,
sin saldos inventados por número. `estado_financiero` procede del departamento;
las reglas completas de solvencia y persistencia financiera corresponden a CON-42/70.

La migración `20261020_0009` añade un índice parcial para consultar titulares activos;
conserva todas las filas y relaciones históricas. El downgrade retira solo el índice.

## Verificación

BDD: `features/vinculos_departamentos.feature`. PostgreSQL real: alta, cambio,
revocación/restauración, relaciones mixtas, dos condominios, unidad/rol inactivos,
último titular y carreras entre usuarios, no-op, rollback y sesiones. Probar desde
navegador una unidad no piloto creada en Estructura, sus vínculos, la selección
de varias unidades y el rechazo de acceso ajeno/revocado. Verificar recarga y reinicio.
