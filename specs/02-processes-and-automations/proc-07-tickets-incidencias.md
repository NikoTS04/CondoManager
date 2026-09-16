# PROC-07: Mesa de Ayuda y Gestión de Tickets de Incidencias

## 1. Ficha del Proceso
- **Identificador:** PROC-07
- **Responsable del Módulo:** **Mantenimiento / Administración**
- **Estado:** En Especificación
- **Versión:** 1.0
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

## 4. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Departamento del residente informante.
- `timestamp`: UTC.
- `accion_ejecutada`: `"CREACION_TICKET_INCIDENCIA"` o `"CIERRE_CONFORME_TICKET"`.
- `motivo`: `"Falla en luminaria de pasadizo piso 4 - Atendido por electricista"`.
- `resultado`: `"RESUELTO"`.
- `estado_anterior`: `{"estado_ticket": "EN_PROCESO"}`.
- `estado_posterior`: `{"estado_ticket": "RESUELTO", "costo_reparacion": 45.00}`.
