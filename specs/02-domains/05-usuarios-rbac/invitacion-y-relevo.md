# CON-76 / CON-7 — Invitación, activación y relevo de accesos

## Identidad y autoridad

La identidad sigue siendo global y los cuatro roles no cambian. La nueva alta por
invitación coexiste con el contrato histórico de alta manual. No migra contraseñas,
no activa cuentas existentes y no concede SuperAdmin. Junta invita residentes de su
condominio; SuperAdmin puede gestionar después sus roles con las API existentes.
Una identidad ya registrada se incorpora mediante la asignación explícita existente,
nunca mediante una invitación que restablezca su contraseña.
Si se cambian roles o vínculos durante el onboarding, reenviar la invitación al
terminar esa configuración: el enlace anterior conserva la revisión de permisos
con la que se emitió y ya no activa la cuenta.

## Contrato HTTP (prefijo /api/v1)

Las mutaciones de invitación y relevo requieren `Idempotency-Key` UUID. La misma
clave, condominio, actor, operación y cuerpo devuelve el resultado original sin
repetir efectos; cambiar actor, operación o cuerpo con esa clave devuelve
`409 IDEMPOTENCIA_CONFLICTO`. La autorización se comprueba también al repetir.

| Operación | Entrada | Resultado |
|---|---|---|
| POST /condominios/{cid}/invitaciones | email, nombre, apellido, documento_identidad, telefono opcional; sin contraseña | 201, invitación pendiente y aviso EN_COLA |
| GET /condominios/{cid}/invitaciones | limit 1..100 (50), offset >= 0 | Invitaciones del contexto con estado y estado del correo; sin secretos |
| POST /condominios/{cid}/invitaciones/{id}/reenviar | Sin cuerpo | Nueva invitación; la anterior queda revocada |
| DELETE /condominios/{cid}/invitaciones/{id} | Sin cuerpo | Revocación lógica idempotente |
| POST /auth/activar | token y password (8..128 caracteres) | Cuenta activada; requiere login posterior |
| POST /condominios/{cid}/relevos | tipo JUNTA/INQUILINO, saliente_id, entrante_id, departamento_id para inquilino; rol_saliente RESIDENTE/AUDITOR/null para Junta | Cambio de ambos usuarios en una transacción |

El token se genera con 256 bits aleatorios, dura 24 horas por defecto (configurable),
se valida por SHA-256 y se consume bajo bloqueo SQL junto con la contraseña y la
activación. Un GET nunca lo consume. Errores: `ACTIVACION_INVALIDA`,
`ACTIVACION_USADA`, `ACTIVACION_EXPIRADA`, `ACTIVACION_REVOCADA` y
`ACTIVACION_NO_AUTORIZADA` (409 para usada, 400 para las demás). La revisión de
cuenta guardada al invitar debe seguir vigente; una deshabilitación administrativa,
una revocación del rol o un condominio inactivo impiden activar. El alta manual no
puede habilitar una cuenta pendiente de invitación; debe completar su activación.

## Transacción y correo

Identidad, asignación inicial, invitación, auditoría y aviso SQL confirman juntos.
La cola durable existente actúa como outbox; reintentar transporte nunca recrea
usuarios. Finalidades distintas: OPERATIVA exige departamento y acceso vigente;
INVITACION revalida invitación pendiente/cuenta/contexto; SEGURIDAD valida un
cambio auditado y el contacto del afectado, aunque ya no tenga acceso operativo.
Solo los productores internos crean las dos finalidades de identidad.

El token solo tiene hash en la invitación. El material de entrega se cifra con
Fernet y una clave externa `IDENTITY_DELIVERY_KEY`, compartida por API y worker.
Los cuerpos consultables están redactados; el ciphertext no forma parte de DTO,
eventos ni auditoría. El enlace usa fragmento `/activar#token=...` y solo el POST
envía el token a la API. No guardar secretos en logs ni parámetros de URL.

Los avisos de identidad usan transporte PROVEEDOR; nunca SIMULADO por defecto.
El adaptador del worker puede inyectarse para pruebas. Sin proveedor configurado,
el envío falla de forma trazable y genera alerta, sin revertir el control de acceso.
ENVIADO acredita aceptación, no entrega. Una aceptación incierta requiere revisión
antes de reenvío; el contrato conserva los intentos/reintentos existentes de CON-78.

## Relevos

Solo SuperAdmin releva Junta. El saliente deja de ser ADMIN_JUNTA y el rol final es
explícito (RESIDENTE, AUDITOR o revocado); no se desactiva globalmente su cuenta.
Los dos usuarios deben existir y el entrante tener asignación contextual vigente.
Un relevo de inquilino exige un vínculo INQUILINO activo del saliente, un titular
activo y unidad vigente; conserva los demás vínculos. Retirar al responsable de
pago limpia la designación y aumenta su versión, sin cambiar cuotas históricas.
El reemplazo se puede designar después mediante condiciones de pago.

Se reutilizan las mutaciones de roles/vínculos, con un único commit para el relevo.
Cada cambio real conserva auditoría y encola un aviso al afectado en la misma
transacción; las operaciones idénticas son no-op. El JWT anterior queda revocado
en la siguiente petición por auth_revision. Pagos, cuotas y reservas no se borran.

## Seguridad y verificación

Duración JWT y expires_in proceden de ACCESS_TOKEN_EXPIRE_MINUTES positivo.
Los rechazos de autenticación/autorización registran actor validado cuando exista,
ruta, contexto UUID solicitado, código, estado y correlación; nunca cuerpo,
Authorization, contraseña, token de invitación o query completa.

Probar PostgreSQL: unicidad, repetición, concurrencia de activación/reenvío,
revocación, expiración, rollback de auditoría/cola, dos condominios, conservación de
cuentas existentes, responsable de pago, relevo atómico y avisos sin vínculo activo.
Probar navegador: invitación, contraseña elegida, login, errores de enlace,
relevo y rechazo del token anterior. Correo real requiere el proveedor CON-78 y
un buzón de prueba autorizado; transporte de prueba no acredita su aceptación.
