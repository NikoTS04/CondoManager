# CON-72 — Contratos base de implementación del Sprint 2

**Responsable:** Gerardo. **Base:** 20/10/2026. **Estado:** contratos definidos para implementar; validación automatizada, integración y revisión de pares pendientes. Los contratos pueden evolucionar mediante el procedimiento de cambios de la sección 9.

## 1. Fuentes y alcance

| Artefacto | Uso |
|---|---|
| [condomanager.openapi.yaml](../03-contracts/openapi/condomanager.openapi.yaml) | Entrada del contrato HTTP objetivo; versión documental 2.0.0. |
| [sprint-2.paths.yaml](../03-contracts/openapi/sprint-2.paths.yaml) | Operaciones por HU, estados HTTP, permisos y marcas de implementación pendiente/parcial. |
| [sprint-2.schemas.yaml](../03-contracts/openapi/sprint-2.schemas.yaml) | Formas de entrada/salida y tipos compartidos. |
| [Catálogo de eventos](../03-contracts/events/domain-events-catalog.md) | Productores, consumidores, versiones, esquemas y recuperación. |

CON-72 entrega interfaces para que cada responsable implemente sus historias. Definir un endpoint en OpenAPI no lo incorpora a FastAPI. Los routers, DTO Python, tipos TypeScript, repositorios y migraciones actuales deben adoptar estos contratos en las HU indicadas; los almacenes piloto en memoria no satisfacen la integración persistente.

Para los contratos del Sprint 2 se usan los artefactos de esta tabla. Cada responsable alinea los documentos de dominio, proceso y persistencia afectados en el PR que implemente su HU; esas actualizaciones generales quedan fuera de esta entrega.

## 2. Convenciones comunes

- HTTP REST con JSON, excepto subida multipart y descarga binaria de vouchers. No se exige el formato JSON:API. Prefijo `/api/v1`, identificadores UUID y cuerpos con campos adicionales rechazados, salvo mapas expresamente abiertos.
- Dinero como cadena de dos posiciones, sin notación exponencial y dentro de `NUMERIC(12,2)`. Se rechaza precisión adicional; los cálculos usan `Decimal`. La moneda se hereda del condominio; el cliente no elige otra para una reserva o comprobante.
- Calendario en `America/Lima`. Fechas `YYYY-MM-DD`; horas `HH:MM:00`, con precisión de minuto. No se cruza medianoche: dividir usos de distintos días en operaciones separadas. Intervalos semiabiertos `[inicio, fin)`; dos intervalos contiguos no se solapan.
- Instantes de auditoría, confirmación, cancelación y eventos en UTC, con `Z` u offset `+00:00`. Para aplicar 24 horas se convierte fecha/hora local del inicio a un instante; nunca asignar UTC directamente a una hora de Lima.
- El calendario local no modifica la planificación UTC ya implementada por el worker de cuotas de CON-11; cualquier cambio de ese cron se acuerda en su propia historia.
- Bearer obligatorio salvo login, salud y demo según su contrato. `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE` son los únicos roles; propietario, copropietario e inquilino son relaciones por departamento.
- Toda escritura valida rol, condominio y recurso. El residente opera exclusivamente con sus vínculos activos; `AUDITOR` no escribe. Los filtros nunca amplían el permiso. Un SuperAdmin global selecciona contexto para las consultas que lo necesitan.
- Confirmar la operación, auditoría y evento pendiente en una transacción antes de responder éxito. Una reversión no modifica saldos, horarios ni notificaciones de éxito.
- Error en raíz: `error_code`, `mensaje`, `detalles` opcional como objeto. Las validaciones se agrupan en `detalles.errores`, sin reproducir contraseñas, tokens o contenido de archivos. Durante la adopción el lector frontend conserva compatibilidad con `detail` histórico; los nuevos handlers usan el formato raíz.

## 3. Usuarios y accesos — Jerson

CON-04 conserva [alta-administrativa.md](../02-domains/05-usuarios-rbac/alta-administrativa.md): cuenta inactiva por defecto, contraseña inicial del administrador, habilitación manual exclusiva de SuperAdmin, login SQL y `auth_revision`. La invitación por correo queda fuera de este sprint.

### CON-05: vínculos

Familia `/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos`:

- `GET`: administración y auditor consultan vínculos activos e inactivos del contexto.
- `POST`: administración crea un vínculo activo con `departamento_id` y `tipo_relacion`; responde `201 Vinculo`. El usuario debe pertenecer al contexto y la unidad debe existir en ese condominio.
- `PATCH .../{departamento_id}`: administración recibe `{"es_activo": false}` o `true`, responde `200 Vinculo`. Un no-op no repite auditoría ni incrementa la revisión de autorización.
- El par usuario/departamento es único. Un duplicado responde `409 VINCULO_DUPLICADO`; cambios de relación se tramitan de forma explícita en una evolución del contrato, sin duplicar el par.
- Una unidad activa conserva al menos un propietario titular activo; el primer vínculo se crea como titular. No se desactiva el último titular de una unidad activa: `409 TITULAR_REQUERIDO`. Antes de habilitar copropietario/inquilino debe existir titular. Para sustituirlo se registra primero el vínculo titular de la nueva identidad y luego se desactiva el anterior; cada mutación protege esta condición bajo el mismo bloqueo de unidad.
- Cambios reales invalidan sesiones anteriores de la identidad afectada mediante `auth_revision`, preservan historial y se auditan. Reactivar un vínculo no revive tokens revocados.

### CON-06: roles

Familia `/condominios/{condominio_id}/usuarios/{usuario_id}/roles`: `GET` consulta; `PUT {"roles":[...]}` reemplaza atómicamente el conjunto contextual y devuelve `RolesUsuario`.

Roles asignables: `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`, sin duplicados y con al menos uno. El rol efectivo usa prioridad `ADMIN_JUNTA > AUDITOR > RESIDENTE`. SuperAdmin puede administrar esos roles; un administrador contextual solo modifica asignaciones de residente/auditor de otras personas, sin conceder o retirar `ADMIN_JUNTA` ni modificar sus propios roles. `es_superadmin` no es editable en esta API.

La mutación serializa asignaciones, vuelve a validar al actor y registra auditoría e invalidación de sesión. Repetir el conjunto es no-op. El login conserva selección de condominio para múltiples asignaciones; varias filas del mismo contexto no se presentan como condominios distintos. Las operaciones de usuarios y las consultas del resto del sistema deben resolver el mismo rol efectivo.

Las identidades con concesión global `es_superadmin` no se administran mediante esta familia contextual: responder `403 ACCESO_DENEGADO` si se intenta modificar su conjunto de roles aquí. Se preserva la provisión global ya documentada en CON-04.

## 4. Catálogo, disponibilidad y reservas

### CON-39 — Jerson; persistencia CON-73 — Nicolás

`GET /areas?condominio_id=...` devuelve áreas activas, horarios, reglas y `zona_horaria=America/Lima`. Administración/auditor pueden usar `incluir_inactivas=true`; para residentes ese filtro se rechaza.

`POST /areas` crea nombre, descripción, aforo positivo, costo no negativo, normas y horarios. `PATCH /areas/{area_id}` edita condiciones o desactiva, solo para administración del contexto. Horarios semanales: `dia_semana` ISO 1–7, inicio menor a fin y sin solapamientos dentro del mismo día. El alta requiere al menos un horario. No se cambia condominio ni se borran reservas; una edición no recalcula costos de reservas ya confirmadas.

CON-73 define además lectura de bloqueos operativos persistidos por área/fecha/intervalo, activos y sin datos personales. Si no existen, la colección es vacía. La API de gestión de bloqueos no se añade al alcance de CON-39; cualquier nueva operación se acuerda mediante PR.

### CON-40 — Gerardo

`GET /areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD`: `200` con arreglo de `HorarioOcupado`, ordenado y con solapamientos fusionados. Considera reservas `CONFIRMADA` de todas las unidades y bloqueos activos; no devuelve nombres, contacto, UUID de reserva o unidad de terceros. El frontend cruza ese resultado con los horarios permitidos del catálogo. Un arreglo vacío no significa uso ilimitado fuera del horario.

Área inexistente: `404 AREA_NO_ENCONTRADA`; inactiva: `422 AREA_INACTIVA`; fecha inválida: `422 DATOS_DISPONIBILIDAD_INVALIDOS`; contexto ajeno: `403 ACCESO_DENEGADO`. Una fecha pasada se rechaza con `422 FECHA_RESERVA_INVALIDA`. Consultar hoy no habilita a reservar intervalos ya iniciados.

### CON-41/43 — Brandon; CON-42 — Anderson

`POST /reservas` recibe exclusivamente contexto, área, departamento, fecha e intervalo. Responde `201 Reserva` en estado `CONFIRMADA`, con costo e instante determinados por servidor. Validar unidad existente/activa/autorizada, área activa, fecha no pasada, inicio futuro, horario del catálogo, solvencia y exclusión de solapamientos dentro de la misma transacción.

`403 DEUDA_MORA_ACTIVA` incluye solo deuda autorizada de esa unidad, sin crear reserva ni confirmación. `409 HORARIO_NO_DISPONIBLE` deja un único ganador ante concurrencia; la protección SQL funciona también si el intervalo no tiene filas previas. Una consulta previa de disponibilidad no sustituye esa protección.

Contrato interno de CON-42: entrada `condominio_id`, `departamento_id` y sesión/transacción de reserva; resultado con unidad conocida/activa y `deuda_vencida: Decimal`. Validar autorización antes de consultar o devolver deuda. Unidad desconocida/inactiva es error, nunca deuda cero. Consultar cuotas y obligaciones persistidas de CON-70; un voucher en revisión no cancela deuda. No crear una API pública adicional solo para esta colaboración.

`GET /reservas` incluye estados históricos autorizados. El residente ve sus unidades activamente vinculadas; administración/auditor ven su contexto. Esta lista no se usa para reconstruir el calendario general filtrando solo reservas propias.

### CON-46 — Gerardo

`POST /reservas/{reserva_id}/cancelar` recibe motivo opcional y devuelve `200 ReservaCancelada`. La presencia histórica de `es_admin` se ignora; el permiso procede de la sesión. Residente: `inicio - ahora >= 24 horas`; administración autorizada puede exceptuar el plazo. Estados diferentes de `CONFIRMADA` o `CANCELADA` responden `422 ESTADO_RESERVA_INVALIDO`.

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
| Jerson | CON-05/06, catálogo CON-39, revocación y perfil efectivo; conservar CON-04 vigente. |
| Anderson | Multipart, recuperación y subsanación CON-22, persistencia/revisión CON-70 y consulta de solvencia CON-42. |
| Brandon | Respuestas y unicidad CON-23, creación CON-41 y garantía SQL CON-43. |
| Alejandro | Consumidores y estados de CON-32/34/36/37; distinguir transporte simulado, aceptación y entrega. |
| Gerardo | DTO/consulta persistente CON-40, cancelación CON-46, evolución de contratos CON-72 y evidencia CON-75. |
| Nicolás | Repositorios/migraciones/outbox CON-73 e integración de API/frontend CON-74, coordinando cambios compartidos. |

Las firmas de colaboración se implementan en las historias de origen: lectura de catálogo y ocupaciones, evaluación de solvencia dentro de la sesión SQL, cancelación transaccional y cola de notificaciones. No crear repositorios alternativos en memoria para acreditar el cierre.

**Verificación de esta entrega:** revisión documental. La validación automatizada, integración y revisión de pares quedan pendientes; publicar esta base no acredita el funcionamiento de las HU ni el cierre de CON-72.

## 9. Procedimiento de cambios durante el sprint

Un desarrollador puede ajustar un contrato al implementar su HU. En el mismo PR actualiza OpenAPI/fragmentos, dominio/proceso y productor/consumidor afectados. Identifica cambio, motivo, compatibilidad y colaboradores involucrados. Si cambia nombres, campos obligatorios, estados, permisos, importes o reglas temporales, coordina la adopción antes de fusionar; las correcciones menores siguen la revisión habitual.

No es obligatorio que Gerardo implemente cada ajuste: el responsable de la historia mantiene su contrato y avisa a quienes lo consumen. Conservar compatibilidad con mensajes persistidos o documentar adaptador y migración. No editar una versión de evento publicada para reinterpretar mensajes antiguos: crear nueva versión. Seguir [CONTRIBUTING.md](../../CONTRIBUTING.md), con ramas de trabajo, Conventional Commits y PR hacia `develop`.
