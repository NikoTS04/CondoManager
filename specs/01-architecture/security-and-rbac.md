# Seguridad y Control de Acceso (Security & RBAC)

## 1. Identidad y fuente de verdad

`condomanager_schema.sql` define exactamente cuatro roles de autorización:
`SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR` y `RESIDENTE`.
Propietario e inquilino son perfiles funcionales de un residente, determinados por
`usuario_departamentos.tipo_relacion`: `PROPIETARIO_TITULAR`, `COPROPIETARIO` o
`INQUILINO`. La relación pertenece a cada vínculo, nunca al rol global del usuario.
Una misma persona puede ser propietaria de una unidad e inquilina de otra.

Contrato detallado: [identidad-y-alcances.md](../02-domains/05-usuarios-rbac/identidad-y-alcances.md).

## 2. Matriz de permisos implementados

| Recurso / operación | SUPERADMIN | ADMIN_JUNTA | AUDITOR | RESIDENTE |
|---|---|---|---|---|
| Crear y listar condominios globalmente | Sí | No | No | No |
| Consultar estructura, presupuestos y distribución | Cualquier condominio | Su condominio | Su condominio | No |
| Modificar estructura, aprobar presupuestos y emitir cuotas | Sí | Su condominio | No | No |
| Consultar unidades del portal, comprobantes y reservas | Contexto seleccionado | Su condominio | Su condominio | Sus vínculos activos |
| Reportar pagos, crear/cancelar reservas | Soporte | Soporte de su condominio | No | Sus vínculos activos |
| Conciliar pagos, evaluar moras y enviar/reintentar comunicados | Sí | Su condominio | No | No |
| Consultar bitácora de comunicaciones | Contexto seleccionado | Su condominio | Su condominio | No |
| Asignar/revocar ADMIN_JUNTA | Sí, excepto propia asignación o identidad global | No | No | No |
| Asignar/revocar AUDITOR y RESIDENTE | Sí | Su condominio, sin modificar Junta ni su propia asignación | No | No |
| Crear/cambiar/revocar vínculos de departamentos | Contexto seleccionado | Su condominio | No | No |

Todas las rutas de negocio requieren Bearer JWT. Ausencia de token: `401`;
rol/contexto/unidad no autorizados: `403`. No existe un modo anónimo de desarrollo.
La consulta del calendario de disponibilidad devuelve únicamente horarios ocupados,
sin datos del departamento que reservó.

## 3. Contexto y renovación de sesión

- JWT firmado HS256: `sub`, `rol`, `condominio_id`, `departamentos`, `session_version`,
  `iat`, `exp`; el login añade `email`, `nombre` y `apellido` sin truncarlos.
- `departamentos` es un arreglo de vínculos con `departamento_id` UUID, `numero`,
  `tipo_relacion` y `es_activo`. Solo se autoriza mediante UUID y vínculo activo.
- Administrativos sin tenencia: `departamentos: []`; no se inventan relaciones
  `ADMINISTRADOR`, `AUDITOR` o `SUPERADMIN`. No hay relación de tenencia de usuario.
- Un token antiguo, con rol desconocido, con vínculos antiguos o sin
  `session_version: 2` responde `401 SESION_DESACTUALIZADA`. Se debe iniciar sesión
  de nuevo. `SISTEMA_AUTOMATICO` sigue siendo un actor interno, nunca un rol de login.
- El frontend restaura la sesión consultando `/auth/me`, descarta cachés de roles
  antiguos y valida el UUID seleccionado en URL/localStorage contra los vínculos.
- El JWT dura 24 horas. No hay refresh token; la renovación se realiza mediante login.
  `auth_revision` identifica la revisión persistida de la cuenta. Toda ruta protegida
  comprueba estado activo, revisión, asignación y contexto vigentes. Desactivar y
   reactivar una cuenta invalida los tokens previos, incluso antes de su expiración.

CON-06 aplica la misma revisión global a los cambios reales de asignación. Solo
`usuario_roles.es_activo=true` autoriza un contexto. Revocar conserva la fila y
sus vínculos; repetir el rol/estado no modifica revisión ni auditoría. Contrato:
[roles y permisos](../02-domains/05-usuarios-rbac/roles-y-permisos.md).

## 4. Aislamiento y reglas de negocio

El condominio recibido en ruta, query o body selecciona un recurso, pero no concede
permisos. Salvo `SUPERADMIN`, debe coincidir con el contexto firmado del usuario.
Cada operación comprueba también el condominio real del recurso. No se aceptan
departamentos desconocidos como solventes. `AUDITOR` solo tiene permisos de lectura.

Un residente solo puede reportar pagos o crear/cancelar reservas de sus vínculos
activos en el contexto de sesión. La mora se evalúa por unidad. La cancelación de un
residente requiere al menos 24 horas de anticipación; el servidor deriva el permiso
administrativo del rol e ignora cualquier intento de elevarlo mediante `es_admin`.

## 5. Piloto y persistencia

CON-05 administra vínculos persistentes, invalida sesiones en cada cambio real y
resuelve unidades del portal y de operaciones de pagos/reservas desde PostgreSQL.
La relación de titular se conserva aunque la cuenta no tenga acceso. Contrato:
[vínculos](../02-domains/05-usuarios-rbac/vinculos-departamentos.md).

CON-04 utiliza identidades, roles y vínculos persistentes para login y autorización.
Los recursos de pagos/reservas/notificaciones conservan su estado piloto hasta sus
entregas de persistencia. Los datos demo se provisionan explícitamente y el login
siempre consulta PostgreSQL. Véase [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md).

El SQL exige `usuario_roles.condominio_id NOT NULL`: representa una **asignación
persistida por condominio**. El `condominio_id: null` del `SUPERADMIN` piloto es un
**contexto activo global de sesión**, no una fila de `usuario_roles`. La concesión
global persistida se representa mediante `usuarios.es_superadmin`, provisionada por
CLI; las API de alta y estado no modifican esa concesión. Se conserva la restricción SQL.

Egresos, proveedores, tickets, exportación de balances y traspaso de Junta son
capacidades documentales futuras; no amplían los permisos de los endpoints actuales.
