# PROC-05: Gestión de Usuarios, Roles y Asignación de Unidades

## 1. Ficha del Proceso
- **Identificador:** PROC-05
- **Responsable del Módulo:** **Administración / Junta Directiva**
- **Estado:** En Especificación
- **Versión:** 1.0
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos), PROC-04 (Reservas)

---

## 2. Propósito y Alcance del Proceso
Permitir la creación, configuración y mantenimiento del directorio de usuarios del sistema (Administradores, Propietarios, Inquilinos y Auditores), vinculando a cada usuario con sus respectivos departamentos o unidades inmobiliarias.

El diseño garantiza la escalabilidad multi-edificio, permitiendo que un usuario sea propietario de múltiples departamentos en un mismo condominio o en diferentes condominios sin duplicar cuentas.

---

## 3. Disparadores y Eventos de Entrada
1. **Alta Administrativa (Onboarding Inicial):** Carga masiva o individual de departamentos y propietarios mediante archivo CSV/Excel o interfaz web.
2. **Registro de Inquilino / Mudanza:** El propietario o administrador registra un nuevo inquilino y asigna la vigencia del contrato de arrendamiento.
3. **Cambio de Directiva:** Actualización del rol de miembros de la Junta Directiva (asignación o retiro de permisos administrativos).

---

## 4. Reglas de Negocio

### 4.1 Relación Usuario - Unidad Habitacional
- Cada unidad inmobiliaria (departamento) debe tener al menos un **Propietario Titular** registrado con DNI/CE, nombre completo, teléfono y correo electrónico.
- Una unidad puede tener opcionalmente uno o más **Inquilinos** registrados.
- Si una unidad cambia de arrendatario:
  - Se desvincula la cuenta del inquilino saliente (revocando su acceso a reservas y notificaciones operativas).
  - El historial de pagos y cuotas históricas permanece inalterable vinculado a la unidad habitacional.

### 4.2 Restricción de Visibilidad por Rol
- Los residentes (propietarios e inquilinos) **únicamente** pueden visualizar los estados de cuenta, comprobantes y datos de su propio departamento.
- La Junta Directiva y el Auditor pueden consultar la información consolidada de todas las unidades del condominio.

---

## 5. Ciclo de Automatización

```
 [ Administrador ingresa DNI y Correo ]
                  │
                  ▼
 [ Sistema valida unicidad de Correo ] ──▶ [ Genera Token de Activación ]
                  │
                  ▼
 [ Asigna Rol y Departamento ] ──▶ [ Despacha Invitación a PROC-03 (Alejandro) ]
                  │
                  ▼
 [ Residente activa contraseña e inicia sesión ]
```

---

## 6. Registro de Auditoría
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Departamento asignado.
- `timestamp`: UTC.
- `accion_ejecutada`: `"ALTA_USUARIO"` o `"VINCULACION_INQUILINO"`.
- `motivo`: `"Registro de inquilino según contrato de alquiler"`.
- `resultado`: `"EXITOSO"`.
- `estado_anterior`: `{"inquilino_id": null}`.
- `estado_posterior`: `{"inquilino_id": "usr-883", "nombre": "Juan Perez"}`.
