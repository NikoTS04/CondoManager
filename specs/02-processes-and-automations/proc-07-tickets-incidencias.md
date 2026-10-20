# PROC-07: Mesa de Ayuda y Gestión de Tickets de Incidencias

## 1. Ficha del Proceso
- **Identificador:** PROC-07
- **Responsable del Módulo:** **Mantenimiento / Administración**
- **Estado:** En Especificación
- **Versión:** 1.1
- **Módulos Vinculados:** PROC-06 (Proveedores), PROC-03 (Notificaciones)

---

## 2. Propósito y Alcance del Proceso
Permitir a los residentes reportar desperfectos, averías o incidencias en áreas comunes e infraestructura del condominio (ej. luminarias fundidas en pasadizos, filtraciones de agua, fallas en ascensores o portones de acceso), brindando trazabilidad en el ciclo de resolución y cierre formal con retroalimentación del vecino.

---

## 3. Disparadores y Ciclo de Vida del Ticket

### Flujo de Estados:
$$\text{REGISTRADO} \longrightarrow \text{ASIGNADO} \longrightarrow \text{EN\_PROCESO} \longrightarrow \text{RESUELTO} \longrightarrow \text{CERRADO}$$

1. **Apertura por Residente:** El vecino completa el formulario indicando ubicación (Torre/Piso/Área), categoría, nivel de urgencia percibido (Baja, Media, Alta, Urgente) y adjunta fotos de evidencia.
2. **Asignación por Administración:** El administrador evalúa la falla y asigna el ticket al proveedor correspondiente registrado en PROC-06.
3. **Resolución y Cierre:** El contratista repara la falla, se ingresa el costo de repuestos si aplica, y el residente confirma su conformidad y calificación de atención.

---

## 4. Mejora Futura Propuesta: Clasificación y Asignación con IA + RPA

> **Estado:** Propuesta pendiente (`TIC-06`). No implementada.

La mejora conserva el flujo anterior y asiste la clasificación y asignación mediante dos capacidades complementarias:

- **IA:** interpreta la descripción y evidencia, recomienda categoría, prioridad y especialidad responsable, detecta posibles duplicados y entrega un nivel de confianza.
- **RPA:** aplica reglas predefinidas y ejecuta la creación, asignación, inicio del plazo, actualización de estado, auditoría y verificación del resultado.

La IA no autoriza por sí sola el cierre, rechazo, gasto o tratamiento de una incidencia crítica. RPA tampoco interpreta libremente la incidencia: solo ejecuta reglas y acciones permitidas.

### 4.1 Regla ECA

> **CUANDO** un residente reporte una incidencia, **SI** la IA la clasifica con confianza suficiente, el caso no es crítico, no existe un duplicado confirmado y hay un proveedor compatible, **ENTONCES** RPA crea y asigna el ticket, inicia el plazo y registra la ejecución.

Si alguna condición no se cumple, el ticket permanece `REGISTRADO` o pasa a una bandeja de excepciones para revisión humana.

### 4.2 Ciclo Propuesto

| Fase | Ejecución |
| :--- | :--- |
| **Evento** | El residente registra descripción, ubicación, urgencia percibida y evidencia. |
| **Análisis IA** | Sugiere categoría, prioridad, duplicados y especialidad responsable; entrega nivel de confianza. |
| **Evaluación de reglas** | Valida umbral, criticidad, datos completos, duplicidad y proveedor compatible. |
| **Decisión** | Procesar automáticamente o solicitar revisión humana. |
| **Acción RPA** | Crea, asigna, inicia el plazo, actualiza el estado y registra auditoría. |
| **Verificación** | Confirma ticket único, estado permitido, responsable compatible, plazo y auditoría persistida. |
| **Retroalimentación** | El administrador corrige recomendaciones y el residente confirma o rechaza la solución. |

### 4.3 Modalidad de RPA

- **Desatendida:** procesa casos normales, controla plazos, verifica poscondiciones y escala vencimientos en segundo plano.
- **Atendida:** presenta la recomendación y solicita confirmación ante baja confianza, criticidad, ambigüedad, costo elevado o falta de proveedor compatible.

---

## 5. Detección, Recuperación y Control

| Señal | Decisión |
| :--- | :--- |
| Datos obligatorios incompletos | Solicitar corrección sin perder el reporte. |
| Baja confianza o contradicción | Detener asignación desatendida y solicitar revisión. |
| Señal crítica | Priorizar y escalar inmediatamente a una persona. |
| Posible duplicado | Proponer vinculación; no fusionar ni eliminar automáticamente. |
| Proveedor incompatible o no disponible | Buscar alternativa o escalar al administrador. |
| Fallo temporal | Reintentar con límite sin duplicar acciones. |
| Ejecución parcial | Marcar `FALLIDO_CONTROL` y continuar desde el último paso seguro. |
| Residente no conforme | Reabrir el ticket en `EN_PROCESO` y conservar el motivo. |

El administrador puede detener, corregir, reasignar o reanudar la automatización. Ningún fallo elimina el reporte original.

---

## 6. Indicadores de Evaluación

1. **Tiempo promedio de asignación:** suma de tiempos entre registro y asignación / tickets asignados.
2. **Exactitud de clasificación confirmada:** recomendaciones aceptadas sin corrección / recomendaciones revisadas x 100.
3. **Resolución dentro del plazo:** tickets resueltos dentro del SLA / tickets resueltos x 100.

Los indicadores se medirán durante un piloto; no representan resultados obtenidos.

---

## 7. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Departamento del residente informante.
- `timestamp`: UTC.
- `accion_ejecutada`: `"CREACION_TICKET_INCIDENCIA"`, `"ASIGNACION_RPA_TICKET"`, `"CORRECCION_RECOMENDACION_IA"` o `"CIERRE_CONFORME_TICKET"`.
- `motivo`: `"Falla en luminaria de pasadizo piso 4 - Atendido por electricista"`.
- `resultado`: `"RESUELTO"`.
- `estado_anterior`: `{"estado_ticket": "EN_PROCESO"}`.
- `estado_posterior`: `{"estado_ticket": "RESUELTO", "costo_reparacion": 45.00}`.

Cuando participe la mejora `TIC-06`, también se registra la recomendación original, confianza, reglas evaluadas, corrección humana, paso fallido, número de reintentos y verificación final.
