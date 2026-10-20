# CON-06 / USR-05 — Roles y permisos persistentes

## Modelo y autoridad

Los roles canónicos siguen siendo `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR` y
`RESIDENTE`. Propietario, copropietario e inquilino son relaciones con unidades,
no roles. `usuarios.es_superadmin` es una concesión global provisionada por CLI;
ningún cuerpo de esta API permite concederla ni modificarla.

Cada par `(usuario_id, condominio_id)` tiene como máximo una asignación en
`usuario_roles`. CON-06 añade `es_activo BOOLEAN NOT NULL DEFAULT true`: revocar
conserva la fila, su rol y la auditoría. Reactivar utiliza la misma asignación.
Las asignaciones históricas quedan activas al migrar. Una fila contextual con rol
`SUPERADMIN` heredada no concede privilegios globales ni permite iniciar sesión.
El downgrade rechaza bajar con asignaciones revocadas para no rehabilitarlas
implícitamente en una revisión que carece de la columna de actividad.

| Acción | SUPERADMIN | ADMIN_JUNTA | AUDITOR / RESIDENTE |
|---|---|---|---|
| Consultar asignaciones | Cualquier condominio activo | Su condominio | No |
| Asignar/revocar ADMIN_JUNTA | Sí | No | No |
| Asignar/revocar AUDITOR y RESIDENTE | Sí | Su condominio, solo si el rol anterior también es AUDITOR/RESIDENTE | No |
| Incorporar una identidad existente sin asignación al contexto | Sí, por UUID explícito | No | No |
| Modificar la propia asignación o una identidad SuperAdmin global | No | No | No |

Junta no modifica a otra Junta, aunque su asignación esté revocada. SuperAdmin
puede sustituir una asignación contextual heredada no operativa. Todos los
intentos de autoasignación, elevación y cruce de contexto se rechazan en backend.
Una asignación no activa una cuenta inactiva ni crea vínculos con departamentos.

## Contrato HTTP

Base: `/api/v1/condominios/{condominio_id}/usuarios/{usuario_id}/rol`.
Requiere Bearer y UUID válidos.

| Método | Entrada | Respuesta |
|---|---|---|
| GET | Sin cuerpo | 200, asignación persistida, incluso revocada |
| PUT | `{"rol":"ADMIN_JUNTA"}` / `AUDITOR` / `RESIDENTE`; sin campos extra | 200, crea, cambia o reactiva la asignación |
| DELETE | Sin cuerpo | 200, asignación con `es_activo=false` |

Respuesta: `usuario_id`, `condominio_id`, `rol`, `es_activo`. El rol de lectura
admite los cuatro valores SQL para identificar asignaciones heredadas. PUT solo
admite los tres roles contextuales. GET/DELETE sin asignación responden 404.
PUT de Junta sin asignación responde el mismo 404, sin revelar identidades ajenas.

`GET /condominios/{cid}/usuarios` mantiene los campos de cuenta de CON-04 y añade
`rol`, `rol_activo` y `es_superadmin` de solo lectura. Incluye asignaciones
revocadas para permitir su gestión. POST de alta y PATCH de estado conservan sus
respuestas de cuenta anteriores.

Errores: `401 NO_AUTENTICADO` / `SESION_REVOCADA`, `403 ACCESO_DENEGADO`,
`404 CONDOMINIO_NO_ENCONTRADO` / `USUARIO_NO_ENCONTRADO` / `ROL_NO_ENCONTRADO`,
`422 DATOS_ROL_INVALIDOS`. No se aceptan roles de tenencia, campos globales,
estado de cuenta, ni identificadores de actor enviados por el cliente.

## Transacción, sesiones y concurrencia

Crear/cambiar/reactivar/revocar una asignación incrementa una vez la
`auth_revision` global del usuario y registra `ROL_ASIGNADO`, `ROL_CAMBIADO` o
`ROL_REVOCADO` en el condominio afectado. El actor procede de la sesión y la
auditoría contiene las instantáneas de asignación anteriores/posteriores, nunca
contraseñas. Auditoría, revisión y asignación confirman o revierten conjuntamente.

La operación bloquea primero el usuario destino y luego sus condominios asociados
más el solicitado en orden UUID; vuelve a validar al actor tras los bloqueos.
Esto serializa la unicidad del par, los cambios de estado y la cadena de auditoría.
Dos PUT idénticos concurrentes producen una sola mutación/auditoría. Repetir el
rol activo o una revocación no cambia revisión ni auditoría.

Login y todas las rutas protegidas solo utilizan asignaciones activas en
condominios activos. Una revocación excluye ese contexto del selector de login;
si no queda ninguno, las credenciales se rechazan. Los JWT previos de cualquier
contexto quedan revocados; el siguiente login emite el rol vigente. Restablecer
el rol anterior no recupera tokens viejos. Los vínculos de departamentos y sus
historiales se conservan y siguen aplicando cuando el rol vigente es RESIDENTE.

## Evidencia

BDD: `features/roles_permisos.feature`. Integración sobre migraciones y PostgreSQL
real: permisos por actor, roles inválidos, dos condominios, asignación inicial,
revocación/reactivación, sesiones, no-op, concurrencia, rollback de auditoría y
migración/downgrade. La sección Usuarios permite editar/revocar/restaurar roles;
SuperAdmin puede incorporar una identidad existente por UUID. Probar cambio de
portal y eliminación de privilegios desde navegador, recarga y reinicio de API.
