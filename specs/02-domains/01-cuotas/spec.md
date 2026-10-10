# Dominio 01: Presupuestos, Cuotas de Mantenimiento y Alícuotas

## 1. Ficha del Dominio
- **Identificador:** DOM-01 / PROC-01
- **Responsables:** **Anderson** (cuotas) / **Gerardo** (CON-9 presupuesto)
- **Estado:** Aprobado para Implementación
- **Versión:** 2.1 (CON-9 especificado)
- **Módulos de Código:** `src/modules/cuotas/`

---

## 2. Propósito y Límites del Dominio
El dominio de Cuotas de Mantenimiento es responsable de:
1. Almacenar el presupuesto operativo mensual aprobado por asamblea para cada condominio.
2. Calcular la alícuota de cada unidad según su coeficiente de participación inmobiliaria o modalidad fija.
3. Emitir el lote de cuotas mensual el día 1 de cada mes de forma automatizada.
4. Aplicar los saldos a favor existentes amortizando o liquidando las cuotas emitidas.
5. Gestionar el ciclo de vida de la obligación financiera (`EMITIDA` $\rightarrow$ `PENDIENTE` $\rightarrow$ `PAGADA` / `VENCIDA`).

---

## 3. Fórmulas Matemáticas y Reglas de Negocio

### 3.1 Presupuesto mensual ordinario (CON-9)

- Cada condominio puede tener un único presupuesto ordinario por periodo. La
  unicidad se define por `(condominio_id, periodo)`.
- El periodo usa el formato estricto `YYYY-MM`, con un mes entre `01` y `12`.
- `monto_total` es un decimal positivo de dos posiciones, se persiste como
  `NUMERIC(12,2)` y se intercambia por API como cadena.
- `moneda` solo puede ser `PEN` o `USD` y debe coincidir con la moneda configurada
  en el condominio.
- `fecha_vencimiento` debe pertenecer al mismo mes indicado por `periodo`.
- Todo presupuesto nace en `BORRADOR`. Mientras permanezca en ese estado puede
  reemplazarse mediante `PUT`; el `condominio_id` y el `id` son inmutables.
- La única transición de estado válida es `BORRADOR -> APROBADO`. La aprobación
  registra el claim `sub` del actor en `aprobado_por` y la fecha UTC en
  `aprobado_en`; también actualiza `actualizado_en` con ese mismo instante.
- Un presupuesto `APROBADO` es inmutable. Intentar modificarlo o aprobarlo de
  nuevo responde `409`.
- Creación, modificación y aprobación generan respectivamente las auditorías
  `PRESUPUESTO_CREADO`, `PRESUPUESTO_MODIFICADO` y `PRESUPUESTO_APROBADO` dentro
  de la misma transacción que el cambio.
- CON-11 solo puede utilizar un presupuesto cuyo estado sea `APROBADO`; la
  ausencia de presupuesto o un registro en `BORRADOR` bloquea la emisión.

### 3.2 Autorización y aislamiento

- `SUPERADMIN` puede crear, modificar, aprobar y consultar presupuestos de
  cualquier condominio existente.
- `ADMIN_JUNTA` puede crear, modificar, aprobar y consultar únicamente dentro
  del `condominio_id` autorizado en su JWT.
- `AUDITOR` puede consultar únicamente dentro de su condominio y recibe `403`
  ante cualquier mutación.
- Los demás roles no pueden acceder a estos endpoints. El backend valida el
  contexto del JWT y no confía solo en el `condominio_id` enviado por el cliente.

### 3.3 Modalidad Alícuota / Coeficiente
$$\text{CuotaBruta}(u) = \text{PresupuestoTotal} \times \left( \frac{\text{Coeficiente}(u)}{100.0000} \right)$$
$$\text{CuotaRedondeada}(u) = \text{round\_half\_up}(\text{CuotaBruta}(u), 2)$$

- **Invariante de Cierre:** Al finalizar la emisión del lote, la diferencia entre la suma de todas las cuotas redondeadas y el presupuesto total no puede exceder $N \times 0.01$ soles. Si existe un descuadre por centavos residuales, el ajuste se imputa al departamento con mayor alícuota o a la cuenta de ajuste por redondeo.

### 3.4 Modalidad Cuota Fija Equitativa
$$\text{Cuota}(u) = \text{round\_half\_up}\left(\frac{\text{PresupuestoTotal}}{N_{\text{unidades}}}, 2\right)$$

### 3.5 Amortización con Saldo a Favor
Si el departamento registra un `saldo_a_favor > 0.00`:
- Si $\text{saldo\_a\_favor} \ge \text{CuotaEmitida}$:
  - La cuota pasa inmediatamente a estado `PAGADA`.
  - $\text{saldo\_a\_favor\_restante} = \text{saldo\_a\_favor} - \text{CuotaEmitida}$.
  - Se registra el movimiento de amortización en la bitácora inmutable.
- Si $\text{saldo\_a\_favor} < \text{CuotaEmitida}$:
  - La cuota pasa a estado `PENDIENTE`.
  - $\text{monto\_total\_exigible} = \text{CuotaEmitida} - \text{saldo\_a\_favor}$.
  - $\text{saldo\_a\_favor\_restante} = 0.00$.

---

## 4. Contratos de Entrada y Salida (DTOs)

### `CrearPresupuestoRequest` (Request)

```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "periodo": "2026-10",
  "moneda": "PEN",
  "monto_total": "20000.00",
  "fecha_vencimiento": "2026-10-20"
}
```

### `PresupuestoResponse` (Response)

```json
{
  "id": "c21b2dc9-b7d4-47d5-b947-90e3ea900f5c",
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "periodo": "2026-10",
  "moneda": "PEN",
  "monto_total": "20000.00",
  "fecha_vencimiento": "2026-10-20",
  "estado": "BORRADOR",
  "creado_por": "6a4a78de-c704-44fb-a8b1-9d387ff67c92",
  "creado_en": "2026-10-08T15:30:00Z",
  "aprobado_por": null,
  "aprobado_en": null,
  "actualizado_en": "2026-10-08T15:30:00Z"
}
```

### Endpoints de presupuesto

| Método y ruta | Resultado exitoso | Regla principal |
| :--- | :---: | :--- |
| `POST /api/v1/presupuestos` | `201` | Crea un `BORRADOR`. |
| `PUT /api/v1/presupuestos/{id}` | `200` | Reemplaza los datos de un borrador. |
| `POST /api/v1/presupuestos/{id}/aprobar` | `200` | Ejecuta `BORRADOR -> APROBADO`. |
| `GET /api/v1/condominios/{condominio_id}/presupuestos/{periodo}` | `200` | Consulta sin mezclar contextos. |

Todos requieren Bearer Token. Los errores contractuales son `401` por ausencia o
invalidez del token; `403` por rol o condominio no autorizado; `404` cuando no
existe el condominio o presupuesto; `409` por duplicado o transición inválida; y
`422` por datos de negocio inválidos.

### `GenerarLoteCuotasDTO` (Request)
```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "periodo": "2026-10",
  "presupuesto_total": "20000.00",
  "fecha_vencimiento": "2026-10-20"
}
```

Este es el contrato vigente de la emisión demostrativa. Al implementar CON-11,
`presupuesto_total` y `fecha_vencimiento` dejarán de ser datos libres y se
recuperarán del presupuesto `APROBADO` de CON-9 para el mismo condominio y periodo.

### `LoteCuotasResponseDTO` (Response)
```json
{
  "lote_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "periodo": "2026-10",
  "total_cuotas_emitidas": 139,
  "monto_total_facturado": "20000.00",
  "cuotas_pagadas_por_saldo_a_favor": 4,
  "fecha_emision": "2026-10-01T00:00:00Z",
  "fecha_vencimiento": "2026-10-20T23:59:59Z"
}
```

---

## 5. Eventos de Dominio Emitidos
- `CuotasEmitidasEvent`: Notifica a PROC-03 (Alejandro) para iniciar el despacho masivo de avisos de cobro por correo/WhatsApp.
