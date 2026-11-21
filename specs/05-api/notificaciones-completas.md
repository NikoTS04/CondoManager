# PROC-03 — cierre de correo transaccional y comunicaciones

## Comunicados

Solo EMAIL. SuperAdmin/Junta escriben, Auditor consulta, residentes no acceden a
audiencias ni lotes administrativos. Todo acceso valida condominio y sesión SQL.
`POST /notificaciones/comunicados/previsualizar`: cuerpo del comunicado y filtros
opcionales `edificio_ids`, `departamento_ids`, `usuario_ids` (listas UUID, intersección).
Vacío significa todo el condominio. IDs ajenos/inexistentes se rechazan sin filtrar
datos. Se muestra un aviso por usuario, no por cada departamento del mismo usuario.
Devuelve borrador persistido con id, contenido, audiencia y cantidad. No envía.

`POST /notificaciones/comunicados/{id}/confirmar`: confirmación idempotente del
borrador (15 minutos). Revalida audiencia y contenido; un cambio de contacto,
acceso o supresión devuelve 409 y exige nueva previsualización. Una confirmación
repetida devuelve el mismo lote incluso pasada su caducidad. Cola y confirmación
se confirman en una transacción; cada lote se audita.
`GET /notificaciones/comunicados?condominio_id=UUID`: últimos 50 lotes con conteos
de EN_COLA, ENVIADO, ENTREGADO, REINTENTANDO, FALLIDO_PERMANENTE y OMITIDO.
El endpoint histórico `/comunicado-masivo` mantiene compatibilidad local; en
producción exige el flujo de previsualización/confirmación (409), sin envíos ciegos.

## Operación y contactos

`GET /notificaciones/operacion?condominio_id=UUID`: resumen contextual de cola,
antigüedad, alertas abiertas, inciertos y última ejecución del job (sin secretos).
Marca revisión del programador tras 5 minutos sin éxito y cola atrasada tras
15 minutos; solo cuando el proveedor está habilitado.
`GET /notificaciones/contactos-bloqueados?condominio_id=UUID`: direcciones suprimidas.
Rebote, blocked y spam del proveedor suprimen el contacto en ese condominio;
el worker descarta nuevos intentos como OMITIDO. Cambiar el email no desbloquea
la dirección original. `POST /notificaciones/contactos-bloqueados/{cid}/reactivar`
exige email y motivo, autorización, revalidación de sesión y auditoría.

`POST /notificaciones/{id}/resolver-incierto`: ciclo e intento esperados, decisión
ACEPTADO/NO_ACEPTADO/DESCARTAR y referencia/motivo de revisión en Mailjet.
ACEPTADO exige MessageID y marca ENVIADO, nunca ENTREGADO. NO_ACEPTADO exige
confirmación humana explícita y crea un ciclo nuevo tras verificar elegibilidad
del destinatario. DESCARTAR marca OMITIDO. No se presupone que el proveedor
permita probar ausencia de un envío con su CustomID. Concurrencia/ciclo cambiado:
409; no se autoriza reenvío ciego. Se conserva el historial y se audita la decisión.

## Recordatorios

`GET/PUT /notificaciones/configuracion/{cid}`: días de anticipación (0–30, únicos,
máximo 10, default [3,0]), hora local de Lima (0–23, default 8), habilitado.
Toda modificación se audita. La primera ejecución inicia en el día actual, sin
inventar campañas históricas. Un cursor diario durable recupera días posteriores
perdidos (máximo 31 días por pasada, sin descartar backlog). El worker vuelve a
leer deuda, vencimiento y moneda antes de enviar: cuota pagada/cambiada se omite,
abono parcial actualiza el importe. Nuevas políticas se aplican desde su modificación;
no reenvían recordatorios ya emitidos. No hay WhatsApp/SMS/PUSH productivos.

## Solvencia

Al conciliar APROBADO y pasar de deuda vencida positiva a cero, se persiste en
la misma transacción `SolvenciaRestablecidaEvent` en outbox propio. Una revisión
repetida no crea otro evento. Se notifica la rehabilitación de reservas sin afirmar
que no existan cuotas futuras. No se modifican cálculos ni reglas financieras.

Requiere migración 0022 antes del deploy. Envíos desactivados durante aceptación.
Las cinco tablas nuevas son internas del backend: en Supabase deben tener RLS
habilitado sin políticas públicas. El rol propietario de la conexión PostgreSQL
y el rol privado service_role conservan su acceso; anon/authenticated no deben
leer audiencias, supresiones ni eventos directamente mediante PostgREST.
