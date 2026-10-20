# PROC-05: Configuración de Condominios, Usuarios, Roles y Asignación de Unidades

Las operaciones del Sprint 2 de alta, vínculos, roles y catálogo de áreas se implementan usando la [base CON-72](../05-api/sprint-2-contratos.md#3-usuarios-y-accesos--jerson). Se conserva el alta inactiva y la habilitación manual de CON-04. Las mutaciones reales de vínculo/rol invalidan sesiones anteriores; la concesión global SuperAdmin queda fuera de la API contextual de roles.

## 1. Ficha del Proceso
- **Identificador:** PROC-05
- **Responsable del Módulo:** **Administración / Junta Directiva**
- **Estado:** En Especificación
- **Versión:** 1.1
- **Módulos Vinculados:** PROC-01 (Cuotas), PROC-02 (Pagos), PROC-04 (Reservas)
- **Historia prioritaria:** CON-2 / USR-01 — Configurar un condominio

---

## 2. Propósito y Alcance del Proceso
Permitir la creación y configuración de condominios y el mantenimiento del directorio
de usuarios del sistema (Administradores, Propietarios, Inquilinos y Auditores),
vinculando a cada usuario con sus respectivos departamentos o unidades inmobiliarias.

El diseño garantiza la escalabilidad multi-edificio, permitiendo que un usuario sea propietario de múltiples departamentos en un mismo condominio o en diferentes condominios sin duplicar cuentas.

---

## 3. Disparadores y Eventos de Entrada
1. **Alta de Condominio:** Un `SUPERADMIN` inicia el onboarding de una nueva
   organización desde la interfaz web o la API.
2. **Alta Administrativa (Onboarding Inicial):** Carga masiva o individual de
   departamentos y propietarios mediante archivo CSV/Excel o interfaz web.
3. **Registro de Inquilino / Mudanza:** El propietario o administrador registra un
   nuevo inquilino y asigna la vigencia del contrato de arrendamiento.
4. **Cambio de Directiva:** Actualización del rol de miembros de la Junta Directiva
   (asignación o retiro de permisos administrativos).

---

## 4. Reglas de Negocio

### CON-04 — Alta administrativa vigente

El administrador define la contraseña inicial y crea una cuenta inactiva. Solo
SuperAdmin habilita o deshabilita su estado desde la aplicación. Login y peticiones
protegidas verifican PostgreSQL y revisión de sesión. La invitación y la verificación
por correo quedan para una evolución posterior. Contrato completo y criterios:
[alta-administrativa.md](../02-domains/05-usuarios-rbac/alta-administrativa.md).

### CON-06 — Asignación y revocación de roles

SuperAdmin gestiona roles contextuales; Junta solo Auditor/Residente de su
condominio, sin modificar a otros administradores ni a sí misma. Las asignaciones
se revocan con `es_activo=false`, conservando vínculos e historial. Cada cambio
real incrementa la revisión global y audita atómicamente. Repetir una operación
idéntica es un no-op. Contrato y escenarios:
[roles-y-permisos.md](../02-domains/05-usuarios-rbac/roles-y-permisos.md).

### 4.1 Configuración Inicial del Condominio (CON-2)

- Solo `SUPERADMIN` puede ejecutar `POST /api/v1/condominios`.
- La solicitud contiene nombre, dirección, moneda, modalidad de mora, valor de la
  modalidad, día de vencimiento y días de gracia según el contrato OpenAPI.
- `dia_vencimiento` es un día calendario entre 1 y 28; `dias_gracia` se encuentra
  entre 0 y 30.
- La modalidad `MONTO_FIJO` exige `monto_mora_fijo` y prohíbe
  `tasa_mora_porcentaje`. La modalidad `PORCENTAJE_SALDO` aplica la regla inversa.
- La persistencia asigna UUID, `activo = true` y fecha UTC. Esos valores no los decide
  el cliente.
- La creación y la auditoría `CONDOMINIO_CREADO` son atómicas.
- El identificador persistido es la entrada obligatoria para CON-3 y CON-9. No se
  permite continuar el onboarding con identificadores simulados.
- Las consultas de recursos dependientes siempre combinan el identificador del recurso
  con el contexto de condominio autorizado.

### 4.2 Relación Usuario - Unidad Habitacional
Contrato ejecutable de CON-05:
[vinculos-departamentos.md](../02-domains/05-usuarios-rbac/vinculos-departamentos.md).
El primer vínculo activo es de titular y no se retira al último sin reemplazo.
La administración crea/cambia/restaura/revoca vínculos por UUID en su contexto;
un cambio real audita e invalida sesiones atómicamente, conservando el historial.
- Cada unidad inmobiliaria (departamento) debe tener al menos un **Propietario Titular** registrado con DNI/CE, nombre completo, teléfono y correo electrónico.
- Una unidad puede tener opcionalmente uno o más **Inquilinos** registrados.
- Si una unidad cambia de arrendatario:
  - Se desvincula la cuenta del inquilino saliente (revocando su acceso a reservas y notificaciones operativas).
  - El historial de pagos y cuotas históricas permanece inalterable vinculado a la unidad habitacional.

### 4.3 Restricción de Visibilidad por Rol
- Los residentes (propietarios e inquilinos) **únicamente** pueden visualizar los estados de cuenta, comprobantes y datos de su propio departamento.
- La Junta Directiva y el Auditor pueden consultar la información consolidada de todas las unidades del condominio.

### 4.4 Autenticación y Resolución de Contexto de Sesión
- Toda solicitud a rutas protegidas requiere un Bearer Token JWT en el encabezado `Authorization`.
- El backend resuelve automáticamente el usuario activo (`get_current_user`) y valida que:
  1. Si invoca acciones de administración (`ADMIN_JUNTA`, `SUPERADMIN`), su claim `rol` coincida exactamente.
  2. Si es `AUDITOR`, sus peticiones estén restringidas estrictamente a métodos de lectura idempotente (`GET`), rechazando cualquier mutación con `403 Forbidden`.
   3. Si es `RESIDENTE`, cualquier operación sobre un `departamento_id` pertenezca a
      un vínculo activo de `departamentos` en su token y a su condominio.
- Los cuatro roles coinciden con el SQL. Propietario/inquilino son relaciones de
  tenencia por unidad, no roles. Contrato y renovación de sesiones en
  [identidad-y-alcances.md](../02-domains/05-usuarios-rbac/identidad-y-alcances.md).

---

## 5. Ciclo de Automatización de Autenticación y Acceso

### 5.1 Alta de condominio

```text
[ SUPERADMIN autenticado ]
           │
           ▼
[ Validar datos y regla de mora ]
           │
           ▼
[ Persistir condominio ACTIVO ]
           │
           ▼
[ Registrar auditoría en la misma transacción ]
           │
           ▼
[ Devolver 201 + UUID persistido ]
```

Si falla la validación se responde `422` sin persistir. Si falla la persistencia o la
auditoría, la transacción completa se revierte.

### 5.2 Autenticación y acceso

```
 [ Usuario ingresa Email y Contraseña ]
                  │
                  ▼
 [ API valida credenciales y cuenta activa contra hash PBKDF2 en PostgreSQL ]
                  │
                  ▼
 [ Resuelve Roles y Departamentos asociados ]
                  │
                  ▼
 [ Emite JWT v2 con rol SQL y vínculos UUID por departamento ]
                  │
                  ▼
 [ Frontend adapta elementos de UI según el Rol ]
```

---

## 6. Registro de Auditoría

### 6.1 Alta de condominio

- `condominio_id`: condominio recién creado.
- `departamento_id`: `null`.
- `timestamp`: UTC.
- `accion_ejecutada`: `CONDOMINIO_CREADO`.
- `motivo`: `CONFIGURACION_INICIAL_SUPERADMIN`.
- `resultado`: `EXITOSO`.
- `actor_tipo`: `SUPERADMIN`.
- `actor_id`: claim `sub` del JWT.
- `estado_anterior`: `{}`.
- `estado_posterior`: configuración persistida.

### 6.2 Altas y vinculaciones de usuarios
Campos mínimos registrados en `auditoria_logs`:
- `departamento_id`: Departamento asignado.
- `timestamp`: UTC.
- `accion_ejecutada`: `"ALTA_USUARIO"` o `"VINCULACION_INQUILINO"`.
- `motivo`: `"Registro de inquilino según contrato de alquiler"`.
- `resultado`: `"EXITOSO"`.
- `estado_anterior`: `{"inquilino_id": null}`.
- `estado_posterior`: `{"inquilino_id": "usr-883", "nombre": "Juan Perez"}`.

---

## 7. Verificación de CON-2

La automatización debe ejecutar
`specs/02-domains/05-usuarios-rbac/features/condominios.feature`. El documento
`specs/04-acceptance-criteria/auth-and-rbac.feature.md` conserva el detalle legible de
los criterios: alta exitosa, rechazo sin autenticación, rechazo por rol, consulta
persistente, validación condicional de mora y aislamiento entre dos condominios.
