# Máquina de Estados: Reserva de Área Común

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
| `CONFIRMADA` | `CANCELAR_RESERVA` | `CANCELADA` | Solicitado por residente con > 24h de anticipación o por administrador. | Libera horario en calendario, emite nota de crédito si hubo cobro. |
| `CONFIRMADA` | `EXPIRAR_USO` | `COMPLETADA` | `fecha_actual > fecha_reserva + hora_fin` | Cierra ciclo de la reserva. |
