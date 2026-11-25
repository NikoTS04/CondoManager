# Resiliencia, Tolerancia a Fallos y Excepciones (Resilience & Exceptions)

## 1. Principio Fundamental: Automatización con Supervisión Humana

La automatización en CondoManager tiene como fin liberar al administrador de tareas rutinarias y repetitivas, **sin eliminar la supervisión humana**.

El sistema clasifica las operaciones en dos vías:
- **Vía Rápida (Fast Path - 100% Automática):** Casos normales y consistentes (ej. pago exacto reportado con código único, reserva en horario disponible con cuota al día, alerta preventiva enviada correctamente).
- **Vía de Excepción (Human-in-the-Loop):** Situaciones atípicas, pagos parciales, reportes con montos discordantes o fallas de comunicación externa que se derivan a la **Bandeja de Excepciones del Administrador**.

---

## 2. Mecanismos de Control y Resiliencia

### 2.1 Control de Idempotencia (Prevención de Duplicados)
Para evitar que un residente cargue accidentalmente dos veces el mismo comprobante, o que una tarea programada aplique doble mora ante un reinicio del servidor:
- Toda solicitud de registro de pago genera una clave única:
  $$\text{IdempotencyKey} = \text{SHA256}(\text{condominio\_id} + \text{banco} + \text{codigo\_operacion} + \text{fecha\_voucher} + \text{monto})$$
- Si la clave ya existe en la base de datos:
  - Si el pago anterior está en estado `APROBADO` o `EN_REVISION`, se rechaza la nueva solicitud informando al usuario que la operación ya fue registrada.
  - Se previene la duplicación de saldos y asientos contables.

### 2.2 Política de Reintentos Exponenciales (Exponential Backoff)
Para servicios externos propensos a fallos temporales (envío de correos SMTP, mensajería WhatsApp, webhooks bancarios):
- **Intento 1:** Inmediato al fallar la primera llamada.
- **Intento 2:** Espera de 2 minutos.
- **Intento 3:** Espera de 10 minutos.
- **Intento 4 (Final):** Espera de 30 minutos.
- **Agotamiento de Reintentos:** Si tras el 4to intento el servicio sigue caído:
  1. La tarea se marca como `ESTADO_FALLIDO_PERMANENTE`.
  2. Se despacha una alerta urgente a la campana de notificaciones de la junta directiva.
  3. Se registra el log de auditoría con la respuesta de error del proveedor externo.

### 2.3 Bloqueos Pesimistas para Prevención de Condiciones de Carrera (Race Conditions)
En la reserva de áreas comunes (ej. dos residentes intentando reservar la zona de parrillas simultáneamente para el mismo sábado a las 20:00):
- Se utiliza bloqueo pesimista en base de datos (`SELECT ... FOR UPDATE` sobre el intervalo de tiempo del recurso).
- La primera transacción que confirme adquiere el bloqueo; la segunda recibe inmediatamente un aviso amigable indicando que el espacio acaba de ser ocupado.

---

## 3. Catálogo de Excepciones y Protocolo de Intervención Humana

| Escenario de Excepción | Comportamiento Automático | Acción Requerida del Administrador |
| :--- | :--- | :--- |
| **Pago Parcial:** Residente paga S/ 100 de una cuota de S/ 150. | El sistema abona los S/ 100 a la deuda más antigua, mantiene el saldo pendiente de S/ 50 y marca la cuota como `PAGO_PARCIAL`. | El administrador revisa si existe acuerdo previo de fraccionamiento o si debe notificar la diferencia al residente. |
| **Pago con Exceso:** Residente transfiere S/ 200 para una cuota de S/ 150. | El sistema liquida la cuota de S/ 150 y asigna automáticamente S/ 50 a `Saldo a Favor` del departamento. | El administrador valida en el siguiente mes que el saldo a favor se descuente de la nueva cuota emitida. |
| **Voucher Ilegible o Monto Discordante:** La imagen no coincide con el monto declarado. | El sistema coloca el comprobante en estado `OBSERVADO`. No modifica los saldos del departamento. | El administrador hace clic en `Rechazar Comprobante`, ingresando el motivo (ej. "Voucher borroso"), lo que dispara un email solicitando el comprobante legible. |
| **Reclamo por Mora Indebida:** El residente pagó antes del corte, pero reportó el voucher tarde. | El sistema aplicó la mora en la fecha de corte por no haber registro previo. | El administrador cuenta con la función `Exonerar Mora / Revertir Penalidad`, la cual anula la mora mediante un asiento compensatorio auditado. |
| **Falla en Notificaciones Masivas:** La cuota mensual no pudo ser enviada a 10 departamentos por caída de correo. | El sistema identifica los 10 envíos fallidos y los aisla en la cola de contingencia. | El administrador visualiza el botón `Reintentar Envíos Pendientes` en el módulo de comunicaciones. |

## 4. Bandeja de Junta para fallos de correo (CON-66)

El primer recorrido usa alertas de correo operativo persistidas. Junta consulta
el origen, el motivo, la prioridad, el estado, la referencia de la notificación
y su ciclo. El detalle incluye la evidencia y las decisiones registradas en
auditoría. El acceso se limita al condominio activo de `ADMIN_JUNTA`.

Un fallo definitivo admite **Cerrar con motivo**, que marca el aviso omitido,
o **Reenviar a un contacto autorizado** cuando la causa admite corregir el
contacto. Durante el nuevo envío el caso figura `EN_PROCESO`; se muestra
`RESUELTA` cuando el proveedor acepta el envío y `FALLIDA` cuando se agota o
se omite el nuevo intento. La evidencia distingue `ENVIADO` de `ENTREGADO`.
La aceptación incierta se consulta en el flujo de revisión de correo existente.

La decisión, el efecto sobre el aviso, el actor y el motivo se guardan juntos.
Una repetición con la misma clave recupera la decisión original sin iniciar
otro ciclo.

## 5. Persistencia y ejecución de resoluciones (CON-86)

CON-86 convierte cada alerta en un caso persistido con evidencia autorizada,
historial de decisiones y ejecución de acciones sobre el proceso de origen.
Además de los fallos de correo, la bandeja incluye los
`JOB_FALLO_DEFINITIVO` (`origen_tipo = JOB`), que no tienen condominio:
`SUPERADMIN` los consulta y resuelve de forma global. Para conservar la
bitácora inmutable con los siete campos, esas decisiones se registran con el
condominio centinela `3709ed64-791a-5cd8-99c7-142ab3ee590c`, creado por la
migración `20261130_0030` y sin usuarios ni roles asociados.

Las acciones permitidas son `CERRAR_CON_MOTIVO` para cualquier causa y
`REENVIAR_CORREO` o `REINTENTAR_JOB` solo cuando el origen admite repetir con
seguridad. `REINTENTAR_JOB` está restringido a procesos idempotentes registrados
en `JOBES_REINTENTABLES`; el job `diario` queda fuera hasta CON-85. La ejecución
revalida el estado del proceso de origen bajo bloqueo pesimista, guarda el
resultado **real** de la acción y lo muestra en la bandeja. Una decisión se
guarda en `excepciones_resoluciones` con clave de idempotencia y huella única
por caso; repetir la clave devuelve la decisión original y no ejecuta dos veces
la acción. La evidencia conserva componente, operación, ciclo, referencia de
correlación y error saneado del proveedor, sin correos ni secretos.
