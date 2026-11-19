# CON-78 / CON-33 — Correo transaccional real y recordatorios · Alejandro

Plan: [Sprint 3](SPRINT-3.md#con-78--correo-transaccional-real--alejandro). Política:
[entrega y reintentos §5](../../specs/02-domains/03-notificaciones/delivery-policy.md#5-transporte-smtp-real-con-78).

## Estado

| Ticket | Estado | Rama |
|---|---|---|
| [CON-78](https://tarquisoncco2.atlassian.net/browse/CON-78) | Primer incremento: adaptador SMTP, selección de transporte y aceptación incierta. Pendiente contrato de identidad (CON-76) y demo con proveedor real. | `feat/PROC-03-con78-correo-real` |
| [CON-33](https://tarquisoncco2.atlassian.net/browse/CON-33) | Implementado: programación diaria, deduplicación SQL, revalidación bajo bloqueo y supresión. Pendiente: confirmar con Anderson el instante de elegibilidad (propuesta abajo) y recibir el recordatorio en correo real. | `feat/PROC-03-con78-correo-real` |

## CON-78 — Qué entrega este incremento

- `transporte_smtp.py`: adaptador SMTP (STARTTLS, SSL o sin TLS) configurado por entorno, con timeout y resultados normalizados: aceptado, temporal, rebote definitivo, contenido rechazado y **aceptación incierta**. No guarda textos del servidor.
- El transporte se fija al encolar (`PROVEEDOR` solo para EMAIL con `EMAIL_TRANSPORTE=SMTP`). El worker atiende cada fila con su transporte; una fila `PROVEEDOR` nunca se acredita con el simulado y, sin configuración, mantiene `PROVEEDOR_NO_CONFIGURADO` con alerta.
- Aceptación incierta (sin respuesta tras transmitir el contenido): `FALLIDO_PERMANENTE` + alerta `ACEPTACION_INCIERTA`, sin reenvío automático. Cada intento lleva `Message-ID` estable `<log-ciclo-intento@dominio>` para reconciliar con el proveedor.
- SMTP acredita `ENVIADO` (aceptación); `ENTREGADO` queda reservado a evidencia posterior del proveedor.
- Docker Compose: servicio Mailpit para desarrollo (`http://localhost:8025`), variables SMTP en API y worker; `.env.example` documentado.

### Plantillas de identidad (`src/modules/usuarios/comunicaciones.py`)

Las tres se encolan como `Notificacion` con `transporte=PROVEEDOR`, `canal=EMAIL`, sin `departamento_id`, y el worker las revalida con `destinatario_identidad_valido` justo antes de enviar. Si la revalidación falla, la fila pasa a `FALLIDO_PERMANENTE` con alerta `DESTINATARIO_INVALIDO`. Ninguna usa la revalidación de mensajes operativos.

| Plantilla | Finalidad / `tipo_evento` | Cuándo se encola | Revalidación antes de enviar |
|---|---|---|---|
| Invitación | `INVITACION` / `UsuarioInvitadoEvent` | Al invitar o reenviar (cuerpo cifrado; el enlace con token nunca queda en el historial). | Invitación vigente (no usada, no revocada, no vencida), cuenta pendiente de activar con la misma revisión, contexto y acceso activos, y correo igual al de la cuenta. |
| Cambio de acceso | `SEGURIDAD` / `AccesoUsuarioCambiadoEvent` | Al cambiar rol, vínculo o estado de la cuenta (relevos incluidos). | Existe el registro de auditoría de la operación, del mismo contexto, y apunta a este usuario; correo igual al de la cuenta. |
| Cuenta activada | `SEGURIDAD` / `CuentaActivadaEvent` | En la misma transacción que consume la invitación y activa la cuenta. `evento_id` se deriva (UUIDv5) de la invitación y `operacion_id` es la invitación, por lo que `uq_notificacion_logica` impide un segundo aviso si se reintenta. | La invitación está usada y no revocada, la cuenta sigue activa, el contexto y el rol siguen activos y el correo coincide. |

La plantilla «cuenta activada» incluye nombre, condominio, enlace a `/login` (derivado de `ACTIVACION_WEB_URL`; sin URL válida se omite) y «si no fuiste tú, contacta a la administración». Nunca lleva token ni contraseña.

## Verificación

Entorno: macOS, Python 3.14, PostgreSQL 16 desechable (puerto 55432), Mailpit v1.27.

| Comando / prueba | Resultado |
|---|---|
| `pytest src/tests/unit/test_transporte_smtp.py` y unitarias de notificaciones | 51 aprobadas |
| `pytest src/tests/integration/test_correo_proveedor_db.py test_alertas_notificaciones_db.py` (PostgreSQL) | 18 aprobadas, sin omisiones |
| Envío real `TransporteSMTP` → Mailpit con plantilla `NOTIF_RECORDATORIO_PREVIO` | Aceptado; Mailpit recibe `Message-ID nid-1-1@condomanager.local` |
| Servidor SMTP caído (puerto cerrado) | `FALLO_TEMPORAL` (503) |
| Suite backend completa `pytest -q` con `CON3/CON13_TEST_DATABASE_URL` | 725 aprobadas, 0 fallidas, 0 omitidas (13 min) |
| Tras integrar `develop` (CON-7/76) | 789 aprobadas, 0 fallidas (9 min) |
| Con CON-33 (`42a9fc5`) | 806 aprobadas, 0 fallidas; ciclo `0022` bajada/subida correcto |
| Con aviso de cuenta activada: identidad, recordatorios, correo, alertas y unitarias | 378 aprobadas |

## Pendiente para cerrar CON-78

1. ~~**Contrato de identidad con Jerson (CON-76).**~~ Resuelto al integrar `develop`: finalidades `OPERATIVA`/`INVITACION`/`SEGURIDAD` con revalidación propia. El worker atiende filas `SIMULADO` con `transport` y toda fila `PROVEEDOR` (de cualquier finalidad) con `proveedor`, construido una vez al arrancar desde la configuración SMTP.
2. **Proveedor del ambiente demo con Nicolás (CON-81):** elegir proveedor SMTP, credenciales en `.env` del ambiente, prueba con cuentas autorizadas y evidencia SQL de intentos.
3. ~~Plantillas de identidad~~ (invitación, cambio de acceso, cuenta activada): implementadas; ver «Plantillas de identidad».
4. ~~Recorrido en navegador~~ con Mailpit: hecho (ver «Recorrido de aceptación local»). Falta repetirlo con el proveedor real del demo.

## CON-33 — Recordatorios de vencimiento

Código: [`recordatorios.py`](../../src/modules/notificaciones/recordatorios.py), revalidación en
[`worker.py`](../../src/modules/notificaciones/worker.py) y migración
`20261118_0022_recordatorios_vencimiento` (estado `SUPRIMIDO`).

| Regla | Implementación |
|---|---|
| Configuración | `RECORDATORIOS_ACTIVOS` (true), `RECORDATORIO_DIAS_ANTICIPACION` (3), `RECORDATORIO_HORA_LIMA` (8). Solo canal EMAIL. |
| Programación | `ProgramadorDiario` corre dentro del worker de notificaciones: una pasada por fecha de Lima desde la hora configurada. |
| Selección SQL | Cuotas con `monto_pagado < monto_total_exigible`, departamento y condominio activos y `hoy ≤ fecha_vencimiento ≤ hoy + N` (America/Lima). Destinatarios: los mismos vínculos activos con email que el resto de avisos operativos (propietario e inquilino). |
| Fechas pasadas | Nunca se programan cuotas ya vencidas. La ventana recupera días perdidos por un worker caído solo para vencimientos futuros o de hoy. Si el despacho llega después del vencimiento, la fila queda `SUPRIMIDO_VENCIMIENTO_PASADO`. |
| Identidad estable | `evento_id` = cuota, `operacion_id` = uuid5(cuota, vencimiento); con `uq_notificacion_logica` el mensaje lógico es único por cuota, fecha, destinatario y canal. Dos workers, reintentos y reinicios no duplican. Un cambio de vencimiento genera un recordatorio nuevo y suprime el anterior (`SUPRIMIDO_VENCIMIENTO_MODIFICADO`). |
| Revalidación | Antes de cada intento, con la fila de la cola bloqueada, el worker lee la cuota con `FOR SHARE`. Sin saldo → `SUPRIMIDO_CUOTA_PAGADA`, sin intento ni transporte. Con saldo → re-renderiza el cuerpo con el saldo vigente (un abono parcial no deja un monto desactualizado). |
| Voucher en revisión | No modifica `monto_pagado`, así que el recordatorio se envía. El texto indica que puede ignorarse si el comprobante ya está en revisión. |
| Gracia | El correo informa el vencimiento y el último día sin mora: `fecha_vencimiento + dias_gracia_aplicados` (o la gracia del condominio). |
| Interfaz | Junta: «Suprimido (ya no aplica)»; residente: «No enviado: el aviso ya no aplica». Un suprimido no se reenvía. |

### Propuesta a Anderson: instante de elegibilidad

> La elegibilidad se decide **al despachar**, en la transacción que reserva el intento, leyendo la
> cuota con `FOR SHARE`. La aprobación de un pago (CON-25/27/28) bloquea condominio →
> departamento → cuotas `FOR UPDATE`, así que un pago en curso termina primero y su resultado
> decide. El instante de elegibilidad es el *commit* de esa transacción: un pago aprobado después
> (milisegundos a segundos, mientras el correo sale por SMTP) ya no puede detener ese envío. La
> cola no bloquea filas de pagos en orden inverso, así que no hay riesgo de deadlock.

Pendiente de confirmación con Anderson. Si se acepta, no requiere cambios en pagos.

### Verificación CON-33

| Prueba (`src/tests/integration/test_recordatorios_db.py`, PostgreSQL 16) | Resultado |
|---|---|
| Un recordatorio por destinatario; segunda pasada, día siguiente y reinicio sin duplicados | Aprobada |
| Dos programadores concurrentes (`asyncio.gather`) crean un solo mensaje lógico por destinatario | Aprobada |
| Ventana: vencida/19-oct no, hoy/21-oct/23-oct sí, 24-oct (fuera de N) no | 6 casos aprobados |
| Cuota pagada no se programa; pago aprobado antes del despacho → `SUPRIMIDO_CUOTA_PAGADA` sin intentos | Aprobadas |
| Voucher en revisión → se envía; abono parcial → el correo anuncia el saldo vigente | Aprobadas |
| Pago concurrente con la cuota bloqueada: el worker espera y suprime tras el commit | Aprobada |
| Despacho tardío tras el vencimiento; cambio de vencimiento suprime y reprograma | Aprobadas |
| Hora de Lima (07:59 no, 08:00 sí, 22:00 local = mismo día), un pase por día, apagado por configuración | Aprobada |
| Mutaciones: sin `FOR SHARE` o sin revalidar saldo, las pruebas de pago concurrente/aprobado fallan | Confirmado |

## Recorrido de aceptación local (18/11/2026)

Stack aislado: PostgreSQL 16 desechable (`condomanager_demo`, migrada a `0022` con
`seed_usuarios_demo` y `seed_areas_demo`), Redis y Mailpit v1.27 desechables, API (`uvicorn`),
worker de notificaciones y frontend (`next dev`) locales con `EMAIL_TRANSPORTE=SMTP` hacia Mailpit.
No se usó la base compartida.

1. **Recordatorio (CON-33).** Se insertó una cuota del Dpto. 102 (S/ 180.00, vence 21/11, gracia
   5 días). Se reinició el worker: el log indica «Proveedor de correo SMTP configurado» y
   «Recordatorios de vencimiento programados: 1 nuevos». Mailpit recibió el correo con el
   vencimiento 21/11/2026, el saldo S/ 180.00 y el último día sin mora 26/11/2026.
2. **Comunicado desde la Junta (CON-78).** Portal Junta → Comunicados → «Corte de agua programado»
   → confirmar. Los 3 destinatarios demo con email quedaron `ENVIADO` y Mailpit recibió los 3.
3. **Estado visible.** El historial de la Junta muestra «Aceptado, entrega sin confirmar» (`ENVIADO`)
   con ciclo e intentos.

4. **Identidad (CON-7/76 + CON-78).** Junta → Usuarios → «Invitar usuario» (Lucía Prueba,
   `lucia.prueba@ejemplo.test`). Mailpit recibió «Activa tu cuenta de CondoManager» con el enlace
   `/activar#token=…`; en `notificaciones_logs.cuerpo` solo queda «Enlace privado omitido del
   historial». Al abrir el enlace y elegir contraseña, llegó «Tu cuenta de CondoManager está activa»
   con el enlace a `/login`. Ambas filas: `INVITACION`/`SEGURIDAD`, `PROVEEDOR`, `ENVIADO`, 1 intento.

Evidencia SQL (`notificaciones_logs` ⨝ `notificaciones_intentos`):

| tipo_evento | estado | transporte | intento | proveedor_message_id |
|---|---|---|---|---|
| NOTIF_COMUNICADO_GENERAL | ENVIADO | PROVEEDOR | 1 | `<b4e28fb0-…-1-1@condomanager.local>` |
| NOTIF_COMUNICADO_GENERAL | ENVIADO | PROVEEDOR | 1 | `<a0a8eeb1-…-1-1@condomanager.local>` |
| NOTIF_COMUNICADO_GENERAL | ENVIADO | PROVEEDOR | 1 | `<c3da1110-…-1-1@condomanager.local>` |
| NOTIF_RECORDATORIO_PREVIO | ENVIADO | PROVEEDOR | 1 | `<16e372b3-…-1-1@condomanager.local>` |
| UsuarioInvitadoEvent | ENVIADO | PROVEEDOR | 1 | `<768e81f9-…-1-1@condomanager.local>` |
| CuentaActivadaEvent | ENVIADO | PROVEEDOR | 1 | `<f5aaea6e-…-1-1@condomanager.local>` |

Capturas: [Junta, historial de envíos](evidencia/con78-33/junta-comunicados-enviado.png) ·
[bandeja de Mailpit](evidencia/con78-33/mailpit-bandeja.png).

**Pendiente:** repetir el mismo recorrido con el proveedor SMTP real del ambiente demo
(CON-81, con Nicolás) sobre cuentas autorizadas, e incluir invitaciones y avisos de relevo (CON-76).
