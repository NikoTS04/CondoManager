# CON-04 / USR-03 — Alta y habilitación administrativa

Decisión del Sprint 2: el administrador establece la contraseña inicial. Las cuentas
nuevas están inactivas hasta que un `SUPERADMIN` las habilita desde la aplicación.
La invitación, activación por enlace y verificación del correo pertenecen a una
evolución posterior; `esta_activo` no acredita un correo verificado.

## Identidad y permisos

- Una identidad UUID es global. El correo se normaliza con `strip().lower()` y el
  documento con `strip().upper()`. Ambos son únicos globalmente, también ante
  solicitudes concurrentes. El documento admite 6–20 caracteres alfanuméricos o
  guiones; no se infiere un tipo de documento de los datos históricos.
- `SUPERADMIN` y `ADMIN_JUNTA` crean cuentas en un condominio activo autorizado.
  El alta añade una asignación `RESIDENTE`, sin inventar vínculos de departamentos.
  La gestión de otros roles y vínculos se completa en CON-06 y CON-05.
- Solo `SUPERADMIN` cambia `esta_activo`. Este estado afecta a la identidad en
  todos sus condominios. La consulta y la operación seleccionan un condominio al
  que pertenece el usuario y verifican esa pertenencia en PostgreSQL.
- `usuarios.es_superadmin` es una concesión global persistida, no editable por
  estas API. Las filas de `usuario_roles` conservan `condominio_id NOT NULL`;
  una fila contextual con texto `SUPERADMIN` no otorga privilegios globales.
- La contraseña inicial tiene 8–128 caracteres y se guarda exclusivamente con el
  hash PBKDF2-SHA256 del módulo común de seguridad. No se devuelve ni se audita.

## Contrato HTTP

Todas las rutas usan `/api/v1`. Los cuerpos rechazan campos adicionales.

| Operación | Cuerpo / parámetros | Resultado |
|---|---|---|
| `POST /condominios/{cid}/usuarios` | `email`, `password`, `nombre`, `apellido`, `documento_identidad`, `telefono` opcional | `201`, cuenta inactiva con asignación `RESIDENTE`. |
| `GET /condominios/{cid}/usuarios` | `limit` 1–100 (50), `offset` >= 0 | `200`, cuentas del contexto, incluidas las inactivas; administración autorizada. |
| `PATCH /usuarios/{id}/estado?condominio_id={cid}` | `{"esta_activo": true}` o `false` | `200`, cuenta persistida; solo `SUPERADMIN`. |
| `POST /auth/login` | `email`, `password`, `condominio_id` opcional | `200`, token y perfil persistido. |
| `GET /auth/me` | Bearer | `200`, perfil y vínculos vigentes. |

La cuenta administrativa devuelve `id`, `email`, `nombre`, `apellido`, `telefono`,
`documento_identidad`, `esta_activo` y `creado_en`; nunca hashes ni revisiones internas.
El login mantiene el perfil público v2 y añade al JWT `auth_revision` positivo.
Un usuario con varias asignaciones elige el contexto: sin selección se responde
`409 CONTEXTO_REQUERIDO` con `detalles.condominios` (UUID y nombre), exclusivamente
después de validar contraseña y cuenta activa. Un SuperAdmin inicia en contexto global.

Errores canónicos: `401 CREDENCIALES_INVALIDAS` (incluye cuentas inactivas),
`401 SESION_REVOCADA`, `403 ACCESO_DENEGADO`, `404 USUARIO_NO_ENCONTRADO` o
`CONDOMINIO_NO_ENCONTRADO`, `409 USUARIO_DUPLICADO`,
`422 DATOS_USUARIO_INVALIDOS`. El JSON usa `error_code`, `mensaje` y `detalles`
opcionales. Los errores de validación nunca incluyen la contraseña recibida.

## Transacciones, auditoría y sesiones

- Alta, asignación inicial y auditoría `ALTA_USUARIO` se confirman conjuntamente
  antes de devolver éxito. Un fallo revierte toda la operación.
- Un cambio real de estado incrementa `usuarios.auth_revision` y registra
  `USUARIO_ESTADO_CAMBIADO` en los condominios asociados, con el actor autenticado
  y los estados anterior/posterior. Los bloqueos de condominio se ordenan por UUID
  para serializar la cadena de auditoría. Repetir el estado es un no-op.
- Cada petición protegida verifica identidad activa y revisión en PostgreSQL,
  resuelve su rol vigente y filtra vínculos por condominio. Una cuenta desactivada
  pierde acceso en su siguiente solicitud; reactivarla exige un nuevo login.
  `session_version = 2` describe el formato, no la revisión individual.
- Las mutaciones vuelven a validar al actor tras tomar los bloqueos transaccionales.
  Las rutas de SuperAdmin utilizan el mismo control persistente.

## Migración y demostración

La migración crea o valida/adopta `usuarios`, `usuario_roles` y
`usuario_departamentos`, preserva estados y registros existentes, cambia el default
de las nuevas cuentas a `false` y añade la revisión y concesión global. La unicidad
normalizada se valida antes de crear índices; las colisiones históricas se informan
sin borrar o fusionar identidades. El downgrade conserva tablas adoptadas.

Los seis perfiles demo se cargan explícitamente en una base de demostración mediante
`python -m scripts.seed_usuarios_demo`, después de migrar. El script crea contexto,
estructura y vínculos piloto coherentes con sus UUID, usa contraseñas conocidas de
prueba y deja activas solamente las cuentas que crea. Al reejecutarse no restablece
contraseñas, permisos ni estados de cuentas existentes. El login no tiene fallback
en memoria. `/auth/demo-users` solo está disponible con `DEMO_MODE=true` y devuelve
perfiles de las cuentas demo persistidas.

El primer SuperAdmin real se provisiona mediante
`python -m scripts.crear_superadmin` (contraseña por entrada interactiva). La
concesión global no requiere crear un condominio ficticio.

## Evidencia requerida

BDD ejecutable: `features/alta_usuarios.feature`. Pruebas en PostgreSQL real de alta
inactiva, normalización y carreras de unicidad, activación exclusiva de SuperAdmin,
revocación/reactivación, rollback de auditoría, no-op, aislamiento de dos condominios,
login con varios contextos y conservación tras nuevas sesiones/reinicio. La UI debe
permitir crear cuentas y al SuperAdmin editar su estado, mostrando errores reales.
