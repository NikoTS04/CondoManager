# CON-72 — Diagnóstico y propuesta de contratos del Sprint 2

**Responsable:** Gerardo. **Estado:** propuesta para revisión; no constituye aprobación de nuevos contratos ni cierre de CON-72. **Base inspeccionada:** `85f1986`, en `develop`, el 20/10/2026.

## 1. Alcance y resultado de la revisión

Se compararon el [Sprint 2](../../docs/sprints/SPRINT-2.md), el [contrato HTTP documentado](api-contracts.md), el [OpenAPI versionado](../03-contracts/openapi/condomanager.openapi.yaml), los routers y DTO de FastAPI, el [cliente del frontend](../../frontend/src/lib/api.ts), el [catálogo de eventos](../03-contracts/events/domain-events-catalog.md) y sus esquemas JSON. También se revisaron persistencia, autorización y verificaciones de contrato existentes.

El OpenAPI generado mediante `app.openapi()` y el YAML versionado describen **38 operaciones HTTP bajo `/api/v1`** cada uno. Al normalizar los nombres de parámetros de ruta, ambos tienen el mismo conjunto de métodos y rutas. Esto comprueba cobertura de rutas, **no equivalencia de cuerpos, respuestas, permisos ni comportamiento**. No se iniciaron servicios ni se ejecutaron peticiones autenticadas para esta inspección.

Los contratos de CON-04 ya reflejan el alta inactiva y la habilitación manual por SuperAdmin. Disponibilidad, cancelación, pagos y notificaciones tienen código aprovechable, pero continúan utilizando almacenes piloto en memoria. CON-05, CON-06 y la administración de CON-39 todavía necesitan operaciones propias; la coincidencia de las 38 rutas no acredita cobertura completa del sprint.

Esta propuesta mantiene los contratos actuales hasta su validación. Las reglas ya acordadas en el sprint se distinguen de las opciones recomendadas que requieren confirmación. No se modifican endpoints, DTO, migraciones, OpenAPI ni esquemas de eventos en esta etapa.

## 2. Inventario por historia y dependencias

Las rutas se expresan sin el prefijo común `/api/v1`. «Propuesta» indica una operación aún no publicada, cuyo nombre y forma deben acordarse con el responsable.

| HU / responsable | Operación o contrato revisado | Situación actual y cambio a preparar | Coordinación necesaria |
|---|---|---|---|
| CON-04 / Jerson | `POST` y `GET /condominios/{condominio_id}/usuarios`; `PATCH /usuarios/{usuario_id}/estado`; `/auth/login`, `/auth/me`, `/auth/demo-users` | Alta y login SQL implementados; conservar cuenta inicialmente inactiva, habilitación exclusiva de SuperAdmin y revocación por `auth_revision`. Limpiar ejemplos de identidad piloto y documentar errores y modo demo. | CON-72 y CON-74. |
| CON-05 / Jerson | Propuesta de consulta y gestión de vínculos por usuario y condominio | Existen modelo, lectura de vínculos en la sesión y datos demo; no hay API de gestión de vínculos. Acordar alta, consulta y desactivación, UUID, relación, unicidad y efecto sobre la sesión. | CON-04, departamentos de CON-3 y CON-06. |
| CON-06 / Jerson | Propuesta de consulta y gestión de roles por usuario y condominio | Existen cuatro roles y resolución contextual. Falta contrato de administración de asignaciones; definir concesión/revocación, límites de `ADMIN_JUNTA` y sesiones vigentes. | CON-04, CON-05 y privilegio global de SuperAdmin. |
| CON-22 / Anderson | `POST /pagos/reportar`; `GET /pagos/comprobantes` | API y cliente envían JSON con `url_voucher`; las especificaciones piden archivo. Completar el contrato de subida, recuperación autorizada y persistencia. | CON-05/06, CON-23, CON-70 y CON-74. |
| CON-23 / Brandon | Reintentos de `POST /pagos/reportar` | Se calcula hash y se consulta un diccionario. El reintento propio continúa respondiendo `202`, mientras la política canónica indica `200` para un voucher en revisión. | Anderson y restricción durable de CON-70. |
| CON-32 / Alejandro | Consumo de `CuotasEmitidasEvent` y registro de avisos | CON-11 ya produce un evento de lote con outbox. El consumidor debe resolver cuotas y destinatarios persistidos y deduplicar avisos; no necesita otro endpoint público para emitir cuotas. | CON-05, CON-11 y CON-73. |
| CON-34 / Alejandro | Recepción del comprobante y resultado real de `POST /pagos/{comprobante_id}/conciliar` | La conciliación actual usa cuotas simuladas. El frontend solo ofrece aprobación/rechazo, aunque DTO y sprint incluyen observación. Faltan eventos y resultado financiero persistente. | Anderson/CON-70 y Brandon/CON-23; después CON-73. |
| CON-36 / Alejandro | Eventos de reserva confirmada/cancelada y operaciones vigentes | Hay servicio de plantillas y despacho; falta integrar productores confirmados y registro durable. La invitación por correo de CON-04 está diferida. | Brandon/CON-41, Gerardo/CON-46 y Nicolás/CON-73. |
| CON-37 / Alejandro | Reintentos automáticos; `POST /notificaciones/reenviar/{log_id}` para intervención administrativa | El reenvío manual y el cálculo de espera no completan el worker automático. Definir intento inicial, tres reintentos, jitter, recuperación y respuesta de registros ya entregados. | CON-32/34/36 y CON-73. |
| CON-39 / Jerson | `GET /areas`; propuesta de alta y edición administrativa | Solo existe consulta del catálogo piloto; faltan escritura, horarios, desactivación y sus contratos. | CON-06 y repositorios/migraciones de CON-73. |
| CON-40 / Gerardo | `GET /areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD` | Endpoint y consumidor existentes; completar DTO explícito, reglas de horario y consulta persistente sin información privada. | CON-39, CON-73 y contratos de CON-41/43. |
| CON-41 / Brandon | `POST /reservas`; `GET /reservas` para las reservas autorizadas | Backend y frontend comparten UUID y `fecha_reserva`; ejemplos narrativos usan otros campos. Integrar creación transaccional, solvencia y exclusión de horarios. | CON-05/06, CON-40/42/43 y CON-73. |
| CON-42 / Anderson | Consulta interna de deuda por departamento para crear una reserva | El piloto consulta deuda precargada. Acordar resultado interno desde cuotas persistidas y rechazo `403 DEUDA_MORA_ACTIVA`; no se requiere por defecto una nueva API pública. | CON-70 y transacción de CON-41. |
| CON-43 / Brandon | Garantía transaccional de `POST /reservas` | Comprobación de intervalos en una lista; falta protección entre procesos y sesiones. Los detalles del bloqueo/restricción se acuerdan con Nicolás. | CON-40/41 y CON-73. |
| CON-46 / Gerardo | `POST /reservas/{reserva_id}/cancelar` | Ya comprueba plazo y deriva permiso administrativo del usuario, pero cambia un diccionario y descarta la auditoría devuelta por el servicio. Completar persistencia, evento y ajustes aplicables. | CON-41, CON-72/73, CON-36 y política económica. |

Las entregas transversales acompañan estos contratos: **CON-70** conserva pagos y efectos financieros; **CON-73** conserva áreas, reservas, eventos y notificaciones; **CON-74** conecta las pantallas; **CON-75** reúne evidencia reproducible. CON-72 coordina sus interfaces y verificaciones, sin asumir la implementación de todas las historias.

## 3. Diferencias verificadas

| ID / prioridad | Evidencia en la base inspeccionada | Consecuencia | Propuesta y responsables |
|---|---|---|---|
| H01 / alta | [API narrativa](api-contracts.md), sección 2.5, usa `fecha`, identificadores como `parrilla-01` y `reserva_id`; [DTO de reservas](../../src/modules/reservas/schemas.py) y cliente usan UUID, `fecha_reserva` e `id`. | Ejemplos que un compañero no puede enviar a la API. | Conservar el vocabulario vigente del DTO/cliente y corregir ejemplos tras aprobar la propuesta. Gerardo y Brandon. |
| H02 / alta | [Router de disponibilidad](../../src/modules/reservas/router.py), función `disponibilidad_area`, no declara `response_model`; su OpenAPI generado devuelve esquema vacío para `200`. El YAML sí describe un arreglo. | El contrato generado no permite validar la respuesta. Además consulta reservas en memoria y no aplica horarios de catálogo. | Definir DTO de intervalo, validar área activa/horarios y usar el repositorio de CON-73. Gerardo, Jerson y Nicolás. |
| H03 / alta | [Máquina de estados](../02-domains/04-reservas/state-machine.md) exige `> 24h`; [sprint](../../docs/sprints/SPRINT-2.md) y `procesar_cancelacion` aceptan exactamente 24h. El servicio interpreta las horas como UTC. | Documentación y cálculo temporal pueden discrepar en la frontera. | Mantener la regla ya acordada `>= 24h`; confirmar zona horaria y conversión antes de codificar. Gerardo y Brandon. |
| H04 / alta | [Router de cancelación](../../src/modules/reservas/router.py), `cancelar_reserva`, modifica `RESERVAS_REGISTRADAS` y recibe auditoría que no persiste. El YAML solo describe el `200`, sin esquema. | Reiniciar pierde el resultado; no hay evidencia durable de cancelación, auditoría o evento. | Contrato detallado de respuesta y transición SQL con auditoría/outbox. Gerardo y Nicolás; consumo por Alejandro. |
| H05 / alta | [API narrativa](api-contracts.md) pide `banco_origen`/`archivo_voucher`; [dominio de pagos](../02-domains/02-pagos-y-moras/spec.md) pide `banco`/`voucher_file`; [DTO HTTP](../../src/modules/pagos/schemas.py), YAML y cliente usan JSON `banco`/`url_voucher`. | El formulario actual no satisface la carga real de archivo de CON-22. | Acordar un único flujo y nombres, límite y almacenamiento; propuesta en la sección 5. Anderson, Brandon y Nicolás para la integración. |
| H06 / alta | [Política de idempotencia](../01-architecture/idempotency-and-deduplication.md) prescribe `200` para duplicado en revisión; el router fija `202` para cualquier retorno normal. El servicio normaliza con `strip()`, sin quitar espacios interiores exigidos por la política. | Clientes y deduplicación no comparten todas las reglas. | `202` nuevo, `200` mismo comprobante en revisión, `409` conciliado o unidad distinta; normalización canónica y unicidad SQL. Anderson y Brandon. |
| H07 / alta | [Diccionario](../03-contracts/database/data-dictionary.md) y servicio utilizan `APROBADO`; el listado convierte ese estado a `CONCILIADO` y el [tipo frontend](../../frontend/src/lib/api.ts) no incluye `OBSERVADO`. El esquema YAML de recepción omite `idempotency_hash`. | Estado y campos de la misma operación cambian entre capas. | Unificar el estado público y completar DTO/respuestas con una migración coordinada del cliente. Anderson, Brandon y Nicolás/CON-74. |
| H08 / alta | `conciliar_pago` en el [router de pagos](../../src/modules/pagos/router.py) crea `cuotas_mock`; el evento de recepción no tiene esquema y el resultado de revisión no tiene productor durable integrado. | CON-34 y la rehabilitación de solvencia no pueden cerrarse con esos datos. | Acordar en CON-70 el productor real, estados y efectos financieros; CON-34 consume el resultado posterior al commit. Anderson y Alejandro. |
| H09 / alta | [Catálogo de eventos](../03-contracts/events/domain-events-catalog.md) declara un envelope común, pero cuatro de sus cinco esquemas actuales son planos; `cuotas-emitidas.schema.json` usa `data`. | Un consumidor no puede tratar uniformemente los mensajes ni asumir versión/contexto. | Preservar el evento de CON-11 y acordar evolución versionada y adaptadores, sin cambiar productores aisladamente. Gerardo y los responsables de cada dominio. |
| H10 / alta | `PagoReportadoEvent` y `ReservaCanceladaEvent` están en el catálogo, sin archivo de esquema; no hay esquema de resultado observado/rechazado. | Faltan contratos para recepción, revisión y cancelación. | Definir productores, consumidores, datos mínimos y esquemas junto con las historias de origen. Gerardo, Anderson, Brandon y Alejandro. |
| H11 / media | [Errores comunes](../../src/core/errors.py) serializan `APIError` en raíz; pagos/reservas/notificaciones también usan `HTTPException.detail`. El esquema `detalles` es objeto, pero algunas validaciones de usuarios devuelven una lista. | El mismo cliente debe interpretar formas distintas y el YAML no describe todas. | Mantener temporalmente el lector compatible del frontend y acordar un error raíz con detalles estructurados. Gerardo y responsables de API. |
| H12 / alta | [Servicio de notificaciones](../../src/modules/notificaciones/service.py) usa transporte simulado por defecto y marca `ENTREGADO` con una respuesta exitosa del transporte; el [router](../../src/modules/notificaciones/router.py) conserva logs en memoria. | Aceptación por transporte o mock no demuestra entrega al destinatario ni recuperación. | Separar registro, aceptación y entrega confirmada en el contrato, conservando intentos y origen. Alejandro y Nicolás. |
| H13 / media | `GET /notificaciones/logs` solo permite administración/auditor; CON-74 pide consulta de comunicaciones para usuarios autorizados. Hay filtros de departamento documentados como número y otros contratos usan UUID. | Falta decidir la consulta para residentes y la identidad usada en filtros. | Acordar alcance de lectura por perfil y UUID; no ampliar permisos sin aprobación. Gerardo, Alejandro y Nicolás. |
| H14 / media | [Identidad](../02-domains/05-usuarios-rbac/identidad-y-alcances.md) conserva ejemplo `usr-res-102`, pese a que [CON-04](../02-domains/05-usuarios-rbac/alta-administrativa.md) exige UUID SQL y `auth_revision`. También quedan menciones a invitaciones en el sprint/eventos. | Un ejemplo histórico puede confundirse con una identidad vigente o ampliar el alcance de CON-04. | Tomar alta administrativa como contrato actual; corregir ejemplos y marcar invitación como futura. Gerardo y Jerson. |
| H15 / alta | [Verificación actual](../../scripts/ci/verify_api_contract.py) usa OpenAPI generado y comprueba `not_a_server_error`, sin tokens para los recorridos protegidos. | Un check verde no prueba igualdad con el YAML ni respuestas autenticadas de éxito. | Añadir verificaciones de compatibilidad y ejemplos autenticados después de aprobar contratos, además del control de robustez. Gerardo y Alejandro. |

## 4. Primera propuesta: disponibilidad, creación y cancelación

### 4.1 Reglas comunes

Reglas ya fijadas por el sprint: UUID para recursos; cuatro roles canónicos; autorización por condominio y vínculo activo; `AUDITOR` solo consulta; dinero decimal; éxito después de commit; cancelación voluntaria con al menos 24 horas; eventos reentregables sin duplicar efectos.

Propuestas pendientes: usar `America/Lima` para interpretar fechas y horas del calendario y UTC con offset en instantes de auditoría/eventos; mantener intervalos semiabiertos `[inicio, fin)` para permitir horarios contiguos; adoptar error raíz `{error_code, mensaje, detalles?}`. La zona debe formar parte explícita del contrato acordado con catálogo y persistencia, sin asumir que una hora local es UTC.

### 4.2 CON-40 — Consultar disponibilidad

Conservar `GET /api/v1/areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD` y el arreglo consumido por `fetchDisponibilidad`. Ejemplo propuesto de `200`:

```json
[
  { "hora_inicio": "19:00:00", "hora_fin": "22:00:00" }
]
```

- `area_id` es UUID y `fecha` es fecha de calendario de la zona acordada. Formalizar `HoraOcupadaDTO` con horas serializadas de manera consistente entre API y frontend.
- Incluir los intervalos confirmados de todas las unidades que ocupan el área, sin nombres, contactos, UUID de reserva ni departamento de terceros. `GET /reservas` sigue siendo una consulta de reservas autorizadas del usuario y no sustituye este calendario.
- Ordenar por inicio y fin. Un arreglo vacío significa ausencia de ocupaciones, no disponibilidad ilimitada: el cliente también aplica los horarios vigentes de CON-39. Los bloqueos explícitos deben tener modelo y reglas acordados con CON-73 antes de incorporarse.
- Conservar `401/403`; documentar `404` para área inexistente y proponer `422` para fecha inválida o área inactiva, con códigos acordados. No convertir área desconocida/inactiva en `200 []`.
- Consulta SQL del repositorio de Nicolás. La consulta orienta al residente; la creación de CON-41 vuelve a validar horarios y solvencia dentro de su propia transacción.

### 4.3 CON-41/42/43 — Crear y proteger la reserva

Conservar `POST /api/v1/reservas` y los campos actuales: `condominio_id`, `area_id`, `departamento_id`, `fecha_reserva`, `hora_inicio`, `hora_fin`. Conservar la respuesta de `ReservaResponseDTO` completa: `id`, contexto, área, unidad, fecha, horas, costo, estado y fecha de creación; `area_nombre` puede ser opcional. OpenAPI y ejemplos deben describir ese mismo objeto.

La reserva termina en `CONFIRMADA` y responde `201` únicamente tras confirmar la transacción. La operación usa el resultado persistente de solvencia de Anderson y la protección de intervalos de Brandon/Nicolás. `403 DEUDA_MORA_ACTIVA` no crea reserva ni evento exitoso; el perdedor de una carrera recibe `409 HORARIO_NO_DISPONIBLE`.

Proponer una función interna de solvencia con entrada `(condominio_id, departamento_id)` y resultado que distinga unidad válida/activa/autorizada, deuda vencida exigible y solvencia. El desconocimiento de la unidad nunca equivale a deuda cero. Precisar sesión/transacción y consistencia con CON-70 antes de elegir la firma definitiva. CON-43 debe coordinar creación y cancelación sobre la misma protección SQL; un lock de memoria no completa esa garantía.

### 4.4 CON-46 — Cancelar

Conservar `POST /api/v1/reservas/{reserva_id}/cancelar` y cuerpo opcional `{"motivo":"Cambio de planes"}`. `es_admin` no concede permisos: el backend actual ya lo sustituye por el rol autenticado. Proponer retirarlo del contrato público después de revisar compatibilidad.

Respuesta propuesta `200`, consistente con `CancelarReservaResponse`:

```json
{
  "id": "d19f20f5-3eef-4e73-b2e3-a150526d5f33",
  "estado": "CANCELADA",
  "mensaje": "Reserva cancelada.",
  "fecha_cancelacion": "2026-10-20T17:00:00Z"
}
```

- Residente: vínculo activo con el departamento de la reserva. Administración: rol y condominio autorizados. Mantener rechazos por acceso a otra unidad/condominio y escritura por auditor.
- Residente puede cancelar cuando `inicio_reserva - ahora >= 24 horas`; comparar instantes tras aplicar la zona acordada. Probar la frontera exacta y ambos lados.
- Cambiar estado, registrar auditoría y guardar el evento pendiente en una transacción; liberar el turno tras commit, sin borrar la reserva. Una reversión conserva la ocupación y no comunica éxito.
- Proponer que repetir una cancelación ya confirmada devuelva el mismo resultado persistido `200`, sin nuevo evento ni ajuste. Hoy el servicio rechaza la repetición con `422`; requiere acuerdo antes de cambiarlo. Los demás estados no cancelables siguen siendo error controlado.
- Si existe un cobro reembolsable, definir previamente elegibilidad, importe, responsable y asiento compensatorio con el flujo financiero. No considerar el simple cambio de estado como evidencia de devolución de dinero.

### 4.5 CON-39 — Contrato de catálogo que necesita disponibilidad

Conservar `GET /areas` con el contexto autorizado y el DTO actual. Proponer a Jerson `POST /areas` para el alta y `PATCH /areas/{area_id}` para editar condiciones o desactivar, con escritura restringida a administración del condominio. El alta incluiría `condominio_id`, nombre, descripción, aforo, costo y horarios; las respuestas devolverían el UUID y las condiciones persistidas.

La estructura de horarios, días permitidos y posibles bloqueos queda en D02: tiene que ser compartida por catálogo, disponibilidad y validación de creación. La desactivación conserva el historial y bloquea nuevas reservas. No añadir una operación de borrado físico como sustituto de esa regla. El DTO final y las migraciones corresponden a CON-39/73; esta sección únicamente propone su interfaz.

## 5. Contratos de pagos y usuarios a coordinar

### Pagos

- **Flujo recomendado para revisión:** un único `POST /pagos/reportar` multipart con `departamento_id`, `banco`, `numero_operacion`, `fecha_operacion`, `monto` y `archivo_voucher`. Mantener `banco` evita introducir otro alias en el cliente; `archivo_voucher` debe unificarse con el `voucher_file` del dominio. Alternativa válida: subida previa con referencia privada emitida por servidor y posterior JSON. Elegir un flujo antes de implementar.
- PNG, JPG y PDF ya son el alcance del sprint. El tamaño máximo, catálogo de bancos, longitud de operación, validación de contenido y recuperación autorizada deben acordarse; actualmente no hay un límite de archivo único documentado. El cliente no debe poder acreditar una carga mediante una URL arbitraria.
- Nuevo comprobante: `202`, `comprobante_id`, `estado=EN_REVISION`, `mensaje` e `idempotency_hash`. Reintento equivalente propio en revisión: `200`, mismo identificador, estado y hash, con código de evaluación acordado. Conciliado o reutilización en otra unidad: `409`, sin exponer datos de otra unidad. Hash/normalización y restricción durable siguen la política canónica.
- **Estado público recomendado para revisión:** `APROBADO`, igual al dominio/SQL, junto con `EN_REVISION`, `OBSERVADO` y `RECHAZADO`. Hoy el frontend usa `CONCILIADO`; aceptar la propuesta exige migrar listado, tipos y chips juntos. No basta con cambiar un enum del YAML.
- Acordar qué sucede al reenviar un comprobante observado/rechazado y cómo conservar las correcciones y su historial. La política explícita de reintentos en revisión no resuelve ese caso.
- Mantener `POST /pagos/{comprobante_id}/conciliar` como productor real del resultado que usa CON-34 dentro de la integración de CON-70. Alinear sus respuestas completas, motivos y posibilidad de observación con el frontend; no extenderse a conciliación bancaria externa fuera del sprint.

### Usuarios, vínculos y roles

- Conservar CON-04 según [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md): contraseña inicial del administrador, alta inactiva, habilitación manual por SuperAdmin, login SQL y revocación de sesión. No introducir invitación por correo como dependencia de cierre.
- **CON-05:** propuesta de familia `/condominios/{condominio_id}/usuarios/{usuario_id}/departamentos`: consultar vínculos, crear el vínculo y desactivarlo mediante su departamento. Definir cuerpo con UUID, `tipo_relacion` y estado administrado; no inventar vínculo por asignar un rol. Jerson debe acordar el contrato y la regla de titularidad antes de publicarlo.
- **CON-06:** propuesta de familia `/condominios/{condominio_id}/usuarios/{usuario_id}/roles`: consultar y gestionar asignaciones permitidas. Acordar si se modifica una asignación o un conjunto y cómo se resuelven varios roles contextuales. No exponer `es_superadmin` como concesión de un administrador de condominio.
- Mutaciones de vínculo/rol deben surtir efecto sobre la siguiente solicitud protegida y evitar que reactivar un acceso reviva sesiones revocadas. Reutilizar la estrategia vigente de `auth_revision` y resolución SQL, coordinada con Jerson; no prometer que CON-04 ya implementó todas las mutaciones de CON-05/06.

## 6. Eventos y comunicaciones

El [relay de CON-11](../../src/modules/cuotas/worker.py) ya publica `CuotasEmitidasEvent` con `event_id`, `event_type`, `producer`, `occurred_at` y `data` en `condomanager:domain-events`, desde outbox SQL. El catálogo lo denomina CloudEvents, pero la forma actual no declara sus atributos requeridos `id`, `source`, `specversion` y `type`; describirlo como envelope propio o acordar una adopción formal posterior. Referencia: [atributos requeridos de CloudEvents](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#required-attributes). CON-72 no necesita cambiar de estándar para cerrar este sprint.

| Evento | Productor / consumidor del Sprint 2 | Contrato que falta cerrar |
|---|---|---|
| `CuotasEmitidasEvent` | CON-11 / CON-32 | Conservar el esquema y el productor existentes. Resolver detalle de cuotas y destinatarios desde el lote persistido. Evitar avisos duplicados si también se consume el esquema histórico `CuotaEmitidaEvent`, que hoy describe un agregado. |
| `PagoReportadoEvent` | CON-22/70 / CON-34 | Esquema ausente; definir identificadores de comprobante, unidad y contexto, estado de recepción y datos mínimos. |
| `PagoConciliadoEvent` | Resultado financiero de CON-70 / CON-34 y consumidores financieros acordados | Esquema plano existente; acordar adaptación al envelope, estado y datos financieros confirmados. Evitar aplicar el pago otra vez al consumir su notificación. |
| Resultado observado/rechazado — nombre por acordar | Revisión persistente de CON-70 / CON-34 | Definir si se usa evento común de resultado o tipos separados; incluir motivo autorizado y relación con el comprobante. |
| `ReservaConfirmadaEvent` | CON-41 / CON-36 | Esquema plano existente; contexto, costo/reglas y datos recuperables para plantilla. |
| `ReservaCanceladaEvent` | CON-46 / CON-36 | Esquema ausente; identificadores, instante confirmado y referencia al ajuste, si corresponde. |

Recomendación pendiente de aprobación: conservar nombres y `event_id` estables, añadir una versión de esquema explícita y adoptar la envoltura común con `data`. La evolución de CON-11 debe aceptar el evento existente mediante un adaptador o desplegar productor y consumidor coordinadamente. Acordar contexto de condominio, causación/correlación, campos obligatorios, formato decimal y timestamps. No declarar esquemas planos antiguos equivalentes al envelope nuevo sin convertirlos.

Reglas compartidas ya exigidas por el sprint: outbox o mecanismo durable en la transacción; publicación después del commit; entrega al menos una vez y consumo idempotente. Para notificaciones, definir una clave lógica por evento, destinatario y canal con restricción persistente. Un reintento actualiza la misma notificación, sin crear otro aviso lógico. Si un lote genera varios avisos, la clave también debe distinguir la cuota u operación individual correspondiente.

El contrato de comunicación debe distinguir registro persistido, aceptación del proveedor y entrega confirmada. Los enum finales y la evidencia de entrega quedan por acordar con Alejandro; un transporte simulado se identifica como tal. Conservar intento inicial más tres reintentos a 2, 10 y 30 minutos, con jitter documentado del primero, y recuperar el próximo intento tras reiniciar. El reenvío manual de un registro `ENTREGADO` no debe producir un nuevo envío.

## 7. Decisiones para validar antes de cambiar contratos canónicos

| Decisión | Recomendación inicial | Quién debe acordarla con Gerardo |
|---|---|---|
| D01 — Zona y horario de calendario | `America/Lima`, horas locales y conversiones explícitas a instantes UTC; intervalos `[inicio, fin)`. | Jerson, Brandon y Nicolás. |
| D02 — Catálogo, bloqueos y consulta | Conservar consulta de ocupaciones; definir horarios/bloqueos persistentes y errores de área inactiva. | Jerson y Nicolás. |
| D03 — Carga y acceso a voucher | Multipart único; unificar nombre de archivo, tamaño máximo, tipos efectivos y recuperación autorizada. | Anderson, Brandon y Nicolás. |
| D04 — Estado público del pago | Unificar en `APROBADO` y migrar el alias `CONCILIADO` del cliente de forma coordinada. | Anderson, Brandon y Nicolás/CON-74. |
| D05 — Corrección de comprobante | Definir reenvío observado/rechazado, versión del archivo y conservación del historial. | Anderson y Brandon. |
| D06 — Cancelación repetida | `200` con resultado original, sin repetir efectos; hoy es `422`. | Brandon y Nicolás. |
| D07 — Reembolso/compensación | Política explícita según cobro real y referencia contable; no inferir una devolución del cambio de estado. | Responsable financiero del flujo y Brandon/Nicolás. |
| D08 — Notificación y acceso | Distinguir aceptación/entrega, enum y filtros por UUID; definir lectura de residentes dentro de su alcance. | Alejandro, Nicolás y Jerson para permisos. |
| D09 — Versión y forma de eventos | Envelope propio versionado, compatible con el productor de CON-11, más esquemas de recepción, resultado y cancelación. | Nicolás, Anderson, Brandon y Alejandro. |
| D10 — Errores y contratos nuevos | Error raíz común y forma de detalles; rutas de vínculos, roles y administración de áreas con reglas existentes. | Cada responsable de API, con Jerson para usuarios/catálogo. |

No requieren una nueva decisión las reglas ya escritas en el sprint: cuatro roles, habilitación manual de CON-04, no afectar saldos al reportar, `202` de comprobante nuevo, `201` de reserva confirmada, bloqueo por mora, frontera de al menos 24h y persistencia/idempotencia/concurrencia. Su implementación y evidencia sí deben verificarse.

Gerardo puede preparar las correcciones de coherencia sobre acuerdos vigentes: ejemplos con UUID y nombres reales del DTO, descripción completa de campos existentes, retirada de referencias históricas a invitaciones y alineación documental de `>= 24h`. Las opciones D01–D10 sí cambian o completan interfaces o reglas compartidas; se validan con los responsables indicados antes de publicarlas como canónicas. En ambos casos, esta etapa entrega la propuesta para su revisión antes de editar esas fuentes.

## 8. Orden de trabajo y verificaciones de aceptación de CON-72

1. Revisar D01/D02/D06/D07 con el equipo de reservas; acordar el DTO de disponibilidad y el repositorio con Nicolás. Esto permite iniciar CON-40 y preparar CON-46 sin esperar el cierre de todas las historias.
2. Resolver D03/D04/D05 con Anderson y Brandon para completar el reporte de archivo, las respuestas de deduplicación y el productor de resultados de CON-70.
3. Completar D08/D09 con Alejandro y Nicolás; preservar CON-11 y asignar cada esquema/evento a una operación confirmada. Confirmar con Jerson D10 y las mutaciones de vínculos/roles.
4. Después de aprobar los acuerdos, actualizar en el mismo cambio coordinado las fuentes canónicas afectadas: dominio/proceso, OpenAPI, API narrativa, DTO, cliente, esquemas y ejemplos. Actualizar también los BDD relacionados antes de solicitar revisión de implementación.
5. Integrar progresivamente los recorridos persistentes con CON-70/73/74 y reunir la evidencia de CON-75. Mantener este diagnóstico como registro de diferencias resueltas/pendientes, identificando el PR que implementa cada acuerdo.

| Verificación a preparar después de aprobar | Resultado exigido / quién aporta evidencia |
|---|---|
| YAML, referencias locales y ejemplos de request/response | OpenAPI válido y ejemplos que cumplan esquemas; ejemplos con UUID y decimales correctos. Gerardo. |
| YAML frente al OpenAPI generado | Comparación de métodos, rutas, parámetros, cuerpos, respuestas y seguridad de las operaciones del sprint; excepciones documentadas, sin confundir cobertura de rutas con conformidad. Gerardo/Alejandro. |
| API y frontend | Tipos/campos compartidos y pruebas de respuestas de éxito y error; ninguna URL inventada ni éxito simulado. Responsables funcionales y Nicolás. |
| Disponibilidad y cancelación | Dos sesiones ven los mismos intervalos; otras reservas ocupan sin revelar identidad; cancelación libera tras commit y sobrevive a reinicio; frontera exacta de 24h. Gerardo y Nicolás. |
| Autorización | Residente, auditor y administración; unidad ajena, cruce de condominios, vínculo revocado, sesión obsoleta y `es_admin` falsificado. Jerson y responsables. |
| Pagos y solvencia | Archivo real, reintentos equivalentes, carreras SQL, resultados observado/rechazado/aprobado y ausencia de efecto financiero al reportar. Anderson y Brandon. |
| Eventos | Payload por esquema, publicación tras commit, recuperación del outbox, reentrega sin duplicar efectos y compatibilidad con CON-11. Productores, Alejandro y Nicolás. |
| Notificaciones | Intentos y próximo reintento persistidos, aceptación separada de entrega y ningún reenvío ya entregado. Alejandro y Nicolás. |
| Cierre CON-72 | Decisiones registradas, contratos canónicos alineados, validaciones automatizadas pasando y revisión de otro integrante; este documento por sí solo no cierra la entrega. Gerardo. |

### Evidencia de esta etapa de análisis

- `git pull --ff-only origin develop`: sin cambios remotos pendientes al crear la rama. La base local conserva la integración de `main` ya realizada.
- Generación de `app.openapi()` sin iniciar servidor ni conexión de negocio: 38 operaciones; comparación normalizada con el YAML: 38, sin rutas exclusivas de una fuente.
- Revisión de los cinco JSON Schema de eventos: únicamente `cuotas-emitidas.schema.json` declara la envoltura con `data` en esta base. No existen todavía esquemas de pago reportado ni reserva cancelada.
- Inspección de routers/DTO/cliente y fuentes enlazadas para H01–H15. Los hallazgos describen el código revisado; no equivalen a pruebas funcionales del flujo completo.
- Verificador estático SDD del repositorio: correcto. Validación documental: enlaces locales existentes, bloques Markdown cerrados, inventario de 15 HU, 15 hallazgos, 10 decisiones y ejemplos JSON legibles; YAML y esquemas JSON existentes también legibles. `git diff --check` sin errores.
- La revisión de reglas y contratos termina aquí. Las decisiones D01–D10 quedan pendientes de validación; no se crean endpoints ni se cambian reglas de negocio con este diagnóstico.
