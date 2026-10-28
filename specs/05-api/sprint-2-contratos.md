# CON-72 — Contratos base de implementación del Sprint 2

Ampliación financiera: [prorrateo, mora diaria y reportes](prorrateo-mora-reportes.md).
El contrato evoluciona a 2.4.0; MONTO_DIARIO, defaults/excepciones, fondos por
edificio, PDF/DOCX y visor/historial se implementan prospectivamente en 0016–0020.
La evidencia de estas entregas es independiente de CON-72/73/74 y no acredita
despliegue, adopción de caja histórica ni modificación de cuotas aprobadas.

**Responsable:** Gerardo. **Base:** 20/10/2026. **Estado:** implementación integrada y verificación local por CON-73/74; revisión de pares y esquema desplegado pendientes. Evidencia en [convergencia CON-72](../../docs/sprints/CON-72-convergencia.md). Los contratos pueden evolucionar mediante el procedimiento de cambios de la sección 9.

## 1. Fuentes y alcance

| Artefacto | Uso |
|---|---|
| [condomanager.openapi.yaml](../03-contracts/openapi/condomanager.openapi.yaml) | Entrada del contrato HTTP, versión 2.4.0; incluye ampliación financiera prospectiva. |
| [sprint-2.paths.yaml](../03-contracts/openapi/sprint-2.paths.yaml) | Operaciones por HU, estados HTTP, permisos y marcas de implementación pendiente/parcial. |
| [sprint-2.schemas.yaml](../03-contracts/openapi/sprint-2.schemas.yaml) | Formas de entrada/salida y tipos compartidos. |
| [Catálogo de eventos](../03-contracts/events/domain-events-catalog.md) | Productores, consumidores, versiones, esquemas y recuperación. |

CON-72 define las interfaces compartidas del sprint. La convergencia integrada incorpora su adopción en routers, DTO Python, tipos TypeScript, repositorios y migraciones, con la evidencia enlazada arriba. La mera definición de un endpoint en OpenAPI o un almacén piloto en memoria no acredita una integración persistente; las futuras modificaciones conservan esta exigencia.

CON-04/05/06/39 conservan las interfaces ya integradas en `develop`: alta administrativa, vínculos persistentes, una asignación de rol por usuario y condominio y catálogo SQL de áreas. Sus rutas y esquemas permanecen en el OpenAPI principal; los fragmentos del sprint no los duplican.

Para los contratos del Sprint 2 se usan los artefactos de esta tabla. Cada responsable alinea los documentos de dominio, proceso y persistencia afectados en el PR que implemente su HU; esas actualizaciones generales quedan fuera de esta entrega.

## 2. Convenciones comunes

- HTTP REST con JSON, excepto subida multipart y descarga binaria de vouchers. No se exige el formato JSON:API. Prefijo `/api/v1`, identificadores UUID y cuerpos con campos adicionales rechazados, salvo mapas expresamente abiertos.
- Importes de respuestas, eventos y nuevos contratos como cadenas de dos posiciones, sin notación exponencial y dentro de `NUMERIC(12,2)`. La configuración de áreas CON-39 conserva su entrada decimal como cadena con hasta dos decimales y salida normalizada a dos. Se rechaza precisión adicional; los cálculos usan `Decimal`. La moneda se hereda del condominio (PEN/USD); el cliente no elige otra para una reserva o comprobante.
- Calendario en `America/Lima`. Fechas `YYYY-MM-DD`; apertura/cierre del catálogo en `HH:MM` y horas de nuevas reservas en `HH:MM:00`, con precisión de minuto. No se cruza medianoche: dividir usos de distintos días en operaciones separadas. Intervalos semiabiertos `[inicio, fin)`; dos intervalos contiguos no se solapan.
- CON-39 conserva la interpretación UTC de reservas históricas sin marca de zona. No reinterpretarlas como horas de Lima; CON-73 preserva sus instantes y CON-40 convierte al calendario local al consultar ocupaciones. Las reservas nuevas guardan su zona y moneda junto con la tarifa confirmada.
- Instantes de auditoría, confirmación, cancelación y eventos en UTC, con `Z` u offset `+00:00`. Para aplicar 24 horas se convierte fecha/hora local del inicio a un instante; nunca asignar UTC directamente a una hora de Lima.
- El calendario local no modifica la planificación UTC ya implementada por el worker de cuotas de CON-11; cualquier cambio de ese cron se acuerda en su propia historia.
- Bearer obligatorio salvo login, salud y demo según su contrato. `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE` son los únicos roles; propietario, copropietario e inquilino son relaciones por departamento.
- Toda escritura valida rol, condominio y recurso. El residente opera exclusivamente con sus vínculos activos; `AUDITOR` no escribe. Los filtros nunca amplían el permiso. Un SuperAdmin global selecciona contexto para las consultas que lo necesitan.
- Cuando una operación produce eventos, confirmar la operación, auditoría y evento pendiente en una transacción antes de responder éxito. Una reversión no modifica saldos, horarios ni notificaciones de éxito.
- Error en raíz: `error_code`, `mensaje`, `detalles` opcional como objeto. Las validaciones se agrupan en `detalles.errores`, sin reproducir contraseñas, tokens o contenido de archivos. Durante la adopción el lector frontend conserva compatibilidad con `detail` histórico; los nuevos handlers usan el formato raíz.

## 3. Usuarios y accesos — Jerson

CON-04 conserva [alta-administrativa.md](../02-domains/05-usuarios-rbac/alta-administrativa.md): cuenta inactiva por defecto, contraseña inicial del administrador, habilitación manual exclusiva de SuperAdmin, login SQL y `auth_revision`. La invitación por correo queda fuera de este sprint.

### CON-05: vínculos

Se conserva el [contrato de vínculos integrado](../02-domains/05-usuarios-rbac/vinculos-departamentos.md). Familia `/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos`:

- `GET`: SuperAdmin o Junta autorizada consultan vínculos activos e inactivos del contexto. Auditor y Residente no acceden a esta gestión administrativa.
- `PUT .../{departamento_id}` recibe solo `tipo_relacion` (`PROPIETARIO_TITULAR`, `COPROPIETARIO` o `INQUILINO`); crea, cambia o restaura el vínculo y responde `200 VinculoUsuario`.
- `DELETE .../{departamento_id}` desactiva lógicamente el vínculo y responde `200 VinculoUsuario`; un vínculo inexistente responde `404 VINCULO_NO_ENCONTRADO`.
- El par usuario/departamento es único y se conserva al restaurar. Crear/cambiar/restaurar exige rol contextual vigente del destino y unidad activa; la desactivación también permite limpiar vínculos con rol revocado o unidad inactiva.
- El primer vínculo activo de una unidad debe ser titular; copropietarios e inquilinos requieren un titular activo. Retirar o cambiar la relación del último titular responde `409 TITULAR_REQUERIDO`. Para sustituirlo se registra primero otro titular. La tenencia se cuenta desde los vínculos activos, independientemente del estado de acceso de la cuenta o su rol.
- Cambios reales incrementan `auth_revision` y auditan atómicamente. Un `PUT` idéntico o `DELETE` repetido conserva revisión e historial; todas las precondiciones siguen aplicando. Restaurar no revive tokens revocados.

### CON-06: roles

Se conserva el [contrato de roles integrado](../02-domains/05-usuarios-rbac/roles-y-permisos.md). Cada par usuario/condominio tiene como máximo una asignación, con revocación lógica. Familia `/condominios/{condominio_id}/usuarios/{usuario_id}/rol`:

- `GET` consulta la asignación, incluso revocada; `PUT {"rol":"RESIDENTE"}` asigna, cambia o reactiva; `DELETE` revoca. Las respuestas son `200 AsignacionRol`: usuario, condominio, rol y `es_activo`.
- Roles asignables: `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`. La lectura conserva roles SQL históricos; `SUPERADMIN` contextual heredado no concede privilegio global. No hay conjunto de roles ni prioridad entre varios roles de un mismo contexto.
- SuperAdmin administra contextos activos y puede incorporar una identidad por UUID. Junta solo gestiona Auditor/Residente ya asignados a su contexto, si el rol anterior también es Auditor/Residente; no modifica otra Junta, aunque su asignación esté revocada. Auditor y Residente no acceden a esta gestión.
- Se rechaza modificar la propia asignación o una identidad SuperAdmin global. `es_superadmin` se provisiona por CLI y no es editable aquí. Un usuario sin asignación responde `404 ROL_NO_ENCONTRADO` en consulta/revocación y en asignación por Junta.

La mutación serializa asignaciones, revalida al actor y confirma rol, auditoría e incremento de `auth_revision` conjuntamente. Repetir el rol activo o la revocación es no-op. Login y rutas protegidas usan asignaciones activas en condominios activos; revocar excluye ese contexto y revoca JWT anteriores. Reactivar conserva la fila y no restaura tokens antiguos.

`GET /condominios/{condominio_id}/usuarios` conserva los campos de cuenta y añade `rol`, `rol_activo` y `es_superadmin` de solo lectura. `GET /cuotas/departamentos` y la autorización de unidades en pagos/reservas usan el padrón SQL de CON-05, con `edificio_id` y `edificio_nombre` para distinguir números de unidad repetidos. El resto de la persistencia financiera y de reservas corresponde a CON-70/73.

## 4. Catálogo, disponibilidad y reservas

### CON-39 — catálogo integrado por Jerson

Se conserva el [contrato de catálogo integrado](../02-domains/04-reservas/catalogo-areas.md). `GET /areas?condominio_id=...` devuelve el catálogo SQL activo del portal, con moneda y `zona_horaria=America/Lima`; el residente solo consulta áreas compartidas o de edificios con unidades activamente vinculadas.

Administración usa `GET|POST /condominios/{condominio_id}/areas`, `GET|PUT /condominios/{condominio_id}/areas/{area_id}` y `PATCH /condominios/{condominio_id}/areas/{area_id}/estado`. Auditor solo consulta. El listado administrativo admite `limit`, `offset` y `esta_activa`; POST devuelve `201`, consultas/edición/estado `200`.

POST/PUT reciben nombre, aforo, costo, `hora_apertura`, `hora_cierre` y `tiempo_maximo_horas`; descripción y edificio son opcionales. Apertura/cierre `HH:MM`, iguales para todos los días, apertura menor a cierre y duración máxima entera 1–24 horas. No hay horarios semanales ni campo de normas en esta entrega. El cliente no determina moneda, contexto ni estado mediante ese cuerpo. El cambio de estado recibe únicamente `esta_activa`.

Desactivar impide nuevas reservas, conserva historial y no recalcula tarifas previas. Las áreas exclusivas exigen que el departamento de la reserva pertenezca al edificio correspondiente, también para actores administrativos. CON-73 reutiliza `areas_comunes` y la migración `20261020_0010`; no crea un catálogo paralelo.

CON-73 define lectura de bloqueos operativos persistidos por área/fecha/intervalo, activos y sin datos personales. Si no existen, la colección es vacía. Su gestión no está implementada por CON-39; cualquier nueva operación pública se acuerda mediante PR.

### CON-40 — Gerardo

`GET /areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD`: `200` con arreglo de `HorarioOcupado`, ordenado y con solapamientos fusionados. Considera reservas `CONFIRMADA` de todas las unidades y bloqueos activos; no devuelve nombres, contacto, UUID de reserva o unidad de terceros. El frontend cruza ese resultado con los horarios permitidos del catálogo. Un arreglo vacío no significa uso ilimitado fuera del horario.

Área inexistente: `404 AREA_NO_ENCONTRADA`; inactiva: `409 AREA_INACTIVA`; fecha inválida: `422 DATOS_DISPONIBILIDAD_INVALIDOS`; contexto o edificio no autorizado: `403 ACCESO_DENEGADO`. Una fecha pasada se rechaza con `422 FECHA_RESERVA_INVALIDA`. Consultar hoy no habilita a reservar intervalos ya iniciados.

### CON-41/43 — Brandon; CON-42 — Anderson

`POST /reservas` recibe exclusivamente contexto, área, departamento, fecha e intervalo. Responde `201 Reserva` en estado `CONFIRMADA`, con costo, moneda e instante determinados por servidor. Validar unidad existente/activa/autorizada y compatible con el edificio, área activa, fecha no pasada, inicio futuro, apertura/cierre diarios, duración máxima, solvencia y exclusión de solapamientos dentro de la misma transacción. Conservar `400 HORARIO_INVALIDO` por horario/duración y `409 AREA_INACTIVA` de CON-39.

`403 DEUDA_MORA_ACTIVA` incluye solo deuda autorizada de esa unidad, sin crear reserva ni confirmación. `409 HORARIO_NO_DISPONIBLE` deja un único ganador ante concurrencia; la protección SQL funciona también si el intervalo no tiene filas previas. Una consulta previa de disponibilidad no sustituye esa protección.

Contrato interno de CON-42: entrada `condominio_id`, `departamento_id` y sesión/transacción de reserva; resultado con unidad conocida/activa y `deuda_vencida: Decimal`. Validar autorización antes de consultar o devolver deuda. Unidad desconocida/inactiva es error, nunca deuda cero. Consultar cuotas y obligaciones persistidas de CON-70; un voucher en revisión no cancela deuda. No crear una API pública adicional solo para esta colaboración.

`GET /reservas` incluye estados históricos autorizados. El residente ve sus unidades activamente vinculadas; administración/auditor ven su contexto. Esta lista no se usa para reconstruir el calendario general filtrando solo reservas propias.

### CON-46 — Gerardo

`POST /reservas/{reserva_id}/cancelar` recibe motivo opcional y devuelve `200 ReservaCancelada`. La presencia histórica de `es_admin` se ignora; el permiso procede de la sesión. Residente: `inicio - ahora >= 24 horas`, interpretando el inicio según la zona conservada de la reserva (UTC para históricos sin marca local); administración autorizada puede exceptuar el plazo. Estados diferentes de `CONFIRMADA` o `CANCELADA` responden `422 ESTADO_RESERVA_INVALIDO`.

La cancelación guarda estado, fecha original, actor, motivo, auditoría y evento en una transacción. Repetir `CANCELADA` devuelve el resultado original sin cambiar fecha, repetir evento ni ajuste. Compartir protección SQL con creación para liberar y volver a ocupar el turno de forma consistente.

Política base de compensación: solo se considera un cobro efectivo registrado y asociado a esa reserva, nunca la tarifa como prueba de pago. Si no lo hay, `ajuste_economico={"estado":"NO_APLICA","monto":"0.00","referencia":null}`. Cuando exista cobro reembolsable, registrar una solicitud por el importe efectivamente pagado y no compensado, con unicidad por reserva; `PENDIENTE` no afirma devolución ni modifica saldos por sí solo. `APLICADO` exige referencia a un asiento compensatorio confirmado. La ejecución financiera corresponde al flujo integrado, se audita y nunca se repite por reintentar una cancelación. No se realiza una transferencia bancaria automática en este contrato.

## 5. Pagos — Anderson y Brandon; persistencia CON-70

### Reporte y recuperación

`POST /pagos/reportar` es multipart único: `departamento_id`, `banco`, `numero_operacion`, `fecha_operacion`, `monto`, `archivo_voucher`. Banco normalizado entre YAPE, PLIN, BCP, INTERBANK, BBVA, SCOTIABANK. Operación de 1–50 caracteres, sin espacios tras normalizar. Voucher PNG/JPEG/PDF de hasta **5 MiB (5242880 bytes)**; validar contenido real y rechazar formatos ajenos, no solo comprobar nombre/MIME declarado.

El servidor genera la clave privada de almacenamiento y el hash canónico. No acepta `url_voucher` como acreditación de una subida. Un fallo entre almacenamiento y SQL no devuelve éxito; debe conservar una tarea de limpieza/reconciliación de objetos huérfanos o revertir la carga según el adaptador.

`GET /pagos/comprobantes` devuelve únicamente registros autorizados y una `url_voucher` generada por servidor hacia `GET /pagos/{comprobante_id}/voucher`. Esa ruta vuelve a comprobar permisos, entrega el binario con `Cache-Control: no-store` y no expone claves S3 públicas.

### Idempotencia, estados y corrección

| Caso | HTTP / código / resultado |
|---|---|
| Comprobante nuevo confirmado | `202`, `COMPROBANTE_RECIBIDO`, estado `EN_REVISION`, UUID y hash persistidos. |
| Reintento propio equivalente en revisión | `200`, `VOUCHER_EN_EVALUACION`, mismo UUID y hash; no guardar otro archivo/evento. |
| Operación aprobada previamente | `409 VOUCHER_YA_CONCILIADO`. |
| Reutilización en otra unidad | `409 VOUCHER_UNIDAD_DISTINTA`, sin devolver el UUID ni datos de la unidad ajena. |
| Mismos datos de un observado | `409 VOUCHER_REQUIERE_SUBSANACION`; usar la operación de subsanación. |
| Mismos datos de un rechazado | `409 VOUCHER_RECHAZADO`; conserva decisión e historial, sin reabrir automáticamente. |
| Archivo excede límite / formato ajeno / contenido inválido | `413 ARCHIVO_DEMASIADO_GRANDE` / `415 FORMATO_VOUCHER_NO_SOPORTADO` / `422 VOUCHER_INVALIDO`. |

Hash: `SHA256(condominio_id|banco_normalizado|operacion_normalizada|fecha_YYYY-MM-DD|monto_2_decimales)`. Quitar todos los espacios de banco/operación, pasar banco a mayúsculas y quitar ceros iniciales de operación. Rechazar una operación en blanco; usar `0` únicamente cuando solo contenía ceros. El monto debe ser positivo, representable y de precisión admitida antes de calcular hash; no redondear silenciosamente entradas inválidas. La restricción única SQL es la garantía entre procesos.

Estado público y persistido: `EN_REVISION`, `APROBADO`, `OBSERVADO`, `RECHAZADO`. Retirar el alias público `CONCILIADO` al adaptar listado, DTO y frontend en el mismo PR de integración.

`PUT /pagos/{comprobante_id}/voucher` acepta solo un nuevo archivo para un `OBSERVADO`: conserva UUID, hash y datos bancarios, agrega una versión privada del archivo y pasa a `EN_REVISION`, con nuevo evento de recepción. Revisar estado bajo lock; otro estado responde `409 ESTADO_COMPROBANTE_INVALIDO`. Las correcciones bancarias o de un rechazo requieren revisión administrativa explícita; no hay reapertura automática ni borrado de la evidencia anterior.

### Resultado real de revisión

`POST /pagos/{comprobante_id}/conciliar`, solo administración del contexto, decide `APROBADO`, `OBSERVADO` o `RECHAZADO`; motivo obligatorio para los dos últimos. `200 ResultadoRevision` devuelve los campos financieros completos definidos en OpenAPI. No devuelve notas internas al residente.

Una decisión solo modifica un `EN_REVISION`. Repetir el mismo resultado de la revisión vigente devuelve su respuesta persistida; no imputa dinero otra vez. Otra decisión sobre estado final responde `409 ESTADO_COMPROBANTE_INVALIDO`. La subsanación observada inicia una nueva revisión trazada.

CON-70 implementa resultado y efectos financieros reales con auditoría y outbox. Aprobación produce `PagoConciliadoEvent`; observación/rechazo, `PagoRevisadoEvent`. Reportar o subsanar no cambia saldos. El saldo resultante y la habilitación informativa de reservas se calculan desde registros reales, no cuotas simuladas ni una plantilla.

## 6. Notificaciones — Alejandro; persistencia CON-73

Las confirmaciones automáticas se originan en los eventos del [catálogo](../03-contracts/events/domain-events-catalog.md). No se requiere que el frontend llame a despacho para completar una reserva o un pago. El registro identifica evento, operación, contexto, destinatario, canal y transporte.

`GET /notificaciones/logs` permite administración/auditor del contexto. El residente ve solo comunicaciones destinadas a su identidad y a unidades con vínculo activo; tener acceso a un departamento no concede ver contactos o comunicaciones individuales de otro usuario. El filtro `departamento_id` es UUID.

`POST /notificaciones/despachar` y `/comunicado-masivo` son administrativos: confirman registros en cola con `202`, sin prometer entrega. Un comunicado genera avisos desde destinatarios autorizados y unidades activas; `generadas` cuenta avisos lógicos persistidos.

`POST /notificaciones/reenviar/{log_id}` responde `200` con el log vigente. `ENVIADO` y `ENTREGADO` no provocan otro envío; avisos ya en cola o programados se reutilizan. Para un fallo definitivo o agotado, corregir a un nuevo destinatario autorizado puede iniciar un nuevo ciclo manual trazado; nunca borrar los intentos anteriores. Sin corrección, el agotamiento responde `409 INTENTOS_AGOTADOS`.

| Estado | Significado |
|---|---|
| `EN_COLA` | Aviso persistido, pendiente de aceptación del proveedor. |
| `ENVIADO` | Aceptado por el proveedor; todavía sin confirmación de entrega. |
| `ENTREGADO` | Entrega confirmada por el proveedor de forma autenticada e idempotente. |
| `REINTENTANDO` | Fallo temporal y siguiente intento programado. |
| `FALLIDO_PERMANENTE` | Fallo definitivo o intentos del ciclo agotados. |

El transporte se identifica como `SIMULADO` o `PROVEEDOR`; la simulación y un HTTP 200/202 de aceptación no acreditan entrega. La confirmación real se procesa mediante el adaptador del proveedor y una referencia externa idempotente.

Cada ciclo tiene hasta cuatro intentos efectivos: inicial y reintentos a los 2, 10 y 30 minutos desde el fallo anterior; el primero agrega jitter de ±15 segundos. `intentos` comienza en cero y solo aumenta al ejecutar, no al programar. Conservar el ciclo, cada intento, el próximo instante y la referencia del proveedor; recuperar pendientes tras reinicios mediante lock/lease persistente.

Un timeout con aceptación incierta se reconcilia con la referencia o clave idempotente del proveedor antes de reenviar. La deduplicación local evita avisos lógicos duplicados; la entrega física exactamente una vez depende de las capacidades del proveedor.

## 7. Errores comunes

Además de los códigos por operación, se usan `401 NO_AUTENTICADO`, `TOKEN_INVALIDO`, `TOKEN_EXPIRADO`, `SESION_DESACTUALIZADA` o `SESION_REVOCADA`; `403 ACCESO_DENEGADO`; `404` según recurso; `422 DATOS_USUARIO_INVALIDOS`, `DATOS_AREA_INVALIDOS`, `DATOS_RESERVA_INVALIDOS` o `DATOS_COMPROBANTE_INVALIDOS`. Los errores inesperados no divulgan stack traces ni datos sensibles. CON-04 conserva `401 CREDENCIALES_INVALIDAS` para cuenta inactiva o credenciales erróneas.

## 8. Adopción por historia y estado de cierre

| Responsable | Qué debe implementar usando esta base |
|---|---|
| Jerson | Conservar alta CON-04, vínculos CON-05, rol contextual revocable CON-06 y catálogo SQL CON-39 ya integrados. |
| Anderson | Multipart, recuperación y subsanación CON-22, persistencia/revisión CON-70 y consulta de solvencia CON-42. |
| Brandon | Respuestas y unicidad CON-23, creación CON-41 y garantía SQL CON-43. |
| Alejandro | Consumidores y estados de CON-32/34/36/37; distinguir transporte simulado, aceptación y entrega. |
| Gerardo | DTO/consulta persistente CON-40, cancelación CON-46, evolución de contratos CON-72 y evidencia CON-75. |
| Nicolás | Repositorios/migraciones/outbox CON-73 e integración de API/frontend CON-74, coordinando cambios compartidos. |

Las firmas de colaboración se implementan en las historias de origen: lectura de catálogo y ocupaciones, evaluación de solvencia dentro de la sesión SQL, cancelación transaccional y cola de notificaciones. No crear repositorios alternativos en memoria para acreditar el cierre.

**Verificación:** las pruebas de convergencia contrastan respuestas de API y eventos
reales con los esquemas publicados, con PostgreSQL migrado y autorización real.
El recorrido Chromium incluye reporte, observación, subsanación, aprobación,
descarga y aviso. Esta evidencia local no sustituye revisión de pares ni validación
del esquema desplegado. El proveedor externo y el rediseño siguen fuera del alcance.

## 9. Procedimiento de cambios durante el sprint

Un desarrollador puede ajustar un contrato al implementar su HU. En el mismo PR actualiza OpenAPI/fragmentos, dominio/proceso y productor/consumidor afectados. Identifica cambio, motivo, compatibilidad y colaboradores involucrados. Si cambia nombres, campos obligatorios, estados, permisos, importes o reglas temporales, coordina la adopción antes de fusionar; las correcciones menores siguen la revisión habitual.

No es obligatorio que Gerardo implemente cada ajuste: el responsable de la historia mantiene su contrato y avisa a quienes lo consumen. Conservar compatibilidad con mensajes persistidos o documentar adaptador y migración. No editar una versión de evento publicada para reinterpretar mensajes antiguos: crear nueva versión. Seguir [CONTRIBUTING.md](../../CONTRIBUTING.md), con ramas de trabajo, Conventional Commits y PR hacia `develop`.
