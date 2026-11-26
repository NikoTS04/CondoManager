# Contratos de API y Especificación OpenAPI (API Contracts)

Ampliación financiera, estado de implementación al 2026-10-25:
[prorrateo, mora diaria editable, fondos, PDF/DOCX y visor](prorrateo-mora-reportes.md).
Prevalece sobre ejemplos previos de día 20, gracia 2 o descarga exclusivamente
como adjunto. Configuración de política y excepciones, visor privado, catálogo,
presupuesto detallado versionado, aprobación con snapshot, emisión jerárquica y
reporte PDF/DOCX implementados; migración 0018 aún no aplicada a la base de la
aplicación. Mora diaria persistente y conciliación retroactiva prospectiva se
integran en 0019; fondos por edificio y cobertura de gastos se integran en 0020.
Los contratos del prorrateo se publican en OpenAPI 2.2.0 y sus fragmentos
`prorrateo.paths.yaml` / `prorrateo.schemas.yaml`; la emisión detallada publica
`CuotasEmitidasEvent` v2, manteniendo intacto el evento legacy.

Base de implementación del Sprint 2: [CON-72 — contratos por historia](sprint-2-contratos.md). La guía reúne los acuerdos y enlaza OpenAPI y eventos. El OpenAPI describe el contrato objetivo y distingue operaciones pendientes/parciales; su publicación no implica que los endpoints estén implementados.

La [convergencia implementada](../../docs/sprints/CON-72-convergencia.md) sustituye
el upload en dos pasos y el alias CONCILIADO de la primera integración. El contrato
vigente usa multipart único, APROBADO y subsanación versionada.

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

### Bandeja de excepciones (CON-66 / CON-86)

`GET /excepciones` devuelve una página con `items` y `hay_mas`. `ADMIN_JUNTA`
ve los fallos de correo de su condominio; `SUPERADMIN` también ve los
`JOB_FALLO_DEFINITIVO`, sin condominio, con componente, operación y referencia
de diagnóstico. `GET /excepciones/{id}` añade `evidencia` (origen, ciclo,
referencia de correlación y estado real del proceso), `historial`,
`acciones_permitidas` y `requiere_revision_correo`.

`POST /excepciones/{id}/resoluciones` exige `Idempotency-Key` UUID, `accion`,
`motivo` y `nuevo_destinatario` cuando la acción es `REENVIAR_CORREO`. Las
acciones son `REENVIAR_CORREO`, `REINTENTAR_JOB` (solo para procesos
idempotentes registrados en `JOBES_REINTENTABLES`) y `CERRAR_CON_MOTIVO`.
Devuelve la decisión persistida, con actor, motivo, clave, huella y el efecto
**real** sobre el proceso de origen. El detalle muestra después su resultado
vigente. Una repetición con la misma clave devuelve la decisión original sin
repetir la acción; con otra huella responde 409. La API devuelve 404 para
casos fuera de alcance y 409 si la acción ya no procede.

### Registro de incidencias (CON-53)

`POST /incidencias` admite multipart con `departamento_id`, `ubicacion`,
`categoria`, `descripcion`, `urgencia` y una `evidencia` opcional. Exige una
sesión de residente con vínculo activo y `Idempotency-Key` UUID. Devuelve 201
con el reporte `REGISTRADO` y 200 al repetir los mismos datos con la misma clave.
Reutilizar la clave con otros datos devuelve 409. Una foto PNG o JPEG inválida o
que exceda 3 MiB se descarta y la respuesta informa `advertencia_evidencia`.
`GET /incidencias/{incidencia_id}` y su subruta `/evidencia` exigen que el
solicitante sea el reportante con vínculo activo o Junta del mismo condominio.
Los reportes fuera de alcance devuelven 404. [OpenAPI de incidencias](../03-contracts/openapi/incidencias.paths.yaml).

`GET /incidencias/mis-reportes?offset=0&limit=25` devuelve `items` y
`hay_mas`. Solo se admiten residentes. La página se ordena por fecha de
creación descendente y contiene únicamente reportes del usuario en el
condominio activo y en sus unidades con vínculo activo. Cada elemento
incluye el estado y el motivo de rechazo vigentes.

### Clasificación de incidencias (CON-54)

`GET /incidencias?offset=0&limit=25` lista tickets del condominio de Junta.
Devuelve `items` y `hay_mas`. Ordena primero los tickets urgentes pendientes,
luego los demás pendientes y por último los rechazados, con los más recientes
primero dentro de cada grupo.
`PATCH /incidencias/{incidencia_id}/revision` requiere `ADMIN_JUNTA` y recibe
`accion`, `version` y los datos de la acción. `CLASIFICAR` recibe `categoria`
y `prioridad`. `RECHAZAR` recibe `motivo` obligatorio. Una versión
desactualizada o un estado distinto de `REGISTRADO` devuelve 409. El reporte
original conserva la categoría y urgencia que declaró el residente. El detalle
incluye la categoría confirmada, la prioridad, el motivo de rechazo y la versión.
Reenviar el reporte de CON-53 devuelve el comprobante original de registro.

### Seguimiento y resolución de incidencias (CON-56)

- `POST /incidencias/{incidencia_id}/seguimiento` (`ADMIN_JUNTA` del condominio,
  multipart): `version`, `comentario` (1–2000), `publico` (por defecto `true`),
  `repuesto` opcional y `monto` decimal opcional (`NUMERIC(12,2)`, sin `float`),
  además de una `evidencia` JPEG/PNG de hasta 3 MiB. Guarda la actualización y, si
  el ticket estaba `ASIGNADO`, lo pasa a `EN_PROCESO`. Un archivo inválido se
  descarta con advertencia y el avance se conserva. Devuelve `201` y el DTO del
  ticket.
- `POST /incidencias/{incidencia_id}/resolucion` (`ADMIN_JUNTA`, multipart):
  `version`, `descripcion` (1–2000) y los mismos campos opcionales de costo y
  evidencia. Solo aplica desde `EN_PROCESO`; en otro estado responde `409`.
  Pasa el ticket a `RESUELTO`. El proveedor no puede invocar ninguna de estas
  rutas.
- `GET /incidencias/{incidencia_id}/historial`: Junta y Auditor del condominio
  ven todas las actualizaciones, incluidos costos y sustentos; el residente ve
  solo las marcadas `publico: true` de su propio reporte. Devuelve `items` y
  `hay_mas` paginados. Otro condominio recibe `404`.
- `GET /incidencias/{incidencia_id}/actualizaciones/{actualizacion_id}/evidencia`:
  bytes privados, `private, no-store`, `nosniff`; mismo alcance que el historial.
- Cada cambio de estado registra en la misma transacción la auditoría de siete
  campos con actor, motivo, estado anterior y estado posterior.

### Confirmación y cierre de incidencias (CON-57)

- `POST /incidencias/{incidencia_id}/confirmacion` (`RESIDENTE` con vínculo activo
  sobre su reporte): `version` y `calificacion` entera entre 1 y 5, con
  `comentario` opcional. Solo desde `RESUELTO`; pasa a `CERRADO`, guarda fecha y
  actor de cierre y registra `CIERRE_CONFORME_TICKET` con auditoría de siete
  campos. Otro condominio o reporte ajeno responde 404; versión desactualizada o
  estado distinto responde 409; calificación fuera de rango responde 422.
- `POST /incidencias/{incidencia_id}/reapertura` (`RESIDENTE`): `version` y
  `motivo` obligatorio. Solo desde `RESUELTO`; vuelve a `EN_PROCESO`, conserva el
  motivo y audita `REAPERTURA_TICKET_INCIDENCIA`.
- `POST /incidencias/{incidencia_id}/cierre-administrativo` (`ADMIN_JUNTA` del
  condominio): `version` y `motivo` obligatorio. Solo desde `RESUELTO`; pasa a
  `CERRADO` y audita `CIERRE_ADMINISTRATIVO_TICKET`. Ninguna ruta permite que un
  proveedor cierre el ticket.
- Las tres rutas devuelven la incidencia vigente con `Cache-Control: private, no-store`.

### Avisos de bloqueos e incidencias (contrato del Sprint 4)

El contrato de CON-55 está implementado; el de CON-47 sigue siendo objetivo
hasta que Brandon actualice OpenAPI. Eventos y claves:
[catálogo](../03-contracts/events/domain-events-catalog.md).

- `POST /incidencias/{incidencia_id}/asignacion` (CON-55; `ADMIN_JUNTA` del
  condominio). Cuerpo con `version`, uno de `responsable_usuario_id` o
  `responsable_proveedor_id` (con `proveedor_nombre` y `correo_proveedor` cuando
  aplica), `plazo` futuro y `nota` opcional. Header `Idempotency-Key` UUID.
  Devuelve la incidencia en `ASIGNADO`, con `asignacion_id` y `avisos_encolados`.
  Repetir la clave con los mismos datos devuelve la asignación original (200);
  con otros datos responde 409. Un responsable inactivo o ajeno responde 403 y
  una versión desactualizada o un estado no asignable responde 409.
- `GET /incidencias/{incidencia_id}/avisos` (CON-55; `ADMIN_JUNTA` del condominio,
  Auditor solo lectura; Residente 403; otro condominio 404). Devuelve `items` con
  `asignacion_id`, `destinatario_tipo` (`RESIDENTE` | `PROVEEDOR`), `estado` y, si
  existe, `aviso_id`, `intentos`, `fecha_actualizacion` y `alerta_abierta`.
- `GET /condominios/{cid}/areas/{aid}/bloqueos/{bid}/avisos` (CON-47; mismos
  permisos). Devuelve `reservas_canceladas`, `avisos_por_estado` y `items` por reserva.
- `estado` es el de `notificaciones_logs` (`EN_COLA`, `ENVIADO`, `ENTREGADO`,
  `REINTENTANDO`, `FALLIDO_PERMANENTE`, `OMITIDO`) o `CONTACTO_FALTANTE`, derivado
  cuando no hay correo utilizable. No expone correos ni contenido del mensaje.
- Reintentar una confirmación no cambia los totales ni duplica avisos.

### CON-81 — disponibilidad del despliegue

GET `/health` y `/api/v1/health` conservan su respuesta de liveness HTTP.
GET `/ready` y `/api/v1/ready` son públicos, de solo lectura, sin caché:
devuelven 200 con `status: "ok"`, `database: "ok"` y `schema_revision` (lista
ordenada de revisiones instaladas) únicamente si PostgreSQL responde y coincide
con la única cabeza de migraciones del artefacto desplegado. El chequeo también
verifica la presencia de las tablas/columnas mapeadas requeridas por la API.
Con fallo, timeout (5 segundos) o esquema incompleto devuelven 503 con
`error_code: "SERVICIO_NO_DISPONIBLE"` y mensaje genérico, nunca DSN, host,
credenciales ni excepción SQL. Readiness no certifica entrega de correo ni avance
de workers: esas evidencias requieren los recorridos del runbook.

### Fondos de moras cobradas (0020)

GET `/edificios/{id}/fondos-moras?periodo=YYYY-MM` entrega saldos, resumen mensual
y movimientos privados de caja reconocida en Lima. Solo administración/auditor
del contexto. GET `/presupuestos/{id}/aplicaciones-moras` lista coberturas.
POST exige `Idempotency-Key`, `version_esperada`, `item_id`, `edificio_id`, `monto`
como cadena positiva y `motivo`. Misma clave/payload devuelve la aplicación
original; otro payload, versión obsoleta o saldo insuficiente: 409. DELETE
`/presupuestos/{id}/aplicaciones-moras/{aplicacion_id}?version_esperada=N` libera
solo una reserva; repetir liberación es no-op. Confirmadas no se eliminan.
Reservar/liberar incrementa versión y recalcula monto_total/coverage por servidor.
PUT valida la cobertura contra reservas existentes, no acepta coberturas ficticias.
409 FONDOS_MORAS_COMPROMETIDOS bloquea un retroactivo sin financiación suficiente.
Ledger, auditoría, presupuesto y eventos FondosMorasActualizadosEvent v1 se
confirman juntos. No se importa efectivo histórico ni se crean egresos bancarios
por aplicar una cobertura. Los reportes aprobados siguen siendo inmutables.

### Mora diaria y conciliación bancaria (0019)

Nuevas emisiones MONTO_DIARIO habilitadas con snapshot, devengos persistentes y
reconstrucción de pagos nuevos en orden `(fecha_operacion, comprobante_id)`.
No hay endpoint público para ejecutar el cron ni recibir importes de mora del
cliente. Aprobación valida la fecha bancaria ya reportada (no futura) y conserva
el request de conciliación. 422 `FECHA_BANCARIA_FUTURA` si es posterior a hoy en
Lima; 409 `CREDITO_RETROACTIVO_CONSUMIDO` si la reconstrucción requiere saldo ya
utilizado. Todo se revierte ante error. Recibos, resultados idempotentes de
revisión e imputaciones originales se conservan; las correcciones posteriores
constan en ledger por componente y auditoría. No se reconstruyen pagos históricos
anteriores a esta adopción ni se convierten cuotas legacy a políticas actuales.
MoraAplicadaEvent y MoraAjustadaEvent v2 usan outbox independiente y consumidor
compatible; 0020 integra el fondo de cobros y las reservas sin caja histórica.

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
      "regla_mora_tipo": "MONTO_DIARIO",
      "monto_mora_diario": "1.00",
      "monto_mora_fijo": null,
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 10,
      "dias_gracia": 0
    }
    ```
  - *Reglas condicionales:*
    - `MONTO_DIARIO` (objetivo predeterminado): monto diario positivo editable,
      default 1.00 PEN, demás campos de mora nulos. Día 10 y gracia 0 por defecto.
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
      "regla_mora_tipo": "MONTO_DIARIO",
      "monto_mora_diario": "1.00",
      "monto_mora_fijo": null,
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 10,
      "dias_gracia": 0,
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
      "fecha_vencimiento": "2026-10-10"
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
      "fecha_vencimiento": "2026-10-10"
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
      "fecha_vencimiento": "2026-10-10",
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
      "fecha_vencimiento": "2026-10-10"
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

### CON-51 y CON-52 — Egresos, aprobaciones, pagos y caja

**Estado:** contrato objetivo; CON-51 registro/consulta/edición y sustento `SUSTENTO` parcialmente implementados en la rama de CON-51/52. Presentación, aprobación, pagos, caja y CON-52 siguen pendientes. Dominio: [DOM-06](../02-domains/06-egresos-proveedores/spec.md).
OpenAPI: [egresos.paths.yaml](../03-contracts/openapi/egresos.paths.yaml) y
[egresos.schemas.yaml](../03-contracts/openapi/egresos.schemas.yaml). El contrato de
integración con CON-48/49 está en
[docs/sprints/CON-48-49-51-52-integracion.md](../../docs/sprints/CON-48-49-51-52-integracion.md).

#### Reglas comunes

- Todas las rutas requieren JWT. `ADMIN_JUNTA` opera en su condominio;
  `SUPERADMIN` en el contexto autorizado/seleccionado. `AUDITOR` puede consultar,
  pero no mutar. `RESIDENTE` no accede al módulo.
- Todas las mutaciones derivan actor/contexto del JWT, validan pertenencia real
  del recurso y escriben auditoría en la misma transacción.
- Dinero en request/response como cadena `0.00`, moneda `PEN|USD`, persistencia
  `NUMERIC(12,2)`/`Decimal`. No aceptar `float`, exponentes ni más de dos decimales.
- `concepto_id` debe ser un `ConceptoPresupuestal` activo del condominio.
  `proveedor_id` y `contrato_id` son UUID nullable. Si se proporcionan, servicio
  valida contexto y relación proveedor-contrato. Antes de integrar CON-48/49 no
  existe FK física; se agregará después mediante migración sobre la cabeza Alembic
  vigente, nunca con tabla placeholder o revisión paralela.
- En esta entrega, el módulo de proveedores no está integrado: los gastos sin
  proveedor/contrato son válidos; referencias UUID no nulas responden
  `409 PROVEEDOR_NO_DISPONIBLE`. La política no crea datos simulados.
- Crear/editar borradores no necesita política de aprobación ni apertura de caja.
  Presentar requiere política configurada. Confirmar pago requiere apertura de
  caja conciliada y saldo suficiente.
- El umbral no tiene valor predeterminado. La política inicial prohíbe
  autoaprobación, requiere una aprobación por debajo/igual al umbral y dos
  aprobaciones de personas distintas por encima. Cambio de monto crea versión y
  las aprobaciones previas dejan de autorizarla. Roles actuales: `ADMIN_JUNTA`,
  `SUPERADMIN`, `AUDITOR`; no se crea rol nuevo.
- Pagos parciales soportados por modelo, deshabilitados por defecto. Deshabilitados,
  solo se confirma el total pendiente; habilitados, la suma no excede el monto
  aprobado vigente. La habilitación la debe ratificar Tesorería.

#### Egresos

| Método y ruta | Permiso | Entrada / resultado |
|---|---|---|
| `GET /condominios/{condominio_id}/egresos` | Junta/Auditor contexto | Filtros `fecha_desde`, `fecha_hasta`, `estado`, `proveedor_id`, `concepto_id`, `offset`, `limit`; lista paginada. |
| `POST /condominios/{condominio_id}/egresos` | Junta escritura | JSON con concepto, descripción, justificación, importe solicitado, moneda, fecha del gasto y referencias opcionales; `201 BORRADOR`. No crea pago ni salida de caja. |
| `GET /condominios/{condominio_id}/egresos/{egreso_id}` | Junta/Auditor contexto | Detalle, estado, versión, proveedor (campos de lectura), documentos, aprobaciones, pagos e historial. |
| `PATCH /condominios/{condominio_id}/egresos/{egreso_id}` | Junta escritura | Solo `BORRADOR`, `version_esperada` obligatoria; `200`. Cambio de importe incrementa versión. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/documentos` | Junta escritura | Multipart `archivo`, `tipo`; CON-51 acepta `SUSTENTO` en egreso `BORRADOR`; `EVIDENCIA_PAGO` queda para CON-52. `201` con metadatos y UUID, no URL pública. |
| `GET /condominios/{condominio_id}/egresos/{egreso_id}/documentos/{documento_id}` | Junta/Auditor contexto | Contenido inline privado, `Cache-Control: no-store`. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/presentar` | Junta escritura | `{version_esperada}`; exige sustento y política configurada; `200 PENDIENTE_APROBACION`. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/aprobaciones` | Junta escritura | `{decision: APROBAR|RECHAZAR, version_esperada, motivo?}`; rechazo requiere motivo; `200` historial/estado resultante. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/cancelar` | Junta escritura | `{version_esperada, motivo}`; solo sin pagos confirmados; `200 CANCELADO`. |

El request de creación acepta `concepto_id`, `proveedor_id?`, `contrato_id?`,
`presupuesto_id?`, `item_presupuesto_id?`, `descripcion`, `justificacion`,
`moneda`, `fecha_gasto`, `monto_solicitado` y `monto_pactado?`. `monto_pactado`
expresa la obligación acordada antes de un eventual incremento; ambos importes
deben ser positivos y el monto solicitado es el objeto de aprobación. Las claves
`presupuesto_id`/`item_presupuesto_id` son ambas nulas o ambas presentes y solo
vinculan el gasto presupuestado: no alteran ni el snapshot aprobado ni caja.

#### Aprobación

`GET /condominios/{condominio_id}/egresos/configuracion-aprobacion` devuelve
`umbral: string|null`, `version`, `pagos_parciales_habilitados` y estado de
configuración. Si aún no hay umbral, no se inventa uno: presentación/aprobación
responde `409 APROBACION_CONFIGURACION_REQUERIDA`.

`PUT` sobre la misma ruta configura `umbral` explícito, `pagos_parciales_habilitados`
(inicialmente `false`) y `version_esperada`; requiere rol administrativo existente,
contexto y auditoría. La asignación final de administración de esta política debe
ratificarse con Tesorería. No hay rol adicional.

Un registrador no puede aprobar su egreso (`403 REGISTRADOR_NO_PUEDE_APROBAR`).
La decisión se vincula a versión e importe. La aprobación única requerida hasta
el umbral deja estado `APROBADO`; sobre el umbral, la primera mantiene
`PENDIENTE_APROBACION` y la siguiente, de otro actor, habilita `APROBADO`.
Rechazar conserva actor, motivo, importe y versión. Una aprobación repetida por el
mismo actor/versión responde `409 APROBACION_DUPLICADA`.

#### Pagos y caja

| Método y ruta | Permiso | Entrada / resultado |
|---|---|---|
| `GET /condominios/{condominio_id}/caja` | Junta/Auditor contexto | Cuentas, moneda, saldo derivado y movimientos paginados. |
| `POST /condominios/{condominio_id}/caja/documentos` | Junta escritura | Multipart con evidencia privada de apertura; devuelve `documento_id`, sin URL pública. |
| `GET /condominios/{condominio_id}/caja/documentos/{documento_id}` | Junta/Auditor contexto | Lectura privada inline de evidencia de apertura. |
| `POST /condominios/{condominio_id}/caja/aperturas` | Junta escritura con permiso vigente | Alias/referencia no sensible de cuenta, saldo conciliado, moneda, fecha de corte, referencia de conciliación y `documento_id` de sustento; requiere `Idempotency-Key`; `201`. Sin apertura previa para esa cuenta. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/pagos` | Junta escritura | `Idempotency-Key`; cuenta, monto, fecha real, referencia bancaria y `documento_id` tipo `EVIDENCIA_PAGO`; `201` confirmado y movimiento único. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/pagos/intentos-fallidos` | Junta escritura | `Idempotency-Key`; cuenta, monto, fecha, referencia, motivo y evidencia opcional; conserva `FALLIDO` sin movimiento de caja. |
| `POST /condominios/{condominio_id}/egresos/{egreso_id}/pagos/{pago_id}/reversos` | Junta escritura con permiso vigente | `Idempotency-Key` y motivo; inserta reverso compensatorio y conserva el pago original. |

La evidencia se carga primero al egreso como `EVIDENCIA_PAGO`; la confirmación
referencia su UUID. El archivo debe pertenecer al mismo egreso y no estar ya
consumido. Pago confirmado, movimiento de caja y auditoría son una sola
transacción. Un intento bancario fallido se conserva mediante la ruta de intento
fallido, sin movimiento de caja. La salida se reconoce al confirmar en sistema con fecha local
Lima; la fecha bancaria se conserva aparte. Un reverso restaura el saldo pagable
neto (confirmados menos reversados) sin exceder el monto aprobado y recalcula el
estado del egreso; no elimina el movimiento original.

**Implementación CON-51 (parcial):** los endpoints de alta, listado/filtrado,
detalle, edición de borrador y sustento privado están registrados por FastAPI.
El sustento reutiliza el adapter de storage privado y la validación binaria
existentes (PDF/JPEG/PNG, `VOUCHER_MAX_BYTES`); el DTO nunca expone la clave de
storage. Solo se acepta `SUSTENTO`; la evidencia de pago depende de CON-52.
El `POST` crea únicamente `BORRADOR` y persiste auditoría con el gasto. Presentar
el egreso y cualquier mutación de caja no se declaran implementados por esta entrega.

#### Estados

- Egreso: `BORRADOR`, `PENDIENTE_APROBACION`, `APROBADO`, `RECHAZADO`,
  `PAGO_PARCIAL`, `PAGADO`, `CANCELADO`.
- Presentar: BORRADOR → PENDIENTE_APROBACION. Aprobar solo llega a APROBADO
  cuando cumple la política. Rechazar pasa a RECHAZADO. Corrección de rechazado
  retorna a BORRADOR en nueva versión; historial no se borra.
- Confirmar un pago mueve APROBADO → PAGO_PARCIAL o PAGADO según saldo y política.
  Cancelar solo es posible antes de pagos confirmados. Un pago efectuado no se
  cancela borrando: se revierte mediante compensación.
- Pago: `CONFIRMADO`, `FALLIDO`, `REVERSADO`. Solo CONFIRMADO afecta caja;
  REVERSADO requiere movimiento compensatorio.
- Caja: libro inmutable independiente de `movimientos_fondo_moras`. No hay
  saldo inicial automático. Sin apertura conciliada responde
  `409 CAJA_NO_CONFIGURADA`; sin saldo responde `409 CAJA_SALDO_INSUFICIENTE`.

Errores comunes: `401 NO_AUTENTICADO`, `403 ACCESO_DENEGADO`/`REGISTRADOR_NO_PUEDE_APROBAR`,
`404 EGRESO_NO_ENCONTRADO` (incluye recurso fuera de contexto), `409`
`EGRESO_VERSION_OBSOLETA`, `EGRESO_ESTADO_INVALIDO`,
`APROBACION_CONFIGURACION_REQUERIDA`, `APROBACION_DUPLICADA`,
`IDEMPOTENCIA_CONFLICTO`, `CAJA_NO_CONFIGURADA`, `CAJA_SALDO_INSUFICIENTE`,
`PAGO_EXCEDE_APROBADO`, `PAGO_YA_REVERSADO`, `422 DATOS_EGRESO_INVALIDOS`,
`413 ARCHIVO_DEMASIADO_GRANDE`, `415 FORMATO_NO_SOPORTADO`, `503 ALMACENAMIENTO_NO_DISPONIBLE`.
Errores monetarios y de transacción nunca exponen datos de otros condominios.

En el incremento CON-51 se usan además `409 PROVEEDOR_NO_DISPONIBLE` mientras
CON-48/49 no esté integrado, `409 EGRESO_CONFLICTO_CONCURRENCIA`,
`409 EGRESO_NO_EDITABLE`, `422 CONCEPTO_PRESUPUESTAL_NO_DISPONIBLE`,
`422 ITEM_PRESUPUESTAL_NO_COINCIDE` y `422 FILTRO_FECHAS_INVALIDO`.
`409 CON52_NO_DISPONIBLE` identifica el envío de `EVIDENCIA_PAGO` hasta que se
implemente su flujo en CON-52.

La respuesta de creación es `Reserva`: `id`, `condominio_id`, `area_id`, `area_nombre` opcional, `departamento_id`, fecha, horas, `zona_horaria`, `costo_reserva`, `moneda`, `estado` y `creado_en`. Nuevas reservas usan horas `HH:MM:00` en America/Lima; las históricas sin marca local conservan interpretación UTC. Intervalos `[inicio, fin)`; cancelación voluntaria con `>= 24h` tras convertir el inicio según su zona. `es_admin` del cliente no concede privilegios. Se conservan `400 HORARIO_INVALIDO` y `409 AREA_INACTIVA` de CON-39.

### 2.6 Notificaciones — Alejandro

Contrato y reglas de entrega/reintento: [comunicaciones del Sprint 2](sprint-2-contratos.md#6-notificaciones--alejandro-persistencia-con-73). Los eventos confirmados producen avisos automáticos; las rutas de despacho/reenviar/comunicado son administrativas.

`GET /notificaciones/logs` filtra contexto y destinatario autorizado; `POST /notificaciones/despachar` y `/comunicado-masivo` confirman registros en cola con `202`; `/reenviar/{log_id}` devuelve `200` sin duplicar avisos entregados o aceptados por proveedor. `EN_COLA`, `ENVIADO`, `ENTREGADO`, `REINTENTANDO` y `FALLIDO_PERMANENTE` distinguen persistencia, aceptación y confirmación. El log identifica transporte simulado o real y conserva ciclos/intentos.

#### Alertas de contratos (CON-50)

No expone endpoints nuevos: la revisión corre dentro de `GET /jobs/diario` y no cambia su
respuesta. La consulta de avisos para el panel de Junta queda pendiente de definir con CON-49.
Contrato interno: [alertas de contratos](../02-domains/06-egresos-proveedores/alertas-contratos.md).

### 2.7 Módulo de Autenticación y RBAC (PROC-05)

Roles canónicos: `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`. Los tres
endpoints de autenticación usan el contrato v2 descrito en
[identidad-y-alcances.md](../02-domains/05-usuarios-rbac/identidad-y-alcances.md).
`departamentos` contiene vínculos `{departamento_id: UUID, numero, tipo_relacion,
es_activo}`. No existe una relación global de usuario; los administrativos sin
tenencia devuelven `[]`. JWT con `session_version: 2`; tokens anteriores o roles
antiguos/desconocidos reciben `401 SESION_DESACTUALIZADA` y requieren login.
El JWT incorpora además `auth_revision`, validada contra PostgreSQL. `GET /auth/demo-users` devuelve perfiles persistidos solo con `DEMO_MODE=true`; en otro caso responde `404`. La creación, estado, selección de contexto y revocación se rigen por [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md).

CON-76 añade [invitación, activación y relevo](../02-domains/05-usuarios-rbac/invitacion-y-relevo.md).
La duración de sesión se configura en minutos y `expires_in` expresa esos mismos
minutos en segundos; el ejemplo usa el valor predeterminado de 60 minutos.

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
# Integración CON-73/74

Reservas y notificaciones adoptan los contratos de CON-72 mediante PostgreSQL;
véase [persistencia integrada](../02-domains/04-reservas/persistencia-sprint-2.md).
`POST /notificaciones/despachar` confirma cola con 202; `GET /notificaciones/logs`
admite residentes solo para sus destinatarios/unidades vigentes. Reintentar un
aviso aceptado no vuelve a enviarlo. La interfaz usa el upload real de CON-70
en dos pasos mientras su migración al multipart único de CON-72 esté pendiente.
# Convergencia CON-72

La adopción coordinada usa [sprint-2-contratos.md](sprint-2-contratos.md): multipart
en `/pagos/reportar`, subsanación en `PUT /pagos/{id}/voucher`, estado APROBADO,
campo codigo en recepción, motivo_rechazo en resultados y descarga autenticada.
Se retira `/pagos/vouchers` y el reporte JSON con url_voucher: los consumidores
del repositorio cambian conjuntamente. Clientes externos requieren actualización
antes del despliegue. El endpoint existente de resultado sigue disponible y
devuelve únicamente la revisión de la evidencia vigente. No hay doble publicación:
productores canónicos y lector compatible con eventos históricos persistidos.
## CON-14 — Estado de cuenta

Contrato y criterios de lectura: [estado de cuenta por unidad y periodo](estado-de-cuenta.md).
# Incremento compatible — 18/11/2026

- `GET /pagos/comprobantes`: mantiene respuesta array. Filtros opcionales
  `fecha_desde`, `fecha_hasta` (fecha bancaria ISO inclusiva), `departamento_id` (UUID),
  `banco` (exacto, insensible a mayúsculas, 1–30 caracteres), `estado`
  (EN_REVISION/APROBADO/OBSERVADO/RECHAZADO), `limit` (1–100, default 50) y `offset` (>=0).
  Se conserva el contrato CON-24 de main. Respuesta privada sin caché.
- `GET /health/ready` (también bajo `/api/v1`): 200 solo si PostgreSQL (`SELECT 1`)
  y Redis (`PING`) responden en hasta dos segundos por dependencia; 503 en otro
  caso. Expone únicamente `status` y estados `ok`/`error` por dependencia, nunca
  credenciales ni excepciones. No prueba workers, entrega de correo o almacenamiento.
  `/health` conserva su función compatible de liveness.
# Consolidación SQL y retiro explícito — 18/11/2026

Reservas conserva rutas y DTO: ahora su única fuente es PostgreSQL, sin adopción
piloto. El historial, disponibilidad, creación y cancelación devuelven 503 ante
fallos del esquema requerido. No migran datos que existan únicamente en memoria.
`POST /moras/evaluar` queda deprecado: devuelve 410
`EVALUACION_MANUAL_RETIRADA` a administradores autorizados. Conserva 401/403/422
para errores de sesión, alcance o cuerpo. El worker diario SQL no cambia.
# Perfil Hobby

Ver [contrato Hobby y Supabase](vercel-hobby.md). Añade endpoint interno diario;
los DTO de pagos no cambian. Límite de subida configurable: 3 MiB en ese perfil.
# Bloqueos preventivos

`GET/POST /condominios/{cid}/areas/{aid}/bloqueos`, `DELETE .../bloqueos/{bid}`.
POST: inicio/fin ISO con zona, motivo (1–500); 201. DELETE: liberación lógica,
200 repetible. GET: lista de los últimos 100 bloqueos, incluidos inactivos.
Junta/SuperAdmin escriben; Auditor consulta, residentes usan disponibilidad anónima
de ocupaciones. 409 si POST afecta reservas confirmadas; no cancela operaciones.
# Services y Mailjet

Contrato de rutas internas, binding y adapter desactivado:
[vercel-services-mailjet.md](vercel-services-mailjet.md).
# Extensión PROC-03: correo productivo

Selección de audiencia, confirmación, operación y políticas:
[cierre EMAIL](notificaciones-completas.md). Requiere esquema 0022.

Contrato de job Supabase Cron y callback autenticado Mailjet:
[Mailjet productivo](vercel-services-mailjet.md). OpenAPI:
[`mailjet.paths.yaml`](../03-contracts/openapi/mailjet.paths.yaml).
La API de despacho conserva 202: confirma persistencia en cola, no recepción.
# CON-68 — Salud y alertas visibles

`GET /api/v1/monitoreo/salud` (solo SUPERADMIN): estado de `api`, `postgresql`, `redis` y
`correo` según el perfil (`ok`/`error`/`deshabilitado`) y último inicio, fin, duración y
resultado de cada job. Siempre 200; nunca expone URLs ni credenciales. Sin caché.
`GET /api/v1/monitoreo/alertas` (SUPERADMIN, ADMIN_JUNTA, AUDITOR): alertas con `componente`,
`operacion` y `referencia_diagnostico`; las de job solo las ve SUPERADMIN. `limit`, `offset`,
`estado`, `condominio_id`. Detalle: [notificaciones §9](../02-domains/03-notificaciones/spec.md)
y [`monitoreo.paths.yaml`](../03-contracts/openapi/monitoreo.paths.yaml).
# Incremento PROC-07: reparto por costo y pago dirigido

- `POST /incidencias/{iid}/costos/{actualizacion_id}/reparto/previsualizacion`:
  Junta del condominio; JSON `{alcance: TODOS|SELECCIONADOS,
  metodo: EQUITATIVA|POR_ALICUOTA, departamento_ids: UUID[], concepto, motivo}`.
  Responde monto decimal textual, departamentos con coeficiente/importe y `huella`.
- `POST /incidencias/{iid}/costos/{actualizacion_id}/reparto`:
  mismos datos más `huella`; exige `Idempotency-Key` UUID. 201 creado/200 repetido;
  409 huella obsoleta, clave reutilizada o costo ya publicado; 403 fuera de contexto.
- `GET /incidencias/{iid}/costos/{actualizacion_id}/reparto`: Junta; instantánea publicada.
- `GET /pagos/cargos-incidencias?departamento_id=UUID`: unidad autorizada; lista de
  cargos con concepto público, incidencia de origen, monto, pagado, pendiente y estado.
- `POST /pagos/reportar`: añade `cargos_incidencia_ids` opcional (lista multipart de
  UUID, máximo 100, sin duplicados). Vacía mantiene el flujo de cuotas sin cambios.
  No vacía exige suma exacta de saldos pendientes seleccionados, de una sola unidad.
  Reutilizar el mismo comprobante con otros destinos devuelve 409.
- Listado de comprobantes incluye `cargos_incidencia_ids`. Conciliar conserva el
  contrato y devuelve el monto aplicado real. Pagos dirigidos quedan fuera del motor
  de cuotas y no generan crédito. La cuenta integra cargo y pago sin doble cómputo.
- Asignación acepta el identificador real del proveedor; nombre/correo enviados por
  clientes antiguos se admiten por compatibilidad pero se resuelven desde el directorio.
- Importes viajan como cadenas de dos decimales; lecturas privadas `no-store`.
