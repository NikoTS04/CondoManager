# Contratos de API y Especificación OpenAPI (API Contracts)

Base de implementación del Sprint 2: [CON-72 — contratos por historia](sprint-2-contratos.md). La guía reúne los acuerdos y enlaza OpenAPI y eventos. El OpenAPI describe el contrato objetivo y distingue operaciones pendientes/parciales; su publicación no implica que los endpoints estén implementados.

## 1. Filosofía de Contratos en SDD

En el Desarrollo Guiado por Especificaciones (SDD), los contratos de API sirven como el **acuerdo formal desacoplado** entre el Frontend (Next.js/TypeScript) y el Backend (FastAPI/Python), así como entre los diferentes módulos desarrollados por los integrantes del equipo (Anderson, Tarqui, Alejandro, Brandon).

Las operaciones siguen **HTTP REST con JSON**, con multipart para vouchers y respuesta binaria para su descarga. Convenciones:
- **Prefijo base:** `/api/v1`
- **Fechas y horas:** calendario `America/Lima`, fechas `YYYY-MM-DD`, configuración del catálogo `HH:MM` y nuevas reservas `HH:MM:00`; instantes de auditoría/eventos en UTC. Intervalos `[inicio, fin)`; históricos sin marca local conservan interpretación UTC.
- **Importes:** respuestas/eventos con dos decimales (`"150.00"`), dentro de `NUMERIC(12,2)`; cálculos con `Decimal`. La configuración CON-39 acepta cadenas con hasta dos decimales y normaliza su salida. Los nuevos contratos rechazan números JSON, exponentes y precisión adicional.
- **Errores:** objeto en raíz; `detalles` opcional es un objeto, con validaciones en `detalles.errores`. No incluir valores sensibles.
- **Manejo de errores estándar:**
  ```json
  {
    "error_code": "DEUDA_MORA_ACTIVA",
    "mensaje": "Su departamento mantiene cuotas vencidas pendientes. Regularice su situación antes de reservar.",
    "detalles": {
      "departamento_id": "6c78c3b5-1efb-4d0b-a5f8-78fc17364083",
      "saldo_vencido": "170.00"
    }
  }
  ```

---

## 2. Contratos Principales por Módulo

### Pagos persistentes y solvencia (CON-22 / CON-70 / CON-42)

Contrato canónico: [integración financiera Sprint 2](../02-domains/02-pagos-y-moras/sprint-2-anderson.md).
La excepción temporal a S3 usa carpeta local privada y solo nombre en `url_voucher`.
`POST /pagos/vouchers` recibe multipart `departamento_id` y `voucher_file` (PNG/JPG/PDF,
máximo 5 MiB); devuelve 201 con nombre, MIME y tamaño. `POST /pagos/reportar` mantiene
su JSON y devuelve 202 para creación, 200 `VOUCHER_EN_EVALUACION` para duplicado
propio en revisión o 409 para reutilización inválida. El hash no sustituye permisos.
`GET /pagos/comprobantes` conserva CONCILIADO como alias público de APROBADO.
`GET /pagos/{id}/voucher` descarga privada; `GET /pagos/{id}/resultado` consulta el
resultado persistido de revisión. `POST /pagos/{id}/conciliar` admite aprobación,
observación y rechazo; solo administración autorizada, con motivo obligatorio para
las dos últimas. Los estados terminales no se vuelven a aplicar.
Errores controlados: 401 sin sesión, 403 fuera de alcance o AUDITOR escribiendo,
404 recurso inexistente/archivo histórico no local, 413 archivo mayor a 5 MiB,
422 archivo/contenido/datos inválidos y 503 almacenamiento local no disponible.
CON-42 aporta guard y `GET /pagos/solvencia/{departamento_id}`; devuelve
`departamento_id`, `saldo_vencido`, `habilitado_reservas`. Una reserva bloqueada
conserva 403 `DEUDA_MORA_ACTIVA` con saldo autorizado y no ocupa el horario.

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

### Vínculos con departamentos (CON-05 / PROC-05)

Contrato: [vínculos](../02-domains/05-usuarios-rbac/vinculos-departamentos.md).
`GET /condominios/{cid}/usuarios/{uid}/departamentos` lista relaciones del contexto,
incluidas las revocadas. `PUT|DELETE` sobre esa ruta más `/{departamento_id}`
asigna/cambia/restaura o revoca (200). PUT solo recibe `tipo_relacion`.
Administración autorizada, rol contextual vigente para asignar y unidad activa.
Primer vínculo de titular; retirar/cambiar al último titular responde
`409 TITULAR_REQUERIDO`. Repeticiones idénticas no cambian revisión ni auditoría.
Un cambio real invalida JWT anteriores y registra el departamento en auditoría.
`GET /cuotas/departamentos` y lectura de unidades en pagos/reservas usan SQL real;
el portal añade edificio para distinguir números de unidad repetidos.

### Catálogo de áreas comunes (CON-39 / PROC-04)

Contrato: [catálogo de áreas](../02-domains/04-reservas/catalogo-areas.md).
`GET|POST /condominios/{cid}/areas`, `GET|PUT /condominios/{cid}/areas/{aid}` y
`PATCH /condominios/{cid}/areas/{aid}/estado`. Administración contextual; Auditor
solo lee. Configuración completa: nombre, descripción, edificio opcional, aforo,
costo decimal como cadena, apertura/cierre `HH:MM` y duración máxima entera.
POST devuelve 201; consultas, PUT y estado 200. No-op sin nueva auditoría.
El portal `GET /areas` usa SQL activo y edificio autorizado, con moneda del
condominio y `zona_horaria=America/Lima`. Nuevas reservas leen esas condiciones:
409 AREA_INACTIVA, 400 HORARIO_INVALIDO o 403 por edificio/contexto no autorizado.
Cambios y auditoría son atómicos; no hay borrado físico. Validaciones de catálogo:
422 DATOS_AREA_INVALIDOS. Pertenencia desconocida: 404, sin filtrar datos ajenos.

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

### 2.4 Pagos — Anderson / CON-22 y CON-70; Brandon / CON-23

Contrato completo, estados y errores: [pagos del Sprint 2](sprint-2-contratos.md#5-pagos--anderson-y-brandon-persistencia-con-70). Esquemas y campos obligatorios: [sprint-2.schemas.yaml](../03-contracts/openapi/sprint-2.schemas.yaml).

| Operación | Entrada / resultado |
|---|---|
| `POST /pagos/reportar` | Multipart: UUID de departamento, `banco`, `numero_operacion`, `fecha_operacion`, `monto`, `archivo_voucher`. PNG/JPEG/PDF hasta 5 MiB. `202` nuevo o `200` reintento propio en revisión, con UUID, estado, código, mensaje y hash. |
| `GET /pagos/comprobantes` | Registros autorizados con estado `EN_REVISION`, `APROBADO`, `OBSERVADO` o `RECHAZADO`; descarga privada mediante ruta generada por servidor. |
| `GET /pagos/{comprobante_id}/voucher` | Archivo binario con autorización de recurso y `Cache-Control: no-store`. |
| `PUT /pagos/{comprobante_id}/voucher` | Multipart de archivo para subsanar un observado; preserva metadatos/hash, versiona el archivo y vuelve a revisión; `202`. |
| `POST /pagos/{comprobante_id}/conciliar` | Administración decide aprobación, observación o rechazo; motivo para los dos últimos; `200` con resultado financiero real persistido. |

No se acepta `url_voucher` del cliente como prueba de carga. La recepción no cancela deuda. Una aprobación previa o reutilización en otra unidad responde `409`; las respuestas nunca revelan datos de una unidad ajena. Normalización, unicidad y subsanación se definen en la guía del Sprint 2 enlazada arriba.

### 2.5 Catálogo, disponibilidad y reservas

Contrato completo: [reservas del Sprint 2](sprint-2-contratos.md#4-catálogo-disponibilidad-y-reservas). Catálogo CON-39 de Jerson; disponibilidad CON-40 y cancelación CON-46 de Gerardo; creación y concurrencia CON-41/43 de Brandon; deuda CON-42 de Anderson; persistencia CON-73 de Nicolás.

| Operación | Contrato |
|---|---|
| `GET /areas` | Catálogo SQL activo del portal, filtrado por contexto y edificio, con apertura/cierre diarios, duración máxima y moneda. |
| `GET|POST /condominios/{cid}/areas`, `GET|PUT /condominios/{cid}/areas/{aid}`, `PATCH .../{aid}/estado` | Gestión CON-39 ya integrada; consulta administrativa incluye inactivas, Auditor solo lee y las mutaciones conservan historial. |
| `GET /areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD` | Arreglo de intervalos ocupados sin datos personales; se cruza con el horario del catálogo. |
| `GET /reservas` | Reservas autorizadas, no calendario general de otras unidades. |
| `POST /reservas` | UUID de condominio, área y departamento; `fecha_reserva`, `hora_inicio`, `hora_fin`. `201` tras commit, `403 DEUDA_MORA_ACTIVA`, `409 HORARIO_NO_DISPONIBLE`. |
| `POST /reservas/{reserva_id}/cancelar` | Motivo opcional, permiso desde sesión; `200` idempotente con fecha original y estado real del ajuste económico. |

La respuesta de creación es `Reserva`: `id`, `condominio_id`, `area_id`, `area_nombre` opcional, `departamento_id`, fecha, horas, `zona_horaria`, `costo_reserva`, `moneda`, `estado` y `creado_en`. Nuevas reservas usan horas `HH:MM:00` en America/Lima; las históricas sin marca local conservan interpretación UTC. Intervalos `[inicio, fin)`; cancelación voluntaria con `>= 24h` tras convertir el inicio según su zona. `es_admin` del cliente no concede privilegios. Se conservan `400 HORARIO_INVALIDO` y `409 AREA_INACTIVA` de CON-39.

### 2.6 Notificaciones — Alejandro

Contrato y reglas de entrega/reintento: [comunicaciones del Sprint 2](sprint-2-contratos.md#6-notificaciones--alejandro-persistencia-con-73). Los eventos confirmados producen avisos automáticos; las rutas de despacho/reenviar/comunicado son administrativas.

`GET /notificaciones/logs` filtra contexto y destinatario autorizado; `POST /notificaciones/despachar` y `/comunicado-masivo` confirman registros en cola con `202`; `/reenviar/{log_id}` devuelve `200` sin duplicar avisos entregados o aceptados por proveedor. `EN_COLA`, `ENVIADO`, `ENTREGADO`, `REINTENTANDO` y `FALLIDO_PERMANENTE` distinguen persistencia, aceptación y confirmación. El log identifica transporte simulado o real y conserva ciclos/intentos.

### 2.7 Módulo de Autenticación y RBAC (PROC-05)

Roles canónicos: `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`. Los tres
endpoints de autenticación usan el contrato v2 descrito en
[identidad-y-alcances.md](../02-domains/05-usuarios-rbac/identidad-y-alcances.md).
`departamentos` contiene vínculos `{departamento_id: UUID, numero, tipo_relacion,
es_activo}`. No existe una relación global de usuario; los administrativos sin
tenencia devuelven `[]`. JWT con `session_version: 2`; tokens anteriores o roles
antiguos/desconocidos reciben `401 SESION_DESACTUALIZADA` y requieren login.
El JWT incorpora además `auth_revision`, validada contra PostgreSQL. `GET /auth/demo-users` devuelve perfiles persistidos solo con `DEMO_MODE=true`; en otro caso responde `404`. La creación, estado, selección de contexto y revocación se rigen por [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md).

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
      "expires_in": 86400,
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
# Integración CON-73/74

Reservas y notificaciones adoptan los contratos de CON-72 mediante PostgreSQL;
véase [persistencia integrada](../02-domains/04-reservas/persistencia-sprint-2.md).
`POST /notificaciones/despachar` confirma cola con 202; `GET /notificaciones/logs`
admite residentes solo para sus destinatarios/unidades vigentes. Reintentar un
aviso aceptado no vuelve a enviarlo. La interfaz usa el upload real de CON-70
en dos pasos mientras su migración al multipart único de CON-72 esté pendiente.
