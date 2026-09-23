# Dominio 01: Cuotas de Mantenimiento y Alícuotas (Anderson)

## 1. Ficha del Dominio
- **Identificador:** DOM-01 / PROC-01
- **Responsable:** **Anderson**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
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

### 3.1 Modalidad Alícuota / Coeficiente
$$\text{CuotaBruta}(u) = \text{PresupuestoTotal} \times \left( \frac{\text{Coeficiente}(u)}{100.0000} \right)$$
$$\text{CuotaRedondeada}(u) = \text{round\_half\_up}(\text{CuotaBruta}(u), 2)$$

- **Invariante de Cierre:** Al finalizar la emisión del lote, la diferencia entre la suma de todas las cuotas redondeadas y el presupuesto total no puede exceder $N \times 0.01$ soles. Si existe un descuadre por centavos residuales, el ajuste se imputa al departamento con mayor alícuota o a la cuenta de ajuste por redondeo.

### 3.2 Modalidad Cuota Fija Equitativa
$$\text{Cuota}(u) = \text{round\_half\_up}\left(\frac{\text{PresupuestoTotal}}{N_{\text{unidades}}}, 2\right)$$

### 3.3 Amortización con Saldo a Favor
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

### `GenerarLoteCuotasDTO` (Request)
```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "periodo": "2026-10",
  "presupuesto_total": "20000.00",
  "fecha_vencimiento": "2026-10-20"
}
```

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
