# Contratos de avisos por correo — Sprint 4 (CON-47 / CON-53 / CON-55)

Aporte de Alejandro al reparto del [Sprint 4](SPRINT-4.md): contratos de los avisos
sobre la cola existente de notificaciones, sin implementar los flujos de otros.

## Hecho

| Entregable | Ubicación |
|---|---|
| Eventos, payloads, claves de deduplicación, destinatarios y plantillas | [Catálogo de eventos](../../specs/03-contracts/events/domain-events-catalog.md) (sección «Avisos del Sprint 4») |
| Escenarios de aceptación de los tres avisos | [avisos-sprint-4.feature.md](../../specs/04-acceptance-criteria/avisos-sprint-4.feature.md) |
| Política de contacto faltante y destinatario externo | [delivery-policy.md §3.1](../../specs/02-domains/03-notificaciones/delivery-policy.md) |
| Matriz de eventos y plantillas | [spec de notificaciones](../../specs/02-domains/03-notificaciones/spec.md) |
| Contrato de lectura para Junta (resumen y estado de avisos) | [api-contracts](../../specs/05-api/api-contracts.md) |
| Plantillas `NOTIF_RESERVA_AFECTADA_BLOQUEO`, `NOTIF_INCIDENCIA_ASIGNADA_RESIDENTE`, `NOTIF_INCIDENCIA_ASIGNADA_PROVEEDOR` | `src/modules/notificaciones/templates.py` |
| Constantes y claves de deduplicación | `src/modules/notificaciones/avisos_contrato.py` |
| Pruebas | `src/tests/unit/test_avisos_contrato_sprint4.py` |

CON-53 ya estaba conectado a la cola (`encolar_aviso`, un aviso por integrante de Junta,
`evento_id` = `operacion_id` = ID de la incidencia); no requirió cambios de código.
No se crearon migraciones ni se modificó OpenAPI (los endpoints de lectura son contrato objetivo).

## Pendiente para quien implemente

- **CON-47 (Brandon):** encolar un aviso por reserva en la transacción del bloqueo con
  `clave_reserva_afectada`, exponer el resumen y tratar el titular sin contacto.
- ~~**CON-55 (Jerson):** encolar los dos avisos al confirmar la asignación con
  `clave_asignacion` y exponer `GET /incidencias/{id}/avisos`.~~ Entregado:
  `POST /incidencias/{id}/asignacion` y `GET /incidencias/{id}/avisos`.
- **Migración `20261127_0027`:** `notificaciones_logs.usuario_destinatario_id`
  pasó a nullable y se añadió `destinatario_externo_id` con unicidad que contempla
  `NULL`, de modo que el correo al proveedor externo sí se puede encolar.
  `notificaciones_alertas.notificacion_id` sigue siendo NOT NULL, por lo que
  `CONTACTO_FALTANTE` se deriva al leer y no se persiste.
- OpenAPI actualizado con los dos endpoints de CON-55; el de CON-47 sigue pendiente.

## Dudas de negocio (sin resolver; no se inventaron reglas)

1. ¿El aviso de CON-47 reemplaza el de `ReservaCanceladaEvent` de esas mismas reservas
   o se envían ambos? El contrato asume que el productor evita el duplicado, pero no está decidido.
2. ¿Qué ajuste económico corresponde a una reserva cancelada por bloqueo? El aviso no lo menciona.
3. ¿El «código del ticket» es el ID de la incidencia o habrá un código corto visible?
4. ¿Qué datos del residente puede recibir el proveedor (nombre, unidad, teléfono)? Se omitieron.
5. ¿Qué ve el residente de la asignación: responsable y plazo, o solo estado y enlace? Se asumió lo segundo.
6. ¿Quién es el «contacto» del proveedor (un único correo del directorio de CON-48 u otros)?
7. ¿Hay aviso a Junta si no existe ningún integrante activo? Hoy solo se audita `avisos_encolados: 0`.

## Verificación

`uv run --extra dev ruff check src scripts migrations`,
`uv run --extra dev python -m pytest src/tests/unit -q --no-cov` y
`python scripts/verify_sdd_compliance.py`.
