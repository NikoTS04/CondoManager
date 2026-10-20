# Dominio 02: Pagos, Conciliación Bancaria y Motor de Moras (Tarqui)

## 1. Ficha del Dominio
- **Identificador:** DOM-02 / PROC-02
- **Responsable:** **Tarqui**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/pagos/`

---

## 2. Propósito y Límites del Dominio
El dominio de Pagos y Moras es responsable de:
1. Recibir, validar e indexar comprobantes de pago subidos por los residentes (Yape, Plin, transferencias CCI).
2. Garantizar la idempotencia estricta para evitar la reutilización fraudulenta o accidental de vouchers bancarios.
3. Proveer la interfaz y lógica para la bandeja de conciliación de la Junta Directiva (Aprobar / Observar / Rechazar).
4. Ejecutar el algoritmo contable de imputación de fondos en orden de prelación.
5. Gestionar el motor nocturno de moras automáticas tras expirar el periodo de gracia.

---

## 3. Algoritmo de Imputación de Pagos (Orden de Prelación)

Cuando un pago por un importe $P$ es aprobado por la Junta Directiva, los fondos se asignan en riguroso orden secuencial:

$$\mathbf{Paso\ 1:} \text{Imputar a penalidades y moras acumuladas más antiguas.}$$
$$\mathbf{Paso\ 2:} \text{Imputar a cuotas extraordinarias vencidas más antiguas.}$$
$$\mathbf{Paso\ 3:} \text{Imputar a cuotas ordinarias vencidas más antiguas.}$$
$$\mathbf{Paso\ 4:} \text{Imputar a la cuota ordinaria del periodo en curso.}$$
$$\mathbf{Paso\ 5:} \text{Si existe remanente } R > 0.00 \implies \text{departamento.saldo\_a\_favor} += R.$$

---

## 4. Motor de Moras y Reglas de Corte

- **Cron de Corte:** Se ejecuta diariamente a las `00:01:00 UTC`.
- **Condición de Aplicación:**
  ```python
  hoy > cuota.fecha_vencimiento + timedelta(days=condominio.dias_gracia)
  and cuota.estado in ["PENDIENTE", "PAGO_PARCIAL"]
  and not cuota.tiene_comprobante_en_revision
  ```
- **Postergación Protectora:** Si el residente cargó un comprobante que aún se encuentra `EN_REVISION` en la bandeja del administrador, la mora se congela automáticamente por 24 horas para no castigar al residente por retrasos en la validación humana de la junta.
- **Efecto Inmediato:** Al aplicarse la mora:
  1. Se genera un registro de recargo por mora.
  2. El departamento adquiere la marca `estado_financiero = 'EN_MORA'`.
  3. Queda automáticamente inhabilitado para reservar áreas comunes (Invariante PROC-04).
  4. Se despacha el evento `MoraAplicadaEvent` a PROC-03 (Alejandro).

---

## 5. Contratos DTO Principales

### `ReportarPagoDTO` (Request Multipart)
Contrato objetivo, subida privada y estados HTTP: [CON-72](../../05-api/sprint-2-contratos.md#5-pagos--anderson-y-brandon-persistencia-con-70). Su adopción en los routers/DTO y el frontend corresponde a CON-22/23/70/74.

- `departamento_id`: UUID
- `banco`: `"YAPE"` | `"PLIN"` | `"BCP"` | `"INTERBANK"` | `"BBVA"` | `"SCOTIABANK"`
- `numero_operacion`: String(min=1, max=50); normalización canónica antes del hash.
- `fecha_operacion`: Date
- `monto`: cadena decimal positiva de dos posiciones, precision=12, scale=2.
- `archivo_voucher`: Binary (PNG/JPEG/PDF), hasta 5 MiB; contenido validado y almacenamiento privado.

Estado público/persistido: `EN_REVISION`, `APROBADO`, `OBSERVADO`, `RECHAZADO`. No transformar `APROBADO` a `CONCILIADO` al construir el listado del contrato objetivo. El resultado aprobado ya incorpora sus efectos financieros antes de publicar el evento; un consumidor no vuelve a imputar el mismo pago.

### `ConciliarPagoDTO` (Request JSON de Administrador)
```json
{
  "comprobante_id": "7b8a1c9e-1234-4567-89ab-cdef01234567",
  "decision": "APROBADO",
  "motivo_rechazo": null,
  "notas_internas": "Verificado con extracto de cuenta corriente BCP"
}
```
