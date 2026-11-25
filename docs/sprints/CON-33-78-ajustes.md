# CON-33 / CON-78 — Ajustes sobre la implementación de develop

Alcance: rescatar de la rama `feat/PROC-03-con78-correo-real` solo lo que `develop` no cubría.
No se trajo el transporte SMTP, la migración `20261118_0022_recordatorios_vencimiento` ni la
lógica de recordatorios duplicada, porque la implementación de Nicolás ya los resuelve.

## Qué cubre develop (Nicolás)

- **Correo real (CON-78):** adaptador Mailjet (`src/modules/notificaciones/mailjet.py`), eventos
  de proveedor, política de aceptación incierta y cola SQL con `transporte` PROVEEDOR/SIMULADO.
- **Recordatorios (CON-33):** `generar_recordatorios` con política y cursor diario por condominio
  (`politicas_notificaciones`), tipos `NOTIF_RECORDATORIO_PREVIO` / `NOTIF_CORTE_HOY`, columnas
  `recordatorio_vencimiento` y `recordatorio_dias`, deduplicación por la clave lógica y estado
  terminal `OMITIDO`.
- **Revalidación al despachar:** el worker ya omitía el recordatorio si la cuota no tenía saldo,
  su vencimiento cambió o la política se deshabilitó, y re-renderizaba el monto vigente. Esto
  **no se duplicó**.

## Qué se aportó

1. **Aviso de «cuenta activada» (CON-78).** `CuentaActivadaEvent` se encola en la misma
   transacción que consume la invitación (`aviso_activacion` en
   `src/modules/usuarios/comunicaciones.py`, integrado en `IdentidadService.activar`).
   - Identidad lógica derivada de la invitación: reintentar la activación no duplica el aviso.
   - Nunca incluye token ni contraseña; el enlace a `/login` se omite si `ACTIVACION_WEB_URL`
     no es válida.
   - Revalidación al despachar en `destinatario_identidad_valido`: invitación consumida y no
     revocada, cuenta activa, email sin cambios, condominio y rol vigentes; si no, queda
     `FALLIDO_PERMANENTE` con alerta, sin tocar el transporte.
   - Usa el transporte PROVEEDOR (Mailjet) y la cola/reintentos existentes; sin migración.
2. **Bloqueo de la cuota al despachar un recordatorio (CON-33).** Lo único que faltaba de la
   revalidación era la concurrencia: el worker leía la cuota sin bloqueo. Ahora la lee con
   `FOR SHARE`; un pago en curso hace esperar al worker, que relee el saldo y deja la fila
   `OMITIDO` / `RECORDATORIO_SIN_DEUDA` en lugar de enviar un aviso de deuda ya saldada.
   Sin migración (el estado terminal ya existe).

## Especificaciones y pruebas

- `specs/02-domains/05-usuarios-rbac/invitacion-y-relevo.md` y `features/invitacion_relevo.feature`.
- `specs/02-domains/03-notificaciones/delivery-policy.md` (§5) y `features/notificaciones.feature`.
- `src/tests/integration/test_identidad_sprint3_db.py`: aviso único e idempotente, envío sin
  secretos, URL inválida sin enlace, revalidación con cuenta desactivada.
- `src/tests/integration/test_recordatorio_revalidacion_db.py`: cuota pagada y vencimiento
  modificado (estado terminal sin intento ni alerta) y bloqueo por pago en curso (la prueba
  falla si se quita el `FOR SHARE`).
