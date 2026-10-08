# Seguridad y Control de Acceso (Security & RBAC)

## 1. Modelo de Identidad y Roles

CondoManager implementa un esquema de **Control de Acceso Basado en Roles (RBAC)** con granularidad por edificio/condominio.

```
                  ┌──────────────────────┐
                  │      SUPERADMIN      │  (Gestor de Plataforma / Administradora)
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ Condominio / Edificio 1 ]       [ Condominio / Edificio 2 ]
            │
            ├─▶ [ Administrador / Junta Directiva ] (Gestión operativa y conciliación)
            ├─▶ [ Auditor / Revisor Fiscal ]        (Solo lectura y reportes)
            ├─▶ [ Propietario ]                     (Dueño de 1 o N departamentos)
            └─▶ [ Inquilino ]                       (Residente arrendatario de 1 dpto)
```

---

## 2. Matriz de Permisos (RBAC Matrix)

| Recurso / Operación | SuperAdmin | Admin / Junta | Auditor | Propietario | Inquilino |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Crear y Configurar Condominios/Edificios** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Gestionar Presupuesto y Emisión de Cuotas** | ✅ | ✅ | 👁️ (Lectura) | ❌ | ❌ |
| **Reportar Pagos (Subir Comprobante Yape/CCI)** | ❌ | ✅ (Manual) | ❌ | ✅ (Sus dptos) | ✅ (Su dpto) |
| **Bandeja de Conciliación (Aprobar/Rechazar)** | ✅ | ✅ | 👁️ (Lectura) | ❌ | ❌ |
| **Cálculo y Ajuste de Moras** | ✅ | ✅ (Ajuste) | 👁️ (Lectura) | ❌ | ❌ |
| **Consultar Estado de Cuenta** | ✅ | ✅ (Todos) | ✅ (Todos) | ✅ (Sus dptos) | ✅ (Su dpto) |
| **Reservar Áreas Comunes** | ❌ | ✅ (Manual) | ❌ | ✅ (Si está al día) | ✅ (Si está al día) |
| **Bloquear/Desbloquear Reservas** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Registrar Egresos y Proveedores** | ✅ | ✅ | 👁️ (Lectura) | ❌ | ❌ |
| **Abrir Tickets de Incidencias** | ❌ | ✅ | 👁️ (Lectura) | ✅ | ✅ |
| **Asignar y Cerrar Tickets** | ✅ | ✅ | 👁️ (Lectura) | ❌ | ❌ |
| **Descargar Balances y Auditoría** | ✅ | ✅ | ✅ | 👁️ (Balance pub.) | ❌ |
| **Gestión de Traspaso de Mando de Junta** | ✅ | ✅ | ❌ | ❌ | ❌ |

*Leyenda: ✅ Permitido | ❌ Denegado | 👁️ Solo Lectura*

---

## 3. Políticas de Autenticación y Autorización

1. **Autenticación Basada en Tokens (JWT):**
   - Access Tokens con expiración corta (15 a 60 minutos) firmados con algoritmo HS256.
   - Claims obligatorios en el Payload del JWT:
     - `sub`: UUID del usuario.
     - `email`: Correo electrónico institucional o personal.
     - `rol`: `"SUPERADMIN"` | `"ADMIN_JUNTA"` | `"AUDITOR"` | `"PROPIETARIO"` | `"INQUILINO"`.
     - `condominio_id`: Identificador del condominio activo. Puede ser `null` únicamente
       para un `SUPERADMIN` que ejecuta operaciones globales como el alta de un
       condominio; para los demás roles es obligatorio.
     - `departamentos`: Lista de números de departamento asignados (ej. `["102"]`).
     - `tipo_relacion`: `"PROPIETARIO_TITULAR"` | `"INQUILINO"` | `"COPROPIETARIO"` | `"ADMINISTRADOR"`.
   - Refresh Tokens almacenados con hash en base de datos y rotación automática.
2. **Multi-Tenancy y Context Isolation:**
   - Cada solicitud contextual usa el `condominio_id` verificado mediante los claims
     del token JWT o una asignación consultada en base de datos.
   - Un `condominio_id` enviado en ruta, query o body selecciona un recurso, pero nunca
     concede autorización por sí solo.
   - Prohibida la consulta cruzada de datos entre condominios distintos (Row-Level
     Security o filtros forzados en el ORM).
   - `POST /api/v1/condominios` y `GET /api/v1/condominios/{condominio_id}` son
     operaciones globales exclusivas de `SUPERADMIN`; la creación no requiere un
     condominio activo previo.
3. **Múltiples Propiedades por Usuario:**
   - Un propietario que posee 2 o más departamentos dentro del mismo condominio (o en condominios distintos) puede alternar su vista sin requerir cuentas de correo separadas.
   - El estado de morosidad se evalúa a nivel de **unidad habitacional (departamento)** para no bloquear injustamente una propiedad que se encuentra al día si otra presenta atraso, salvo política expresa del condominio.

---

## 4. Matriz de Elementos de Interfaz de Usuario (UI Elements por Pantalla y Rol)

| Pantalla / Vista | Elemento de Interfaz | `SUPERADMIN` | `ADMIN_JUNTA` | `AUDITOR` | `PROPIETARIO` | `INQUILINO` |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Header Global** | Enlace / Acceso `/junta` | ✅ | ✅ | ✅ (Solo Lectura) | ❌ (Oculto) | ❌ (Oculto) |
| | Enlace / Acceso `/residente` | ✅ | ✅ (Soporte) | ❌ (Oculto) | ✅ | ✅ |
| | Selector de Departamentos | ❌ | ❌ | ❌ | ✅ (Si tiene >1) | ❌ (Fijo a 1) |
| | Badge de Rol Activo | ✅ ("SISTEMA") | ✅ ("JUNTA") | ✅ ("AUDITORÍA")| ✅ ("PROPIETARIO")| ✅ ("INQUILINO") |
| **Portal Residente** | Widget Estado de Cuenta | ✅ | ✅ (Cualquiera)| 👁️ (Lectura) | ✅ (Sus dptos) | ✅ (Su dpto) |
| | Formulario Reporte Pago | ❌ | ✅ (Manual) | ❌ | ✅ | ✅ |
| | Botón Reservar Área Común | ❌ | ✅ (Manual) | ❌ | ✅ (Solvente) / 🔒 (Mora) | ✅ (Solvente) / 🔒 (Mora) |
| | Botón Cancelar Reserva | ❌ | ✅ | ❌ | ✅ (>24h antes) | ✅ (>24h antes) |
| **Portal Junta** | Botón Emitir Lote Cuotas | ✅ | ✅ | ❌ (Oculto/Inactivo)| ❌ | ❌ |
| | Botón Ejecutar Motor Moras| ✅ | ✅ | ❌ (Oculto/Inactivo)| ❌ | ❌ |
| | Botón Aprobar Comprobante | ✅ | ✅ | ❌ (Oculto/Inactivo)| ❌ | ❌ |
| | Botón Rechazar Comprobante| ✅ | ✅ | ❌ (Oculto/Inactivo)| ❌ | ❌ |
| | Banner Informativo de Modo| ❌ | ❌ | ✅ ("Modo Auditor") | ❌ | ❌ |
| **Auditoría** | Visualización 7 Campos | ✅ | ✅ | ✅ | ❌ | ❌ |
| | Botón Validar Hash SHA256| ✅ | ✅ | ✅ | ❌ | ❌ |
| | Exportar Bitácora Criptográfica | ✅ | ✅ | ✅ | ❌ | ❌ |

*Leyenda: ✅ Permitido / Visible | ❌ Denegado / Oculto | 🔒 Deshabilitado por Invariante de Negocio | 👁️ Solo Lectura*

---

## 5. Módulo de Transición y Documentación Interna (Gobernanza)

Para mitigar el riesgo de pérdida de conocimiento o traumatismo operativo al renovar la Junta Directiva (Riesgo 1.4 de la plantilla de negocio):

1. **Protocolo de Traspaso de Mando (Handover Protocol):**
   - El Administrador saliente genera un *Acta Digital de Entrega de Cargo* generada automáticamente por el sistema con un clic.
   - Contiene: saldo en cuentas, cuentas por cobrar, morosidad histórica acumulada, contratos vigentes con proveedores y tickets de incidencias pendientes.
2. **Repositorio de Actas y Acuerdos:**
   - Sección digital protegida para almacenar PDFs firmados de actas de asambleas ordinarias y extraordinarias, estatutos del edificio y manual de convivencia.
3. **Guías Operativas Integradas:**
   - Asistente guiado dentro del panel administrativo para inducir a los nuevos directivos en la revisión de pagos, emisión de cuotas y manejo de proveedores.
