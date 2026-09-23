# Dominio 05: Gestión de Usuarios, Roles (RBAC) y Departamentos

## 1. Ficha del Dominio
- **Identificador:** DOM-05 / PROC-05
- **Responsable:** **Junta Directiva / Administración**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/usuarios/`

---

## 2. Propósito y Alcance
Administrar el catálogo de residentes, copropietarios, inquilinos y directivos del condominio, controlando sus permisos de acceso mediante el modelo RBAC contextual por condominio.

---

## 3. Matriz de Roles
- `SUPERADMIN`: Control global de la plataforma multi-condominio.
- `ADMIN_JUNTA`: Gestión total del condominio asignado (emisión, conciliación, proveedores).
- `AUDITOR`: Lectura irrestricta de auditoría y estados financieros.
- `PROPIETARIO`: Gestión de sus propiedades, consulta de cuentas y reserva de áreas.
- `INQUILINO`: Reporte de pagos, tickets y reservas de su departamento arrendado.
