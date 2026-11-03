# CON-78 / CON-33 — Correo transaccional real y recordatorios · Alejandro

Plan: [Sprint 3](SPRINT-3.md#con-78--correo-transaccional-real--alejandro). Política:
[entrega y reintentos §5](../../specs/02-domains/03-notificaciones/delivery-policy.md#5-transporte-smtp-real-con-78).

## Estado

| Ticket | Estado | Rama |
|---|---|---|
| [CON-78](https://tarquisoncco2.atlassian.net/browse/CON-78) | Primer incremento: adaptador SMTP, selección de transporte y aceptación incierta. Pendiente contrato de identidad (CON-76) y demo con proveedor real. | `feat/PROC-03-con78-correo-real` |
| [CON-33](https://tarquisoncco2.atlassian.net/browse/CON-33) | Sin iniciar. Requiere acordar con Anderson el instante de elegibilidad frente a un pago concurrente. | — |

## CON-78 — Qué entrega este incremento

- `transporte_smtp.py`: adaptador SMTP (STARTTLS, SSL o sin TLS) configurado por entorno, con timeout y resultados normalizados: aceptado, temporal, rebote definitivo, contenido rechazado y **aceptación incierta**. No guarda textos del servidor.
- El transporte se fija al encolar (`PROVEEDOR` solo para EMAIL con `EMAIL_TRANSPORTE=SMTP`). El worker atiende cada fila con su transporte; una fila `PROVEEDOR` nunca se acredita con el simulado y, sin configuración, mantiene `PROVEEDOR_NO_CONFIGURADO` con alerta.
- Aceptación incierta (sin respuesta tras transmitir el contenido): `FALLIDO_PERMANENTE` + alerta `ACEPTACION_INCIERTA`, sin reenvío automático. Cada intento lleva `Message-ID` estable `<log-ciclo-intento@dominio>` para reconciliar con el proveedor.
- SMTP acredita `ENVIADO` (aceptación); `ENTREGADO` queda reservado a evidencia posterior del proveedor.
- Docker Compose: servicio Mailpit para desarrollo (`http://localhost:8025`), variables SMTP en API y worker; `.env.example` documentado.

## Verificación

Entorno: macOS, Python 3.14, PostgreSQL 16 desechable (puerto 55432), Mailpit v1.27.

| Comando / prueba | Resultado |
|---|---|
| `pytest src/tests/unit/test_transporte_smtp.py` y unitarias de notificaciones | 51 aprobadas |
| `pytest src/tests/integration/test_correo_proveedor_db.py test_alertas_notificaciones_db.py` (PostgreSQL) | 18 aprobadas, sin omisiones |
| Envío real `TransporteSMTP` → Mailpit con plantilla `NOTIF_RECORDATORIO_PREVIO` | Aceptado; Mailpit recibe `Message-ID nid-1-1@condomanager.local` |
| Servidor SMTP caído (puerto cerrado) | `FALLO_TEMPORAL` (503) |
| Suite backend completa `pytest -q` con `CON3/CON13_TEST_DATABASE_URL` | 725 aprobadas, 0 fallidas, 0 omitidas (13 min) |

## Pendiente para cerrar CON-78

1. **Contrato de identidad con Jerson (CON-76):** invitaciones y avisos de cambio de acceso no tienen `departamento_id` ni vínculo activo; la cola actual lo exige (`notificaciones_logs.departamento_id NOT NULL` y revalidación de destinatario en el worker). Proponer una clase de mensaje de identidad con su propia revalidación (cuenta + contexto) sin relajar la de mensajes operativos.
2. **Proveedor del ambiente demo con Nicolás (CON-81):** elegir proveedor SMTP, credenciales en `.env` del ambiente, prueba con cuentas autorizadas y evidencia SQL de intentos.
3. Plantillas nuevas de identidad (invitación, activación, cambio de acceso) cuando exista el contrato.
4. Recorrido en navegador: despacho/comunicado desde la Junta → correo en Mailpit/proveedor → estado `ENVIADO` visible.
