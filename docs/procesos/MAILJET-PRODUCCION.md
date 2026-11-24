# Activación Mailjet y Supabase Cron

## Cierre EMAIL — esquema 0022

La rama `feat/PROC-03-notificaciones-completas` requiere **migración 0022 antes
del despliegue**. No cambiar la programación ni las credenciales ya verificadas.
Mantener MAILJET_ENABLED=false durante el cambio.

1. Respaldar la base objetivo y comprobar su revisión actual.
2. Desde un runner con las variables privadas de esa base, aplicar
   `alembic upgrade head` (no durante build ni desde cada Function).
3. Desplegar el nuevo código y comprobar `/api/v1/ready`: revisión 20261121_0022.
4. En Comunicados: elegir audiencia, previsualizar destinatarios y confirmar.
   La cantidad es por usuario, no por unidad; los contactos suprimidos se excluyen.
   Repetir la confirmación del mismo borrador no duplica el lote. Si la respuesta
   se pierde, recuperar ese borrador en Operación; no crear otra campaña.
5. Revisar el padrón y toda la cola pendiente antes de habilitar el proveedor.
   Los datos demo con buzones ficticios no son aptos para envíos productivos.
6. Activar Mailjet únicamente al aceptar el cambio con contactos reales autorizados.

La interfaz permite configurar días y hora de recordatorios, consultar lotes,
suprimir automáticamente correos con eventos negativos y reactivar contactos
con motivo auditado. La política deshabilitada omite también recordatorios en cola.
El cursor recupera días posteriores a su primera activación; procesa hasta 31 por
pasada sin saltar el resto. Al enviar, actualiza importes y omite pagados o cuotas
cuyo vencimiento cambió. Los avisos vencidos recuperados no afirman «vence hoy».

Las aceptaciones inciertas se resuelven con revisión humana de Mailjet,
referencia/motivo y ciclo esperado. ACEPTADO exige MessageID y no acredita entrega.
NO_ACEPTADO exige confirmación explícita de que no se aceptó el intento anterior:
autorizarlo erróneamente puede duplicar un correo. DESCARTAR no genera otro envío.
No se utiliza CustomID como prueba automática de ausencia ni de idempotencia externa.

Supervisión: última ejecución completa del programador (revisión tras 5 min sin
éxito), antigüedad de cola (advertencia tras 15 min), alertas e inciertos por contexto.
Las advertencias están disponibles en la aplicación; no se inventa un servicio
externo de monitorización ni se envían alertas a una dirección no configurada.
WhatsApp, SMS y PUSH no se habilitan mediante esta entrega.

Rollback: conservar MAILJET_ENABLED=false y preferir corrección hacia adelante.
La migración no permite downgrade si ya hay políticas, lotes, supresiones, eventos
o avisos OMITIDO: no se borra historial para volver a una versión anterior.
Un backend antiguo tampoco reconoce OMITIDO; no basta con revertir el código.

### Preparación inicial (sin tablas adicionales en aquella entrega)

## Preparación

No ejecutar migraciones ni habilitar envíos durante build. La integración inicial no añadía
tablas. No convertir el historial SIMULADO a PROVEEDOR: hacerlo enviaría correos
históricos. Revisar también el outbox pendiente antes de activar: los hechos aún
no consumidos generan avisos al recuperarse.

Variables privadas del servicio `app`, Production:

```dotenv
MAILJET_ENABLED=false
MAILJET_FROM_EMAIL=nicolas.tarqui@unmsm.edu.pe
```

Conservar `MAILJET_API_KEY` y `MAILJET_SECRET`. Añadir
`MAILJET_WEBHOOK_SECRET`: secreto aleatorio independiente de al menos 32 caracteres.
El `.env.deploy` privado ya contiene el remitente y un secreto generado para callback;
reimportar esas variables en el servicio app sin compartir el archivo.
Conservar `CRON_SECRET` y `IDENTITY_DELIVERY_KEY`. Nunca publicar secretos como
NEXT_PUBLIC, en commits, capturas, comandos compartidos o logs.

## Callback de Mailjet

En Mailjet → Event Tracking, configurar los eventos **sent, bounce, blocked, spam**
con el endpoint HTTPS:

`https://mailjet:CONTRASEÑA_CALLBACK@DOMINIO/api/v1/notificaciones/mailjet/eventos`

La contraseña es MAILJET_WEBHOOK_SECRET; usar un secreto URL-safe. Mailjet
recomienda HTTPS + Basic Auth; no se presupone una firma HMAC inexistente.
Verificar que Authorization llegue al servicio y que la protección de deployment
no bloquee al proveedor. Sin credencial el endpoint debe devolver 401.
El callback confirma aceptación del servidor destinatario, no lectura humana.
Comprobar verificación del remitente y SPF/DKIM/DMARC: verificar una dirección
universitaria no concede control del DNS de su dominio ni garantiza entregabilidad.
Mailjet reintenta callbacks que no reciban 200; una caída SQL no debe responder éxito.

## Supabase Cron

Habilitar **Cron (pg_cron)**, **pg_net** y **Vault** en el proyecto Supabase.
En Vault crear manualmente:

- `condomanager_url`: URL HTTPS del portal, sin barra final.
- `condomanager_cron_secret`: mismo CRON_SECRET del backend.

Solo un administrador debe acceder al editor SQL, al job y a estos secretos.
Luego registrar el job (no incluir credenciales literales en SQL):

```sql
select cron.schedule(
  'condomanager-notificaciones',
  '* * * * *',
  $job$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets
            where name = 'condomanager_url')
            || '/api/v1/jobs/notificaciones',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        select decrypted_secret from vault.decrypted_secrets
        where name = 'condomanager_cron_secret'
      )
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 55000
  );
  $job$
);
```

Comprobar `cron.job_run_details` y `net._http_response`: que pg_net acepte una
solicitud no acredita un 200 de la API. Configurar supervisión de errores 401/403/503
y de acumulación de EN_COLA. Un 409 indica ejecución ya en curso.
El job no necesita acceso público a otras rutas de API.

## Activación y aceptación

1. Desplegar la rama con MAILJET_ENABLED=false y callback secreto configurado.
2. Verificar health/readiness y pruebas negativas de autenticación.
3. Configurar los callbacks y el Cron. El job responde DESHABILITADO sin enviar.
4. Revisar cola/outbox y verificar que los contactos reales sean correctos.
5. Poner MAILJET_ENABLED=true, hacer redeploy y crear un comunicado pequeño
   dirigido únicamente a los contactos de prueba autorizados.
6. Comprobar MessageID, ENVIADO, callback ENTREGADO y recepción en ambas bandejas.
7. Probar rechazo/429 con transportes sustituidos; no provocar rebotes reales
   intencionalmente contra correos de residentes.

Desactivar MAILJET_ENABLED y redeploy suspende los nuevos intentos, no cancela
una petición que ya salió. Supabase Cron puede pausarse además desde el panel.
Timeout/5xx quedan como aceptación incierta; no repetir sin revisar Mailjet.
No hay reenvío automático del mismo mensaje incierto ni garantía exactly-once externa.

## Capacidad y límites

Máximo 20 intentos y 45 s por llamada; locks SQL evitan dos jobs simultáneos.
Con cron cada minuto los umbrales 2/10/30 min pueden retrasarse hasta el siguiente
tick o por backlog. Validar capacidad y cuotas reales de Mailjet, Supabase y Vercel.
Los recordatorios se generan desde las 08:00 de Lima el día correspondiente;
los pagados se descartan al despachar. No se recuperan avisos de días anteriores.
WhatsApp/RPA no forma parte de esta integración de correo.
