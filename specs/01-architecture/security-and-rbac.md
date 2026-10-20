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
- El JWT del piloto dura 24 horas. No hay refresh token implementado; la renovación
  se realiza mediante login. Las asignaciones incluidas en el JWT son una instantánea
  válida hasta expirar o renovar la sesión.

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

El directorio de login y los recursos de pagos/reservas/notificaciones siguen siendo
catálogos piloto en memoria. Sus identidades UUID se generan de forma coherente a
partir de `CONDOMINIO_PILOTO_ID`; sin configuración se usa el espacio demo aislado.
La alineación de roles no convierte estos módulos en persistencia SQL.

El SQL exige `usuario_roles.condominio_id NOT NULL`: representa una **asignación
persistida por condominio**. El `condominio_id: null` del `SUPERADMIN` piloto es un
**contexto activo global de sesión**, no una fila de `usuario_roles`. Antes de
conectar el login a usuarios reales debe resolverse la concesión global y la
selección de asignaciones; no se cambia ni se relaja la restricción SQL.

Egresos, proveedores, tickets, exportación de balances y traspaso de Junta son
capacidades documentales futuras; no amplían los permisos de los endpoints actuales.
