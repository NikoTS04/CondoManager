# Contratos de API y Especificación OpenAPI (API Contracts)

## 1. Filosofía de Contratos en SDD

En el Desarrollo Guiado por Especificaciones (SDD), los contratos de API sirven como el **acuerdo formal desacoplado** entre el Frontend (Next.js/TypeScript) y el Backend (FastAPI/Python), así como entre los diferentes módulos desarrollados por los integrantes del equipo (Anderson, Tarqui, Alejandro, Brandon).

Todas las peticiones y respuestas siguen el estándar **JSON:API / REST** con las siguientes convenciones:
- **Prefijo base:** `/api/v1`
- **Formatos de fecha:** ISO-8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`)
- **Formatos monetarios:** Cadenas de texto o números decimales con 2 dígitos (`"150.00"` / `150.00`) validados estrictamente por Pydantic.
- **Manejo de errores estándar:**
  ```json
  {
    "error_code": "DEUDA_MORA_ACTIVA",
    "mensaje": "Su departamento mantiene cuotas vencidas pendientes. Regularice su situación antes de reservar.",
    "detalles": {
      "departamento_id": "dpto-501",
      "saldo_vencido": "170.00"
    }
  }
  ```

---

## 2. Contratos Principales por Módulo

### Usuarios y autenticación persistente (CON-04 / PROC-05)

Contrato canónico: [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md).
`POST /condominios/{cid}/usuarios` registra contraseña inicial y devuelve una cuenta
inactiva (`201`); `GET` lista las cuentas del contexto. Solo SuperAdmin ejecuta
`PATCH /usuarios/{id}/estado?condominio_id={cid}` con `{"esta_activo": true|false}`.
El estado es global a la identidad y no acredita verificación de correo.
Login consulta PostgreSQL; cuentas inactivas reciben `401 CREDENCIALES_INVALIDAS`.
El JWT conserva el perfil v2 y añade `auth_revision`, comprobada en todas las rutas
protegidas. Una modificación real del estado invalida sesiones anteriores.
El login acepta `condominio_id` opcional para múltiples asignaciones; sin selección
devuelve `409 CONTEXTO_REQUERIDO` con los contextos autorizados tras validar credenciales.
Alta/estado y auditoría se confirman antes de responder. El correo y documento
normalizados tienen unicidad durable; duplicados responden `409 USUARIO_DUPLICADO`.
Las respuestas y errores nunca incluyen contraseña o hash. Invitaciones por correo
se difieren a una evolución posterior.

### Asignaciones de roles (CON-06 / PROC-05)

Contrato: [roles y permisos](../02-domains/05-usuarios-rbac/roles-y-permisos.md).
`GET|PUT|DELETE /condominios/{cid}/usuarios/{uid}/rol` consulta, asigna/reactiva
o revoca lógicamente. PUT recibe únicamente `rol` (ADMIN_JUNTA/AUDITOR/RESIDENTE).
Todos devuelven 200 con `usuario_id`, `condominio_id`, `rol`, `es_activo`.
SuperAdmin gestiona cualquier contexto activo; Junta solo roles Auditor/Residente
de identidades ya asignadas a su contexto. La propia asignación, los SuperAdmin
globales y la elevación por Junta están protegidos (403). Sin asignación: 404
`ROL_NO_ENCONTRADO`; cuerpo inválido: 422 `DATOS_ROL_INVALIDOS`.
Cambios y auditoría son atómicos e invalidan sesiones anteriores; los no-op no.
El listado administrativo añade `rol`, `rol_activo`, `es_superadmin` e incluye
asignaciones revocadas. La concesión global de SuperAdmin continúa mediante CLI.

### Distribución de cuotas (CON-10)

Base: `/api/v1/condominios/{condominio_id}/distribucion`. Requiere Bearer Token.
`SUPERADMIN` opera sobre cualquier condominio; `ADMIN_JUNTA` solo sobre el suyo;
`AUDITOR` solo consulta el suyo. Los demás roles no acceden.

| Método | Entrada | Respuesta |
| :--- | :--- | :--- |
| `PUT` | `{"metodo": "POR_ALICUOTA"}` o `{"metodo": "EQUITATIVA"}`; sin campos extra | `200`, configuración persistida y validada. |
| `GET` | Sin cuerpo | `200`, configuración vigente; consultar no garantiza que los departamentos sigan siendo válidos. |

Respuesta: `id` y `condominio_id` UUID, `metodo`, `actualizado_por` (claim `sub`)
y `actualizado_en` (fecha UTC). El PUT repetido con el mismo método vuelve a validar
los departamentos y, si es válido, conserva respuesta y auditoría anteriores.
Una modificación registra `DISTRIBUCION_CONFIGURADA` transaccionalmente.

Errores con `error_code` y `mensaje`:
- `401 NO_AUTENTICADO` / `TOKEN_INVALIDO` por credenciales ausentes o inválidas.
- `403 DISTRIBUCION_ACCESO_DENEGADO` por rol o contexto ajeno/inválido.
- `404 CONDOMINIO_NO_ENCONTRADO` / `DISTRIBUCION_NO_CONFIGURADA`.
- `422 DATOS_DISTRIBUCION_INVALIDOS` por cuerpo o identificador inválido.
- `422 DISTRIBUCION_SIN_DEPARTAMENTOS` para ambas modalidades.
- `422 DISTRIBUCION_COEFICIENTES_INVALIDOS` si la suma no es exactamente
  `100.0000` o un coeficiente no es válido. Una suma incorrecta incluye
  `detalles.suma_coeficientes` y `detalles.suma_requerida` como cadenas.

Contrato interno CON-11: `DistribucionService.obtener_para_emision(condominio_id)`
revalida y devuelve `DistribucionParaEmision(configuracion_id, metodo, departamentos)`;
cada departamento contiene `id` y `coeficiente: Decimal`. Debe llamarse en la
transacción de emisión. `calcular_distribucion(presupuesto: Decimal, departamentos,
metodo)` devuelve `dict[UUID, Decimal]` ordenado por UUID, sin ajuste residual.
La configuración es vigente por condominio, no versionada por periodo; CON-11
conserva la instantánea del lote y realiza su control de concurrencia.

### 2.1 Módulo de Condominios (CON-2 / PROC-05)

Todos los endpoints de esta sección requieren `Authorization: Bearer <token>` y rol
global `SUPERADMIN`. La ausencia de credenciales responde `401 NO_AUTENTICADO`; un rol
distinto responde `403 ACCESO_DENEGADO`.

- **`GET /api/v1/condominios`**
  - *Descripción:* Lista los condominios activos para que el `SUPERADMIN` seleccione
    el contexto operativo antes de ingresar a procesos como presupuesto mensual.
  - *Response (200 OK):* Arreglo de objetos `CondominioResponse`, ordenado desde el
    condominio creado más recientemente.
  - La lista vacía indica que debe iniciarse el alta del primer condominio.
  - Otros roles reciben `403 ACCESO_DENEGADO`; sus contextos proceden del JWT y no
    pueden escoger arbitrariamente otro condominio.

- **`POST /api/v1/condominios`**
  - *Descripción:* Crea la raíz persistente de un nuevo contexto multi-condominio y
    registra la auditoría `CONDOMINIO_CREADO` en la misma transacción.
  - *Request Body:*
    ```json
    {
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Principal 123, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 20,
      "dias_gracia": 2
    }
    ```
  - *Reglas condicionales:*
    - `MONTO_FIJO`: `monto_mora_fijo` es obligatorio y
      `tasa_mora_porcentaje` debe ser `null`.
    - `PORCENTAJE_SALDO`: `tasa_mora_porcentaje` es obligatoria y
      `monto_mora_fijo` debe ser `null`.
    - `activo`, `id` y `creado_en` son campos de servidor y se rechazan si el cliente
      intenta incluirlos.
  - *Response (201 Created):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Principal 123, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 20,
      "dias_gracia": 2,
      "activo": true,
      "creado_en": "2026-10-08T15:30:00Z"
    }
    ```
  - *Response (422 Unprocessable Entity):* `DATOS_CONDOMINIO_INVALIDOS` cuando los
    campos no cumplen sus rangos o la combinación de mora es inconsistente.

- **`GET /api/v1/condominios/{condominio_id}`**
  - *Descripción:* Recupera exactamente el condominio persistido con el UUID indicado.
  - *Parámetro de ruta:* `condominio_id`, UUID obligatorio.
  - *Response (200 OK):* Mismo objeto de respuesta del alta.
  - *Response (404 Not Found):*
    ```json
    {
      "error_code": "CONDOMINIO_NO_ENCONTRADO",
      "mensaje": "No existe un condominio con el identificador solicitado.",
      "detalles": {
        "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      }
    }
    ```

### 2.2 Presupuestos mensuales (CON-9)

Todos los endpoints requieren `Authorization: Bearer <token>`. `SUPERADMIN` puede
operar cualquier condominio; `ADMIN_JUNTA` puede crear, modificar, aprobar y
consultar solo el condominio de su JWT; `AUDITOR` dispone únicamente del `GET` para
su condominio. Los demás roles y todo cruce de contexto reciben
`403 PRESUPUESTO_ACCESO_DENEGADO`.

- **`POST /api/v1/presupuestos`**
  - *Descripción:* Crea un presupuesto mensual ordinario en `BORRADOR` y registra
    `PRESUPUESTO_CREADO` en la misma transacción.
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "periodo": "2026-10",
      "moneda": "PEN",
      "monto_total": "20000.00",
      "fecha_vencimiento": "2026-10-20"
    }
    ```
  - *Response (201 Created):* Devuelve `PresupuestoResponse` con UUID, estado,
    actor y fechas del servidor.

- **`PUT /api/v1/presupuestos/{id}`**
  - *Descripción:* Reemplaza `periodo`, `moneda`, `monto_total` y
    `fecha_vencimiento` mientras el presupuesto esté en `BORRADOR`. `id` y
    `condominio_id` no pueden modificarse. Registra `PRESUPUESTO_MODIFICADO` con
    las fotografías anterior y posterior.
  - *Request Body:*
    ```json
    {
      "periodo": "2026-10",
      "moneda": "PEN",
      "monto_total": "20500.00",
      "fecha_vencimiento": "2026-10-20"
    }
    ```
  - *Response (200 OK):* Devuelve el borrador actualizado.

- **`POST /api/v1/presupuestos/{id}/aprobar`**
  - *Descripción:* Ejecuta una sola vez la transición `BORRADOR -> APROBADO`,
    asigna `aprobado_por` desde el claim `sub`, registra `aprobado_en` en UTC y
    crea `PRESUPUESTO_APROBADO` atómicamente.
  - *Request Body:* No tiene.
  - *Response (200 OK):* Devuelve el presupuesto aprobado.

- **`GET /api/v1/condominios/{condominio_id}/presupuestos/{periodo}`**
  - *Descripción:* Recupera el presupuesto existente, sea `BORRADOR` o
    `APROBADO`, para el contexto autorizado. El periodo usa `YYYY-MM`.
  - *Response (200 OK):*
    ```json
    {
      "id": "c21b2dc9-b7d4-47d5-b947-90e3ea900f5c",
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "periodo": "2026-10",
      "moneda": "PEN",
      "monto_total": "20000.00",
      "fecha_vencimiento": "2026-10-20",
      "estado": "APROBADO",
      "creado_por": "6a4a78de-c704-44fb-a8b1-9d387ff67c92",
      "creado_en": "2026-10-08T15:30:00Z",
      "aprobado_por": "6a4a78de-c704-44fb-a8b1-9d387ff67c92",
      "aprobado_en": "2026-10-08T16:00:00Z",
      "actualizado_en": "2026-10-08T16:00:00Z"
    }
    ```

Reglas comunes: `periodo` debe ser válido; `monto_total` es una cadena decimal
positiva con dos posiciones y capacidad `NUMERIC(12,2)`; la moneda es `PEN` o
`USD` y coincide con la del condominio; el vencimiento pertenece al periodo; y
solo existe una fila por `(condominio_id, periodo)`.

| HTTP | `error_code` | Uso |
| :---: | :--- | :--- |
| `401` | `NO_AUTENTICADO` | Token ausente, inválido o expirado. |
| `403` | `PRESUPUESTO_ACCESO_DENEGADO` | Rol no permitido o condominio fuera del contexto autorizado. |
| `404` | `PRESUPUESTO_NO_ENCONTRADO` / `CONDOMINIO_NO_ENCONTRADO` | No existe el recurso solicitado. |
| `409` | `PRESUPUESTO_PERIODO_DUPLICADO` | Ya existe el par condominio-periodo. |
| `409` | `PRESUPUESTO_NO_EDITABLE` | El registro ya está aprobado. |
| `422` | `DATOS_PRESUPUESTO_INVALIDOS` | Periodo, moneda, monto o vencimiento incumple el contrato. |

Contrato para CON-11: la emisión recibe `condominio_id + periodo`, recupera el
registro persistido y solo continúa si `estado == APROBADO`. El cliente no puede
reemplazar `monto_total` ni `fecha_vencimiento` durante la emisión.

### 2.3 Emisión de Cuotas (CON-11, Nicolás)
- **`POST /api/v1/cuotas/emitir-lote`**
  - *Descripción:* Genera las cuotas del mes para todas las unidades activas del condominio.
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "periodo": "2026-10"
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "lote_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "total_cuotas_emitidas": 139,
      "monto_total_facturado": "20000.00",
      "periodo": "2026-10",
      "cuotas_cubiertas_saldo_favor": 4,
      "fecha_emision": "2026-10-01T00:00:00Z",
      "fecha_vencimiento": "2026-10-20"
    }
    ```

  - Bearer obligatorio: `SUPERADMIN` o `ADMIN_JUNTA` del condominio.
  - Campos adicionales se rechazan; monto y vencimiento proceden de CON-9 aprobado.
  - `409 LOTE_YA_EMITIDO` ante reintentos; `409 PRESUPUESTO_NO_APROBADO` si falta
    aprobación. `401/403` por identidad/contexto, `404` condominio inexistente,
    `422` padrón/configuración inválidos o condominio inactivo.
  - Transacción única con CON-10 y CON-13; evento durable en outbox.

### 2.4 Módulo de Pagos y Moras (Tarqui)
- **`POST /api/v1/pagos/reportar`**
  - *Descripción:* El residente carga un comprobante de pago bancario (Yape/CCI).
  - *Request Body (Multipart/Form-Data):*
    - `departamento_id`: UUID
    - `banco_origen`: `"BCP"` | `"INTERBANK"` | `"BBVA"` | `"YAPE"` | `"PLIN"`
    - `numero_operacion`: `"00984123"`
    - `fecha_operacion`: `"2026-10-15"`
    - `monto`: `"170.00"`
    - `archivo_voucher`: File (PNG / JPG / PDF)
  - *Response (202 Accepted):*
    ```json
    {
      "comprobante_id": "7b8a1c9e-1234-4567-89ab-cdef01234567",
      "estado": "EN_REVISION",
      "mensaje": "Comprobante recibido. En proceso de conciliación por la Junta Directiva."
    }
    ```

- **`POST /api/v1/pagos/{id}/conciliar`**
  - *Descripción:* La Junta aprueba o rechaza el comprobante.
  - *Request Body:*
    ```json
    {
      "decision": "APROBADO",
      "motivo_rechazo": null,
      "notas_internas": "Validado en extracto de cuenta BCP"
    }
    ```
  - *Response (200 OK):* Retorna la liquidación e imputación a cuotas y el nuevo saldo del departamento.

### 2.5 Módulo de Reservas (Brandon)
- **`POST /api/v1/reservas`**
  - *Descripción:* El residente solicita el uso de un área común.
  - *Request Body:*
    ```json
    {
      "area_id": "parrilla-01",
      "departamento_id": "dpto-302",
      "fecha": "2026-10-25",
      "hora_inicio": "19:00",
      "hora_fin": "22:00"
    }
    ```
  - *Response (201 Created) - Residente Solvente:*
    ```json
    {
      "reserva_id": "res-9988-aabb",
      "estado": "CONFIRMADA",
      "area": "Zona de Parrilla 1",
      "fecha": "2026-10-25",
      "horario": "19:00 - 22:00"
    }
    ```
  - *Response (403 Forbidden) - Residente con Deuda en Mora:*
    ```json
    {
      "error_code": "DEUDA_MORA_ACTIVA",
      "mensaje": "No es posible reservar: Su departamento mantiene cuotas vencidas pendientes."
    }
    ```
  - *Response (409 Conflict) - Horario Ocupado:*
    ```json
    {
      "error_code": "HORARIO_NO_DISPONIBLE",
      "mensaje": "El área común ya se encuentra reservada en el horario solicitado."
    }
    ```

### 2.6 Módulo de Notificaciones (Alejandro)
- **`POST /api/v1/notificaciones/despachar`**
  - *Descripción:* Envío manual o por webhook interno de comunicaciones masivas o alertas.

### 2.7 Módulo de Autenticación y RBAC (PROC-05)

Roles canónicos: `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`. Los tres
endpoints de autenticación usan el contrato v2 descrito en
[identidad-y-alcances.md](../02-domains/05-usuarios-rbac/identidad-y-alcances.md).
`departamentos` contiene vínculos `{departamento_id: UUID, numero, tipo_relacion,
es_activo}`. No existe una relación global de usuario; los administrativos sin
tenencia devuelven `[]`. JWT con `session_version: 2`; tokens anteriores o roles
antiguos/desconocidos reciben `401 SESION_DESACTUALIZADA` y requieren login.
`GET /auth/demo-users` devuelve la lista de perfiles públicos con la misma forma.

Pagos, reservas y notificaciones requieren Bearer. Las listas se filtran por contexto
y vínculo activo; UUID de unidad ajena o condominio distinto responde `403`.
`GET /pagos/comprobantes` sustituye el listado local de comprobantes y
`GET /cuotas/departamentos` devuelve el padrón del portal ya autorizado.
- **`POST /api/v1/auth/login`**
  - *Descripción:* Autentica a un usuario y genera su token de acceso JWT con sus claims y permisos.
  - *Request Body:*
    ```json
    {
      "email": "admin@villabonita3.pe",
      "password": "Password123!"
    }
    ```
  - *Response (200 OK):*
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 3600,
      "usuario": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "admin@villabonita3.pe",
        "nombre": "Carlos",
        "apellido": "Mendoza",
        "rol": "ADMIN_JUNTA",
       "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "departamentos": []
      }
    }
    ```
  - *Response (401 Unauthorized):*
    ```json
    {
      "error_code": "CREDENCIALES_INVALIDAS",
      "mensaje": "Correo o contraseña incorrectos."
    }
    ```

- **`GET /api/v1/auth/me`**
  - *Descripción:* Retorna el perfil y contexto activo del usuario autenticado vía Bearer Token.
  - *Headers:* `Authorization: Bearer <token>`
  - *Response (200 OK):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "email": "residente102@villabonita3.pe",
      "nombre": "Ana",
      "apellido": "Gómez",
       "rol": "RESIDENTE",
       "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
       "departamentos": [{"departamento_id": "48c8c328-8a14-59b6-bc14-c905db21e630", "numero": "102", "tipo_relacion": "PROPIETARIO_TITULAR", "es_activo": true}]
    }
    ```
# Estructura inmobiliaria (CON-3 / USR-02)

Contrato detallado: [estructura-inmobiliaria.md](../02-domains/05-usuarios-rbac/estructura-inmobiliaria.md).
Prefijo `/api/v1/condominios/{condominio_id}`; JWT obligatorio.

| Método | Ruta relativa | Respuesta |
|---|---|---|
| GET / POST | `/edificios` | Lista / recurso 201 con UUID, condominio_id, nombre_bloque, total_pisos |
| GET | `/departamentos` | Lista con filtros opcionales edificio_id y activo |
| POST | `/edificios/{edificio_id}/departamentos` | 201; entrada numero, piso, coeficiente_participacion (string) |
| PATCH | `/departamentos/{departamento_id}/estado` | 200; entrada activo (boolean), no-op si no cambia |
| POST | `/importaciones/previsualizar` | 200; multipart archivo CSV; ninguna escritura |
| POST | `/importaciones/confirmar` | 200; revalida el archivo y guarda filas válidas |

Importación devuelve `total_filas`, `nuevas`, `creadas`, `ya_existentes`, `rechazadas`
y `filas`, cada una con `fila`, `numero`, `piso`, `edificio`, `coeficiente`,
`total_pisos`, `estado` y `errores`. Máximo 2 MiB / 5000 filas. Errores de estructura
usan el sobre `error_code`, `mensaje`, `detalles` opcional; estados 401/403/404/409/422.
