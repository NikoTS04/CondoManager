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
   - Access Tokens con expiración corta (15 a 60 minutos).
   - Refresh Tokens almacenados con hash en base de datos y rotación automática.
2. **Multi-Tenancy y Context Isolation:**
   - Cada solicitud HTTP incluye el `condominio_id` verificado mediante los claims del token JWT.
   - Prohibida la consulta cruzada de datos entre condominios distintos (Row-Level Security o filtros forzados en el ORM).
3. **Múltiples Propiedades por Usuario:**
   - Un propietario que posee 2 o más departamentos dentro del mismo condominio (o en condominios distintos) puede alternar su vista sin requerir cuentas de correo separadas.
   - El estado de morosidad se evalúa a nivel de **unidad habitacional (departamento)** para no bloquear injustamente una propiedad que se encuentra al día si otra presenta atraso, salvo política expresa del condominio.

---

## 4. Módulo de Transición y Documentación Interna (Gobernanza)

Para mitigar el riesgo de pérdida de conocimiento o traumatismo operativo al renovar la Junta Directiva (Riesgo 1.4 de la plantilla de negocio):

1. **Protocolo de Traspaso de Mando (Handover Protocol):**
   - El Administrador saliente genera un *Acta Digital de Entrega de Cargo* generada automáticamente por el sistema con un clic.
   - Contiene: saldo en cuentas, cuentas por cobrar, morosidad histórica acumulada, contratos vigentes con proveedores y tickets de incidencias pendientes.
2. **Repositorio de Actas y Acuerdos:**
   - Sección digital protegida para almacenar PDFs firmados de actas de asambleas ordinarias y extraordinarias, estatutos del edificio y manual de convivencia.
3. **Guías Operativas Integradas:**
   - Asistente guiado dentro del panel administrativo para inducir a los nuevos directivos en la revisión de pagos, emisión de cuotas y manejo de proveedores.
