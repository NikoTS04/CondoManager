# PROC-04: Gestión de Reservas de Áreas Comunes y Control de Solvencia

## 1. Ficha del Proceso
- **Identificador:** PROC-04
- **Responsable del Módulo:** **Brandon**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-02 (Pagos y Morosidad), PROC-03 (Notificaciones)

---

## 2. Propósito y Alcance del Proceso
Automatizar el catálogo, calendario y reserva de áreas comunes del condominio (ej. zonas de parrillas/BBQ, salón de usos múltiples/eventos, gimnasio, salas de coworking o canchas deportivas). 

El módulo garantiza la equidad en el uso de los espacios comunes, evita solapamientos de horarios y aplica una **regla de validación cruzada automática con el estado financiero del residente**, impidiendo solicitudes de departamentos que mantengan deudas vencidas impagas.

---

## 3. Disparadores y Eventos de Entrada
1. **Solicitud de Reserva por Residente:** Selección de área común, fecha y franja horaria desde el portal web o móvil.
2. **Evento de Regularización de Deuda (Desbloqueo Automático):** Cuando PROC-02 aprueba un pago que deja la deuda en cero, se emite `SolvenciaRestablecidaEvent`, habilitando automáticamente al residente para reservar.
3. **Cancelación por Residente o Administrador:** Anulación de una reserva previa con liberación del espacio en el calendario.

---

## 4. Reglas de Negocio

### 4.1 Validación Cruzada de Solvencia Financiera
Antes de evaluar la disponibilidad física de un espacio, el motor consulta el estado financiero del departamento solicitante:
- **Condición de Rechazo Automático:** Si el departamento posee al menos una cuota en estado `EN_MORA` o con vencimiento superado tras el periodo de gracia:
  $$\text{Deuda Exigible}(d) > 0 \implies \text{Bloqueo Inmediato de Reserva}$$
- El sistema muestra un mensaje claro al residente: *"Su departamento registra una deuda vencida pendiente. Regularice su cuota para habilitar el sistema de reservas."*

### 4.2 Control de Disponibilidad y Concurrencia
- **Bloqueo de Intervalos (Pessimistic Lock):** Dos residentes no pueden reservar el mismo espacio en horarios coincidentes o solapados.
- **Aforo y Límites de Uso:** Cada área común posee reglas configurables:
  - *Máximo de reservas activas por departamento:* (ej. máximo 2 reservas activas simultáneas para asegurar rotación).
  - *Anticipación mínima y máxima:* (ej. mínimo 24 horas antes, máximo 30 días de antelación).
  - *Costo de mantenimiento o limpieza:* (si aplica canon o depósito de garantía).

---

## 5. Ciclo de Automatización

| Fase | Detalle Técnico |
| :--- | :--- |
| **1. Evento** | Residente envía solicitud: `POST /api/v1/reservas` con `{area_id, fecha, hora_inicio, hora_fin}`. |
| **2. Evaluación de Reglas** | 1. Valida solvencia financiera en `cuotas_mantenimiento` (¿Saldo vencido == 0?). <br>2. Valida disponibilidad en `reservas` para ese horario (`SELECT ... FOR UPDATE`). <br>3. Valida límites de reservas mensuales del residente. |
| **3. Decisión** | ¿Cumple todas las condiciones? <br>- Sí $\rightarrow$ Aprueba y bloquea el horario. <br>- No (Deudor) $\rightarrow$ Rechaza por motivo `"DEUDA_PENDIENTE"`. <br>- No (Ocupado) $\rightarrow$ Rechaza por motivo `"HORARIO_NO_DISPONIBLE"`. |
| **4. Acción** | Si aprueba: <br>1. Crea fila en tabla `reservas` con estado `CONFIRMADA`. <br>2. Emite `ReservaConfirmadaEvent`. <br>3. Genera cargo de limpieza en estado de cuenta si el área tiene tarifa. |
| **5. Verificación** | Confirma que el calendario refleja el bloqueo y dispara a PROC-03 (Alejandro) el envío del comprobante de reserva con las reglas del espacio. |

---

## 6. Máquina de Estados de la Reserva

```
  [ SOLICITADA ]
        │
   (Validación de Solvencia y Horario)
        │
   ┌────┴──────────────────────────┐
   ▼                               ▼
[ CONFIRMADA ]                [ RECHAZADA ]
   │                           - Por Mora
   ├──────────────────┐        - Por Conflicto Horario
   ▼                  ▼
[ COMPLETADA ]   [ CANCELADA ]
 (Uso efectivo)   (Por residente / fuerza mayor)
```

---

## 7. Intervención Humana y Excepciones
- **Reserva de Emergencia o Bloqueo por Mantenimiento:** La Junta Directiva puede bloquear preventivamente un área común (ej. fumigación o reparación de parrilla). Las reservas previamente confirmadas que resulten afectadas son notificadas automáticamente para su reprogramación.
- **Excepción Especial de Junta:** El Administrador puede autorizar manualmente una reserva extraordinaria aprobada por la directiva incluso si existe un acuerdo de pago diferido.

---

## 8. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Departamento solicitante.
- `timestamp`: UTC.
- `accion_ejecutada`: `"SOLICITUD_RESERVA_AREA"` o `"CANCELACION_RESERVA"`.
- `motivo`: `"Reserva de Parrilla 1 aprobada - Residente al día"` / `"Rechazada por mora activa"`.
- `resultado`: `"CONFIRMADA"` o `"RECHAZADA"`.
- `estado_anterior`: `{"area_id": "parrilla-01", "estado_slot": "LIBRE"}`.
- `estado_posterior`: `{"reserva_id": "uuid", "estado_slot": "RESERVADO"}`.

---

## 9. Escenarios de Aceptación (BDD)
```gherkin
Escenario: Rechazo automático de reserva por cuota en mora
  Dado que el departamento 201 tiene una cuota vencida de S/ 170.00 en estado "EN_MORA"
  Cuando el residente del departamento 201 intenta reservar la "Zona de Parrillas" para el próximo sábado
  Entonces el sistema rechaza la solicitud de forma inmediata
  Y muestra el mensaje "No es posible reservar: Su departamento mantiene cuotas vencidas pendientes"
  Y no altera el calendario de disponibilidad del área común.
```
