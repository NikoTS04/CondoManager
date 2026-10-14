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

- CON-10 persiste una configuración vigente por condominio, con `metodo` igual a
  `POR_ALICUOTA` o `EQUITATIVA`, actor y fecha UTC de la última modificación.
  CON-11 lee esta configuración al emitir el periodo; CON-10 no mantiene versiones
  por periodo ni modifica lotes ya emitidos.
- `POR_ALICUOTA` exige al menos un departamento y la suma exacta de sus coeficientes
  `Decimal` igual a `100.0000`, sin tolerancia ni redondeo previo de la suma.
  `99.9999` y `100.0001` se rechazan. Cada coeficiente debe ser finito,
  ser mayor que cero y menor o igual a cien y tener como máximo cuatro decimales.
- Se consideran todos los departamentos del condominio mientras CON-3 no integre
  el campo de actividad. Este criterio queda aislado en
  `listar_departamentos_para_distribucion` del repositorio.
- El PUT valida antes de persistir. Los errores `DISTRIBUCION_SIN_DEPARTAMENTOS`
  y `DISTRIBUCION_COEFICIENTES_INVALIDOS` devuelven `422` con mensaje explicativo.
  CON-11 debe revalidar los departamentos actuales antes de usar la configuración.
- Escritura para `SUPERADMIN` y `ADMIN_JUNTA`; lectura también para `AUDITOR`.
  Salvo `SUPERADMIN`, el condominio debe coincidir con el claim del JWT.
- Cada cambio genera auditoría de siete campos, estados anterior/posterior y hash
  encadenado en la misma transacción. Repetir el mismo PUT válido conserva el
  identificador, actor, fecha y auditoría anteriores.
- El cálculo puro `calcular_distribucion` devuelve montos por identificador con
  `Decimal` y `ROUND_HALF_UP` a dos posiciones, sin usar `float`.
  La suma individual puede diferir del presupuesto por centavos: el cierre exacto
  y el ajuste residual determinista del lote pertenecen exclusivamente a CON-11.

### 3.4 Modalidad Cuota Fija Equitativa
$$\text{Cuota}(u) = \text{round\_half\_up}\left(\frac{\text{PresupuestoTotal}}{N_{\text{unidades}}}, 2\right)$$

- `EQUITATIVA` exige al menos un departamento y no utiliza sus coeficientes.
- La selección y revalidación usan el mismo conjunto de departamentos que alícuota.
- El presupuesto del cálculo debe ser un `Decimal` finito no negativo; los
  identificadores de departamentos no pueden repetirse. La función no consulta
  persistencia, no aplica saldos a favor ni ajusta centavos residuales.

### 3.5 Amortización con Saldo a Favor
- CON-13 aplica el crédito **después** de fijar el bruto definitivo, incluido el
  ajuste de centavos de CON-11. Solo acepta `Decimal` finitos, no negativos,
  redondeados a dos posiciones mediante `ROUND_HALF_UP`.
- `aplicado = min(monto_cuota, saldo_disponible)`;
  `pendiente = monto_cuota - aplicado`; `saldo_restante = saldo_disponible - aplicado`.
- El crédito es un **pago**, no un descuento: `monto_total_exigible` conserva el
  bruto, `monto_pagado = aplicado` y `monto_descuento = 0.00`. El neto pendiente
  se consulta como `monto_total_exigible - monto_pagado`.
- Si el pendiente es cero queda `PAGADA` (también una cuota de bruto cero);
  en otro caso queda `PENDIENTE`, incluso con saldo cero o aplicación parcial.
- Esta decisión sigue `AMORTIZAR_TOTAL` de la máquina de estados y el escenario
  de liquidación de `cuotas.feature`: evita contabilizar dos veces el crédito,
  respeta el CHECK de pagos y conserva el total bruto distribuido del presupuesto.
- La aplicación persiste en `aplicaciones_saldo_favor`, con `UNIQUE(cuota_id)`.
  Incluso el saldo cero genera un registro: un reintento devuelve la aplicación
  original sin consumir créditos posteriores ni duplicar auditorías.
- Se bloquea primero el condominio, luego el departamento y finalmente la cuota
  con `SELECT FOR UPDATE`. El bloqueo del condominio serializa la lectura del
  último hash y la escritura de auditoría, incluso entre departamentos distintos,
  y comparte el orden de CON-9/CON-10 para conservar una cadena lineal;
  se releen los valores bajo bloqueo. Cuota, saldo, aplicación y auditoría de siete
  campos (con actor, saldo previo, aplicado, restante y estados) se guardan juntos.
- Contrato CON-11: dentro de `async with session.begin()`, crear y hacer `flush`
  de la cuota `EMITIDA`, sin pagos ni descuentos, con bruto definitivo, y llamar
  `SaldosFavorService(SQLAlchemySaldoFavorRepository(session)).aplicar_a_cuota_emitida(cuota, actor)`.
  El servicio usa un savepoint, nunca hace `commit` y exige transacción externa;
  cualquier fallo del lote debe revertir la transacción completa. En lotes se
  procesa por ID de departamento ascendente para conservar el orden de bloqueos.
  Es un contrato interno, no agrega endpoint ni sustituye la emisión persistente.
- La migración `20261014_0004` crea la aplicación sin FK a cuotas porque esa tabla
  todavía pertenece a CON-11. La migración de CON-11 que cree `cuotas_mantenimiento`
  debe añadir `fk_aplicacion_saldo_cuota` (`cuota_id` → `cuotas_mantenimiento.id`,
  `ON DELETE RESTRICT`). El ORM conserva la FK; UNIQUE y CHECKs ya se aplican.

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
