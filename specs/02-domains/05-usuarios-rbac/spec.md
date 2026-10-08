# Dominio 05: Condominios, Usuarios, Roles (RBAC) y Departamentos

## 1. Ficha del Dominio

- **Identificador:** DOM-05 / PROC-05
- **Historias cubiertas:** CON-2 / USR-01 y las historias de identidad y acceso de PROC-05
- **Responsable:** **Junta Directiva / Administración**
- **Estado:** Aprobado para implementación
- **Versión:** 2.1
- **Módulos de código:** `src/modules/condominios/`, `src/modules/usuarios/`

---

## 2. Propósito y Alcance

Administrar la raíz de aislamiento de la plataforma (`Condominio`), el catálogo de
residentes, copropietarios, inquilinos y directivos, y sus permisos mediante RBAC
contextual por condominio.

La historia CON-2 establece el contrato mínimo para crear y consultar un condominio.
Las historias posteriores deben utilizar el `condominio_id` persistido por este flujo;
no se permiten identificadores fijos, valores de demostración ni contextos tomados de
un cuerpo de solicitud sin comprobarlos contra la identidad autenticada.

---

## 3. Configuración de un Condominio (CON-2 / USR-01)

### 3.1 Actor autorizado

- Únicamente un usuario autenticado con rol global `SUPERADMIN` puede crear un
  condominio.
- Una solicitud sin Bearer Token válido responde `401 Unauthorized`.
- Un usuario autenticado con cualquier otro rol responde `403 Forbidden`.
- La autorización se valida siempre en el backend. Ocultar el formulario en el
  frontend no constituye un control de seguridad.

### 3.2 Datos de creación

| Campo de dominio | Tipo | Regla |
|---|---|---|
| `nombre` | Texto, 1-150 caracteres | Obligatorio después de eliminar espacios exteriores. |
| `direccion` | Texto, 1-500 caracteres | Obligatoria después de eliminar espacios exteriores. |
| `moneda` | Enum | Solo `PEN` o `USD`. |
| `regla_mora_tipo` | Enum | `MONTO_FIJO` o `PORCENTAJE_SALDO`. |
| `monto_mora_fijo` | Decimal `NUMERIC(12,2)` nullable | Obligatorio y mayor o igual que cero cuando la regla es `MONTO_FIJO`; nulo en caso contrario. |
| `tasa_mora_porcentaje` | Decimal `NUMERIC(7,4)` nullable | Obligatoria entre `0.0000` y `100.0000` cuando la regla es `PORCENTAJE_SALDO`; nula en caso contrario. |
| `dia_vencimiento` | Entero | Día calendario entre 1 y 28. Es el nombre canónico; reemplaza al ambiguo `dias_corte`. |
| `dias_gracia` | Entero | Entre 0 y 30 días calendario. |

Los importes y tasas se reciben y devuelven como cadenas decimales. Está prohibido
usar `float` para validarlos, persistirlos o serializarlos.

### 3.3 Resultado e invariantes

1. La creación genera un `id` UUID no proporcionado por el cliente.
2. El condominio se persiste con `activo = true` y `creado_en` en UTC.
3. El cliente no puede establecer `activo` durante la creación.
4. La operación de creación y su entrada de auditoría se confirman en una sola
   transacción; ante cualquier fallo, ninguna de las dos queda persistida.
5. La respuesta `201 Created` devuelve el recurso persistido, incluido su `id`,
   configuración normalizada, estado y fecha de creación.
6. `GET /api/v1/condominios/{condominio_id}` devuelve exactamente un condominio o
   `404 CONDOMINIO_NO_ENCONTRADO`; nunca sustituye el recurso solicitado por uno
   predeterminado.

### 3.4 Aislamiento multi-condominio

- `condominio_id` es la raíz de partición lógica de todos los datos de negocio.
- Toda tabla dependiente debe incluir directa o indirectamente una relación obligatoria
  con `condominios.id`.
- Los servicios contextuales obtienen el condominio autorizado desde el JWT o desde
  una asignación validada en base de datos. Un `condominio_id` recibido del cliente no
  concede acceso por sí solo.
- Toda consulta y mutación contextual debe filtrar por el condominio autorizado además
  del identificador del recurso.
- Las pruebas de integración deben crear al menos dos condominios y demostrar que la
  consulta de uno no devuelve ni modifica datos del otro.

### 3.5 Auditoría

La creación registra una entrada inmutable con:

- `condominio_id`: UUID recién creado.
- `departamento_id`: `null`.
- `accion_ejecutada`: `CONDOMINIO_CREADO`.
- `motivo`: `CONFIGURACION_INICIAL_SUPERADMIN`.
- `resultado`: `EXITOSO`.
- `actor_tipo`: `SUPERADMIN`.
- `actor_id`: claim `sub` del JWT.
- `estado_anterior`: `{}`.
- `estado_posterior`: representación persistida sin secretos.

---

## 4. Matriz de Roles

- `SUPERADMIN`: Control global de la plataforma multi-condominio y único rol que crea
  condominios.
- `ADMIN_JUNTA`: Gestión total del condominio asignado (emisión, conciliación,
  proveedores), sin permiso para crear otros condominios.
- `AUDITOR`: Lectura de auditoría y estados financieros dentro de los condominios
  autorizados.
- `PROPIETARIO`: Gestión de sus propiedades, consulta de cuentas y reserva de áreas.
- `INQUILINO`: Reporte de pagos, tickets y reservas de su departamento arrendado.

---

## 5. Criterios de terminado de CON-2

CON-2 se considera terminada únicamente cuando:

1. El contrato OpenAPI y el diccionario de datos coinciden con esta especificación.
2. Un `SUPERADMIN` puede crear y consultar un condominio persistente.
3. Las solicitudes anónimas y de roles no autorizados reciben `401` y `403`,
   respectivamente.
4. La respuesta de creación contiene UUID, `activo = true` y `creado_en`.
5. La auditoría se registra atómicamente.
6. Una prueba con dos condominios confirma el aislamiento.
7. Los escenarios ejecutables de
   `features/condominios.feature` y las pruebas unitarias y de integración pasan.
