# PROC-03 — aceptación del transporte productivo

```gherkin
Escenario: Envío y confirmación
  Dado un aviso EMAIL PROVEEDOR con destinatario vigente
  Cuando Supabase Cron invoca el job autenticado y Mailjet acepta el envío
  Entonces se conserva MessageID y estado ENVIADO
  Cuando llega un evento sent autenticado del mismo intento
  Entonces queda ENTREGADO sin acreditar lectura humana

Escenario: Protección contra duplicados y errores ambiguos
  Dado un intento durable y una respuesta incierta
  Cuando se recupera la cola
  Entonces se alerta para revisión sin repetir el envío
  Y los callbacks repetidos o de ciclos anteriores no revierten estados

Escenario: Activación segura
  Dado un historial SIMULADO y Mailjet deshabilitado
  Cuando se habilita Mailjet
  Entonces solo nuevas comunicaciones EMAIL se encolan para PROVEEDOR
  Y el job no envía registros SIMULADO

Escenario: Recordatorio
  Dada una cuota con saldo y destinatario vigente
  Cuando son las 08:00 de Lima tres días antes o el día del vencimiento
  Entonces se encola una sola notificación por cuota, tipo y destinatario
  Y si se paga antes del despacho no se envía el recordatorio
```
