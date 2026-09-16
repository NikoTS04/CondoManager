# Máquinas de Estados y Transiciones del Sistema (State Machines)

## 1. Máquina de Estados: Cuota de Mantenimiento (`cuotas_mantenimiento`)

```
               [ INICIO: Generación mensual ]
                              │
                              ▼
                        [ EMITIDA ]
                              │
               ┌──────────────┴──────────────┐
  (Tiene saldo a favor total)        (Saldo a pagar > 0)
               ▼                             ▼
          [ PAGADA ]                   [ PENDIENTE ]
               ▲                             │
               │ (Pago total aprobado)       ▼ (Llega fecha_vencimiento)
               ├────────────────────── [ VENCIDA ]
               │                             │
               │                             ▼ (Supera dias_gracia)
               ├────────────────────── [ EN_MORA ]
               │                             │
               │ (Abona parte del total)     ▼
               └────────────────────── [ PAGO_PARCIAL ]
```

### Tabla de Transiciones Legales:
| Estado Origen | Evento Disparador | Estado Destino | Pre-condiciones / Reglas |
| :--- | :--- | :--- | :--- |
| `NULL` | `GENERAR_CUOTA_MES` | `EMITIDA` | Presupuesto activo aprobado. |
| `EMITIDA` | `CONSUMIR_SALDO_FAVOR` | `PAGADA` | Saldo a favor $\ge$ Monto emitido. |
| `EMITIDA` | `PUBLICAR_A_RESIDENTES`| `PENDIENTE`| Saldo exigible $> 0$. |
| `PENDIENTE` | `LLEGAR_FECHA_CORTE` | `VENCIDA` | Fecha actual $>$ Fecha de vencimiento. |
| `VENCIDA` | `EXPIRAR_DIAS_GRACIA` | `EN_MORA` | No hay pago reportado en revisión. Aplica recargo de mora. |
| `PENDIENTE`/`VENCIDA`/`EN_MORA` | `APROBAR_PAGO_TOTAL` | `PAGADA` | Monto imputado cubre el 100% de la deuda. |
| `PENDIENTE`/`VENCIDA`/`EN_MORA` | `APROBAR_PAGO_PARCIAL`| `PAGO_PARCIAL`| Monto imputado cubre parte de la deuda. Saldo pendiente $> 0$. |

---

## 2. Máquina de Estados: Comprobante de Pago (`comprobantes_pago`)

```
   [ Residente envía comprobante ]
                 │
                 ▼
          [ EN_REVISION ]
                 │
        ┌────────┴────────┐
        ▼                 ▼
   [ APROBADO ]      [ RECHAZADO ]
        │             (Requiere motivo obligatorio)
        ▼
   [ IMPUTADO ]
(Distribución a cuotas)
```

---

## 3. Máquina de Estados: Reserva de Área Común (`reservas`)

```
     [ Residente solicita reserva ]
                   │
                   ▼
            [ SOLICITADA ]
                   │
          ┌────────┴────────┐
   (Solvente + Disponible) (Deuda vencida O Conflicto horario)
          ▼                 ▼
    [ CONFIRMADA ]    [ RECHAZADA ]
          │
     ┌────┴────────┐
     ▼             ▼
[ COMPLETADA ] [ CANCELADA ]
```

### Invariante Crítica:
- No es posible realizar una transición de `SOLICITADA` a `CONFIRMADA` si la consulta `SELECT COUNT(*) FROM cuotas_mantenimiento WHERE departamento_id = :id AND estado = 'EN_MORA'` es mayor a cero, a menos que exista un token de autorización forzada por la Junta Directiva.
