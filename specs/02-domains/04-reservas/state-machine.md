# Máquina de Estados: Reserva de Área Común

Base vigente: [CON-72](../../05-api/sprint-2-contratos.md#4-catálogo-disponibilidad-y-reservas). `SOLICITADA`/`RECHAZADA` del diagrama representan decisiones internas de la nueva creación: un intento fallido no crea una reserva persistida ni ocupa el turno. La creación pública devuelve únicamente `CONFIRMADA`; el listado puede conservar también estados históricos `SOLICITADA`/`RECHAZADA` ya existentes, sin borrarlos ni convertirlos en una reserva vigente.

```
     [ Residente solicita reserva ]
                   │
                   ▼
            [ SOLICITADA ]
                   │
          ┌────────┴──────────────────────────┐
   (Solvente + Disponible)       (Deuda vencida O Horario ocupado)
          ▼                                   ▼
    [ CONFIRMADA ]                      [ RECHAZADA ]
          │                         - Motivo: "MORA_ACTIVA"
     ┌────┴────────┐                - Motivo: "HORARIO_OCUPADO"
     ▼             ▼
[ COMPLETADA ] [ CANCELADA ]
```

## Tabla de Transiciones de la Reserva

| Estado Origen | Evento | Estado Destino | Guardas / Precondiciones | Acciones / Efectos |
| :--- | :--- | :--- | :--- | :--- |
| `[NULL]` | `SOLICITAR_RESERVA` | `SOLICITADA` | Usuario autenticado vinculado a departamento. | Inicia transacción pesimista. |
| `SOLICITADA` | `CONFIRMAR_RESERVA` | `CONFIRMADA` | `deuda_en_mora == 0.00` Y horario libre con bloqueo pesimista. | Registra reserva, descuenta cupo, emite `ReservaConfirmadaEvent`. |
| `SOLICITADA` | `RECHAZAR_POR_MORA` | `RECHAZADA` | `deuda_en_mora > 0.00` | Aborta transacción con código HTTP 403, emite log de auditoría. |
| `SOLICITADA` | `RECHAZAR_POR_CONFLICTO` | `RECHAZADA` | Horario se solapa con reserva confirmada existente. | Aborta transacción con código HTTP 409, informa al usuario. |
| `CONFIRMADA` | `CANCELAR_RESERVA` | `CANCELADA` | Residente con >= 24h de anticipación en America/Lima, o administración autorizada del contexto. | Guarda fecha, actor y motivo; libera tras commit; auditoría y `ReservaCanceladaEvent`; ajuste según cobro acreditado. |
| `CANCELADA` | `CANCELAR_RESERVA` | `CANCELADA` | Solicitante autorizado. | Devuelve `200` y resultado original, sin otro evento ni compensación. |
| `CONFIRMADA` | `EXPIRAR_USO` | `COMPLETADA` | `fecha_actual > fecha_reserva + hora_fin` | Cierra ciclo de la reserva. |

El ajuste distingue `NO_APLICA`, `PENDIENTE` y `APLICADO`; cancelar no acredita por sí solo una devolución. La tarifa de la reserva no demuestra que exista un cobro. Un estado no cancelable responde `422 ESTADO_RESERVA_INVALIDO`; el campo cliente `es_admin` se ignora.
