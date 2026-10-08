# Guía textual para diagramar los procesos de CondoManager en Bizagi

Este documento describe los ocho procesos principales de CondoManager y el proceso transversal de gestión de excepciones y reintentos. Está pensado como guía para dibujarlos manualmente utilizando notación BPMN en Bizagi Modeler.

## Convenciones utilizadas

- `(Inicio)` y `(Fin)`: eventos BPMN.
- `[Tarea]`: actividad realizada por una persona o por el sistema.
- `<¿Condición?>`: compuerta exclusiva; se debe dibujar como un rombo.
- `((Temporizador))`: evento de tiempo.
- `((Mensaje))`: evento de mensaje o comunicación entre participantes.
- `→`: flujo de secuencia.
- Cuando una tarea dice **automática**, puede representarse como una tarea de servicio.
- Cuando una tarea dice **manual**, puede representarse como una tarea de usuario.
- Las notificaciones por correo se pueden conectar mediante un evento de mensaje con el proceso PROC-03.

---

## PROC-01 — Gestión de cuotas de mantenimiento

**Objetivo:** generar las cuotas ordinarias o extraordinarias de los departamentos y dejarlas listas para su pago.

**Carriles sugeridos:** Administrador/Junta Directiva, Sistema CondoManager y Residente.

### Flujo principal

```text
((Temporizador: día 1 del mes))
        ↓
[Sistema consulta el presupuesto aprobado]
        ↓
<¿Existe un presupuesto aprobado?>
   ├─ No → [Registrar excepción y avisar al administrador] → (Fin sin emisión)
   └─ Sí
        ↓
[Obtener departamentos activos, alícuotas y saldos a favor]
        ↓
[Calcular la cuota de cada departamento]
        ↓
[Redondear importes y verificar que el total coincida con el presupuesto]
        ↓
<¿Los cálculos son correctos?>
   ├─ No → [Registrar descuadre y enviar a revisión] → (Fin con excepción)
   └─ Sí
        ↓
[Generar las cuotas del periodo]
        ↓
<¿El departamento tiene saldo a favor?>
   ├─ Sí → [Aplicar saldo a favor]
   │          ↓
   │       <¿Cubre toda la cuota?>
   │          ├─ Sí → [Marcar cuota como PAGADA]
   │          └─ No → [Marcar saldo restante como PENDIENTE]
   └─ No → [Marcar cuota como PENDIENTE]
        ↓
[Registrar emisión en auditoría]
        ↓
((Mensaje a PROC-03: enviar aviso de nueva cuota))
        ↓
[Residente recibe la cuota y fecha de vencimiento]
        ↓
(Fin: cuotas emitidas)
```

### Inicio alternativo para una cuota extraordinaria

```text
(Inicio: administrador registra cuota extraordinaria)
        ↓
[Ingresar acta, concepto, monto y número de pagos]
        ↓
<¿La información es válida?>
   ├─ No → [Solicitar corrección] → (Fin)
   └─ Sí → [Generar cuotas extraordinarias] → [Continuar desde el registro de auditoría]
```

---

## PROC-02 — Gestión de pagos, conciliación y morosidad

**Objetivo:** recibir comprobantes, conciliarlos contra los movimientos bancarios, distribuir el pago entre las deudas y aplicar moras cuando corresponda.

**Carriles sugeridos:** Residente, Sistema CondoManager, Tesorero/Junta Directiva y PROC-03 Notificaciones.

### Flujo A: reporte y conciliación de un pago

```text
(Inicio: residente desea reportar un pago)
        ↓
[Residente completa datos y adjunta el voucher]
        ↓
[Sistema valida formato, monto, fecha y código de operación]
        ↓
[Sistema calcula la clave de idempotencia]
        ↓
<¿El comprobante ya fue registrado?>
   ├─ Sí → [Rechazar el registro como duplicado]
   │          ↓
   │       ((Mensaje: informar comprobante duplicado))
   │          ↓
   │       (Fin: pago no registrado)
   └─ No
        ↓
[Guardar comprobante con estado EN_REVISION]
        ↓
[Congelar temporalmente la aplicación de mora]
        ↓
((Mensaje: confirmar recepción al residente))
        ↓
[Mostrar comprobante en la bandeja de conciliación]
        ↓
[Tesorero compara el voucher con el movimiento bancario]
        ↓
<¿Cuál es la decisión?>
   ├─ Rechazar → [Registrar motivo obligatorio]
   │                ↓
   │             [Cambiar estado a RECHAZADO]
   │                ↓
   │             ((Mensaje: enviar correo con motivo de rechazo))
   │                ↓
   │             (Fin: comprobante rechazado)
   ├─ Observar → [Solicitar información o voucher legible]
   │                ↓
   │             [Mantener el pago sin afectar saldos]
   │                ↓
   │             (Fin temporal: pendiente de subsanación)
   └─ Aprobar
        ↓
[Cambiar comprobante a APROBADO]
        ↓
[Imputar el dinero: moras → cuotas extraordinarias → cuotas antiguas → cuota actual]
        ↓
<¿Queda dinero excedente?>
   ├─ Sí → [Registrar excedente como saldo a favor]
   └─ No → [Continuar]
        ↓
<¿El departamento todavía tiene deuda vencida?>
   ├─ Sí → [Mantener estado EN_MORA y bloqueo de reservas]
   └─ No → [Cambiar estado a AL_DIA y habilitar reservas]
        ↓
[Registrar conciliación e imputaciones en auditoría]
        ↓
((Mensaje a PROC-03: enviar confirmación y estado de cuenta))
        ↓
(Fin: pago conciliado)
```

### Flujo B: evaluación automática de moras

```text
((Temporizador: evaluación diaria de vencimientos))
        ↓
[Buscar cuotas vencidas o parcialmente pagadas]
        ↓
<¿Terminó el periodo de gracia?>
   ├─ No → (Fin: esperar siguiente evaluación)
   └─ Sí
        ↓
<¿Existe un comprobante EN_REVISION?>
   ├─ Sí → [Posponer la mora por 24 horas]
   │          ↓
   │       ((Mensaje: alertar a la junta para revisar el pago))
   │          ↓
   │       (Fin temporal)
   └─ No
        ↓
[Calcular y aplicar la penalidad configurada]
        ↓
[Cambiar cuota y departamento a EN_MORA]
        ↓
[Bloquear nuevas reservas]
        ↓
[Registrar aplicación de mora en auditoría]
        ↓
((Mensaje a PROC-03: enviar aviso de mora y restricción))
        ↓
(Fin: mora aplicada)
```

---

## PROC-03 — Gestión de notificaciones y comunicaciones

**Objetivo:** generar y enviar correos o mensajes originados por los demás procesos, verificar su entrega y reintentar los envíos que fallen.

**Carriles sugeridos:** Proceso solicitante, Sistema de Notificaciones, Proveedor de correo/WhatsApp, Residente y Administrador.

### Flujo principal

```text
((Mensaje recibido: nueva cuota, pago, mora, reserva, usuario, contrato o ticket))
        ↓
[Identificar el tipo de notificación]
        ↓
[Consultar destinatarios y canales configurados]
        ↓
<¿Los datos de contacto son válidos?>
   ├─ No → [Registrar contacto inválido]
   │          ↓
   │       [Alertar al administrador]
   │          ↓
   │       (Fin con excepción)
   └─ Sí
        ↓
[Seleccionar y completar la plantilla]
        ↓
[Registrar notificación como EN_COLA]
        ↓
[Enviar correo o mensaje mediante el proveedor]
        ↓
<¿El proveedor confirmó la entrega?>
   ├─ Sí → [Cambiar estado a ENTREGADO]
   │          ↓
   │       [Registrar resultado en la bitácora]
   │          ↓
   │       (Fin: notificación entregada)
   └─ No
        ↓
<¿El error es temporal?>
   ├─ Sí → [Invocar subproceso de reintentos]
   └─ No → [Marcar como FALLIDO_PERMANENTE]
               ↓
            [Alertar al administrador]
               ↓
            (Fin con fallo)
```

### Correos que se originan en este proceso

- Aviso de nueva cuota y recordatorio de vencimiento.
- Confirmación de recepción del voucher.
- Resultado de conciliación: aprobado, observado o rechazado.
- Aviso de mora y bloqueo de reservas.
- Aviso de levantamiento de la restricción.
- Confirmación o cancelación de reserva.
- Invitación y activación de una cuenta de usuario.
- Alertas de contratos y cambios de estado de tickets.

---

## PROC-04 — Gestión de reservas de áreas comunes

**Objetivo:** comprobar la solvencia del departamento y la disponibilidad del área antes de confirmar una reserva.

**Carriles sugeridos:** Residente, Sistema CondoManager, Junta Directiva y PROC-03 Notificaciones.

### Flujo principal

```text
(Inicio: residente consulta o solicita una reserva)
        ↓
[Consultar catálogo y horarios disponibles]
        ↓
[Residente selecciona área, fecha y horario]
        ↓
[Sistema valida que el usuario pertenezca al departamento]
        ↓
<¿El departamento tiene deuda en mora?>
   ├─ Sí → [Rechazar solicitud por MORA_ACTIVA]
   │          ↓
   │       [Registrar rechazo en auditoría]
   │          ↓
   │       (Fin: reserva denegada)
   └─ No
        ↓
[Validar anticipación, duración y límite de reservas]
        ↓
<¿Cumple las reglas del área?>
   ├─ No → [Rechazar e indicar la regla incumplida] → (Fin)
   └─ Sí
        ↓
[Bloquear transaccionalmente el área y horario]
        ↓
<¿El horario continúa disponible?>
   ├─ No → [Rechazar por HORARIO_NO_DISPONIBLE] → (Fin)
   └─ Sí
        ↓
[Crear reserva en estado CONFIRMADA]
        ↓
<¿El área tiene costo?>
   ├─ Sí → [Generar cargo de reserva o limpieza]
   └─ No → [Continuar]
        ↓
[Registrar reserva en auditoría]
        ↓
((Mensaje a PROC-03: enviar confirmación y normas de uso))
        ↓
(Fin: reserva confirmada)
```

### Flujo de cancelación

```text
(Inicio: residente o administrador solicita cancelación)
        ↓
<¿La cancelación cumple el plazo permitido o fue autorizada por la junta?>
   ├─ No → [Rechazar cancelación] → (Fin)
   └─ Sí → [Cambiar reserva a CANCELADA]
              ↓
           [Liberar el horario]
              ↓
           <¿Existía un cobro?>
              ├─ Sí → [Emitir ajuste o nota de crédito]
              └─ No → [Continuar]
              ↓
           ((Mensaje: enviar aviso de cancelación))
              ↓
           (Fin: reserva cancelada)
```

---

## PROC-05 — Gestión de usuarios, roles y departamentos

**Objetivo:** registrar personas, asignarles un rol y vincularlas con uno o más departamentos.

**Carriles sugeridos:** Administrador/Junta Directiva, Sistema CondoManager, PROC-03 Notificaciones y Usuario.

### Flujo principal

```text
(Inicio: administrador registra o importa un usuario)
        ↓
[Ingresar DNI/CE, nombre, correo y teléfono]
        ↓
[Sistema valida formato y unicidad del correo/documento]
        ↓
<¿El usuario ya existe?>
   ├─ Sí → [Recuperar cuenta existente]
   └─ No → [Crear cuenta inactiva]
        ↓
[Seleccionar rol: administrador, auditor, propietario o inquilino]
        ↓
[Vincular usuario con condominio y departamento]
        ↓
<¿La asignación es válida?>
   ├─ No → [Mostrar error y solicitar corrección] → (Fin sin alta)
   └─ Sí
        ↓
[Generar token de activación]
        ↓
((Mensaje a PROC-03: enviar correo de invitación))
        ↓
[Usuario abre el enlace y establece contraseña]
        ↓
<¿El token es válido y no ha vencido?>
   ├─ No → [Solicitar nueva invitación] → (Fin temporal)
   └─ Sí → [Activar cuenta y permisos]
              ↓
           [Registrar alta o vinculación en auditoría]
              ↓
           (Fin: usuario habilitado)
```

### Flujo de cambio de inquilino o directiva

```text
(Inicio: administrador registra cambio)
        ↓
[Desactivar vínculo o rol anterior]
        ↓
[Conservar el historial asociado al departamento]
        ↓
[Crear nuevo vínculo o rol]
        ↓
[Notificar a las personas involucradas]
        ↓
(Fin: permisos actualizados)
```

---

## PROC-06 — Gestión de egresos, proveedores y contratos

**Objetivo:** registrar gastos sustentados, administrar proveedores y controlar el vencimiento de sus contratos.

**Carriles sugeridos:** Tesorería/Junta Directiva, Sistema CondoManager, Proveedor y PROC-03 Notificaciones.

### Flujo A: registro de egreso

```text
(Inicio: tesorería recibe factura u orden de pago)
        ↓
[Seleccionar o registrar proveedor]
        ↓
[Ingresar categoría, descripción, monto y fecha]
        ↓
[Adjuntar factura, recibo o constancia]
        ↓
<¿La información y el sustento están completos?>
   ├─ No → [Solicitar corrección o documento faltante] → (Fin temporal)
   └─ Sí
        ↓
<¿El pago requiere aprobación?>
   ├─ Sí → [Junta revisa y aprueba o rechaza]
   │          ↓
   │       <¿Fue aprobado?>
   │          ├─ No → [Registrar rechazo] → (Fin)
   │          └─ Sí → [Continuar]
   └─ No → [Continuar]
        ↓
[Registrar pago al proveedor]
        ↓
[Clasificar el egreso en el presupuesto]
        ↓
[Registrar movimiento y comprobante en auditoría]
        ↓
(Fin: egreso registrado)
```

### Flujo B: alerta de vencimiento de contratos

```text
((Temporizador: revisión diaria de contratos))
        ↓
[Consultar fechas de vencimiento]
        ↓
<¿El contrato vence en 60 días?>
   ├─ Sí → [Generar alerta preventiva de cotización o renovación]
   └─ No → [Continuar]
        ↓
<¿El contrato vence en 30 días?>
   ├─ Sí → [Generar alerta prioritaria]
   └─ No → [No generar alerta]
        ↓
((Mensaje a PROC-03: notificar a la junta))
        ↓
(Fin: contratos evaluados)
```

---

## PROC-07 — Gestión de tickets de incidencias

**Objetivo:** registrar problemas de infraestructura, asignarlos a un responsable y controlar su atención hasta el cierre.

**Carriles sugeridos:** Residente, Sistema CondoManager, Administración, Proveedor/Mantenimiento y PROC-03 Notificaciones.

### Flujo principal

```text
(Inicio: residente detecta una incidencia)
        ↓
[Registrar ubicación, descripción, categoría y urgencia]
        ↓
[Adjuntar fotografías o evidencia]
        ↓
[Sistema crea ticket en estado REGISTRADO]
        ↓
((Mensaje: avisar a la administración))
        ↓
[Administrador revisa y clasifica el ticket]
        ↓
<¿La incidencia es válida?>
   ├─ No → [Rechazar o solicitar más información] → (Fin)
   └─ Sí
        ↓
[Asignar personal o proveedor responsable]
        ↓
[Cambiar estado a ASIGNADO]
        ↓
[Proveedor inicia atención]
        ↓
[Cambiar estado a EN_PROCESO]
        ↓
[Registrar acciones, repuestos y costos]
        ↓
<¿La incidencia fue solucionada?>
   ├─ No → [Actualizar diagnóstico y continuar atención] ─┐
   │                                                     │
   └─ Sí → [Cambiar estado a RESUELTO]                   │
              ↓                                          │
           ((Mensaje: solicitar conformidad al residente))
              ↓
           <¿El residente está conforme?>
              ├─ No → [Reabrir o devolver a EN_PROCESO] ─┘
              └─ Sí → [Registrar calificación y cerrar ticket]
                         ↓
                      [Cambiar estado a CERRADO]
                         ↓
                      [Registrar cierre en auditoría]
                         ↓
                      (Fin: incidencia cerrada)
```

---

## PROC-08 — Gestión de reportes, KPIs y balances

**Objetivo:** consolidar la información financiera y generar indicadores y balances para la junta y los propietarios.

**Carriles sugeridos:** Sistema CondoManager, Junta Directiva/Tesorería y Propietario.

### Flujo A: consulta de indicadores

```text
(Inicio: usuario autorizado abre el dashboard)
        ↓
[Sistema obtiene cuotas, pagos conciliados, moras y egresos]
        ↓
[Calcular tasa de morosidad]
        ↓
[Calcular porcentaje de recaudación]
        ↓
[Calcular flujo de caja y fondo de reserva]
        ↓
<¿Los datos contables están completos?>
   ├─ No → [Mostrar advertencia y registrar inconsistencia]
   └─ Sí → [Mostrar indicadores consolidados]
        ↓
(Fin: dashboard actualizado)
```

### Flujo B: balance mensual

```text
((Temporizador: cierre del último día del mes))
        ↓
[Consolidar ingresos, egresos y cuentas por cobrar]
        ↓
[Conciliar información con movimientos bancarios]
        ↓
<¿Existen diferencias pendientes?>
   ├─ Sí → [Enviar balance a revisión de tesorería]
   │          ↓
   │       [Tesorería corrige o justifica diferencias]
   └─ No → [Continuar]
        ↓
[Generar snapshot contable inmutable]
        ↓
[Generar Balance_Mensual_Periodo.pdf]
        ↓
[Publicar balance para usuarios autorizados]
        ↓
((Mensaje: avisar a junta y propietarios))
        ↓
(Fin: balance mensual publicado)
```

---

## Proceso transversal — Gestión de excepciones y reintentos

**Objetivo:** recibir los casos que no pueden resolverse por el flujo normal, ejecutar reintentos cuando corresponda y derivar los casos que requieren decisión humana.

**Carriles sugeridos:** Proceso de origen, Sistema CondoManager, Administrador/Junta Directiva y Servicio externo.

### Flujo principal

```text
((Mensaje de error o excepción desde cualquier proceso))
        ↓
[Registrar proceso de origen, datos, fecha y causa]
        ↓
[Clasificar la excepción]
        ↓
<¿Es un fallo técnico temporal?>
   ├─ Sí
   │   ↓
   │ [Marcar operación como REINTENTANDO]
   │   ↓
   │ ((Temporizador: esperar 2 minutos))
   │   ↓
   │ [Ejecutar segundo intento]
   │   ↓
   │ <¿Funcionó?>
   │   ├─ Sí → [Marcar como EXITOSO y retornar al proceso de origen] → (Fin)
   │   └─ No → ((Temporizador: esperar 10 minutos))
   │              ↓
   │           [Ejecutar tercer intento]
   │              ↓
   │           <¿Funcionó?>
   │              ├─ Sí → [Marcar como EXITOSO y retornar] → (Fin)
   │              └─ No → ((Temporizador: esperar 30 minutos))
   │                         ↓
   │                      [Ejecutar cuarto y último intento]
   │                         ↓
   │                      <¿Funcionó?>
   │                         ├─ Sí → [Marcar como EXITOSO y retornar] → (Fin)
   │                         └─ No → [Marcar FALLIDO_PERMANENTE]
   │                                    ↓
   │                                 [Alertar al administrador]
   │                                    ↓
   │                                 (Fin con fallo)
   └─ No
        ↓
<¿Requiere una decisión humana?>
   ├─ No → [Rechazar operación y comunicar el motivo] → (Fin)
   └─ Sí
        ↓
[Crear caso en la bandeja de excepciones]
        ↓
[Administrador revisa antecedentes y evidencias]
        ↓
<¿Cuál es la decisión?>
   ├─ Aprobar excepción → [Ejecutar operación autorizada]
   ├─ Corregir/Revertir → [Crear ajuste compensatorio]
   └─ Rechazar → [Mantener estado anterior]
        ↓
[Registrar decisión, motivo, actor y estados en auditoría]
        ↓
((Mensaje: comunicar resultado a la persona involucrada))
        ↓
(Fin: excepción resuelta)
```

### Casos que pueden llegar a este proceso

- Comprobante duplicado, ilegible o con importe discordante.
- Pago parcial o superior a la deuda.
- Reclamo por una mora posiblemente incorrecta.
- Solicitud extraordinaria de reserva.
- Correo rebotado o proveedor de mensajería no disponible.
- Descuadre al generar cuotas o balances.
- Error al registrar un egreso o al asociar un contrato.
- Incidencia que debe ser reabierta.

---

## Recomendación para dibujarlos en Bizagi

Para evitar diagramas excesivamente grandes, conviene crear un diagrama BPMN por cada proceso. En los procesos que tienen dos flujos claramente diferentes —PROC-02, PROC-06 y PROC-08— se pueden utilizar subprocesos colapsados dentro de un solo diagrama o elaborar dos páginas relacionadas.

Las tareas comunes no necesitan repetirse con todo su detalle:

- **Enviar notificación** puede dibujarse como un subproceso o tarea de llamada a PROC-03.
- **Registrar auditoría** puede mostrarse como una tarea automática antes del final.
- **Gestionar excepción** puede dibujarse como un evento de error que llama al proceso transversal.
- **Validar permisos** puede colocarse al inicio como tarea de servicio o condición de acceso.

