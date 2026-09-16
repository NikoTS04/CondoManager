# Contratos de API y Especificación OpenAPI (API Contracts)

## 1. Filosofía de Contratos en SDD

En el Desarrollo Guiado por Especificaciones (SDD), los contratos de API sirven como el **acuerdo formal desacoplado** entre el Frontend (Next.js/TypeScript) y el Backend (FastAPI/Python), así como entre los diferentes módulos desarrollados por los integrantes del equipo (Anderson, Tarqui, Alejandro, Brandon).

Todas las peticiones y respuestas siguen el estándar **JSON:API / REST** con las siguientes convenciones:
- **Prefijo base:** `/api/v1`
- **Formatos de fecha:** ISO-8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`)
- **Formatos monetarios:** Cadenas de texto o números decimales con 2 dígitos (`"150.00"` / `150.00`) validados estrictamente por Pydantic.
- **Manejo de errores estándar:**
  ```json
  {
    "error_code": "DEUDA_MORA_ACTIVA",
    "mensaje": "Su departamento mantiene cuotas vencidas pendientes. Regularice su situación antes de reservar.",
    "detalles": {
      "departamento_id": "dpto-501",
      "saldo_vencido": "170.00"
    }
  }
  ```

---

## 2. Contratos Principales por Módulo

### 2.1 Módulo de Cuotas (Anderson)
- **`POST /api/v1/cuotas/emitir-lote`**
  - *Descripción:* Genera las cuotas del mes para todas las unidades activas del condominio.
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "periodo": "2026-10",
      "presupuesto_total": "20000.00",
      "fecha_vencimiento": "2026-10-20"
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "cuotas_generadas": 139,
      "total_emitido": "20000.00",
      "periodo": "2026-10",
      "estado": "EMITIDAS"
    }
    ```

### 2.2 Módulo de Pagos y Moras (Tarqui)
- **`POST /api/v1/pagos/reportar`**
  - *Descripción:* El residente carga un comprobante de pago bancario (Yape/CCI).
  - *Request Body (Multipart/Form-Data):*
    - `departamento_id`: UUID
    - `banco_origen`: `"BCP"` | `"INTERBANK"` | `"BBVA"` | `"YAPE"` | `"PLIN"`
    - `numero_operacion`: `"00984123"`
    - `fecha_operacion`: `"2026-10-15"`
    - `monto`: `"170.00"`
    - `archivo_voucher`: File (PNG / JPG / PDF)
  - *Response (202 Accepted):*
    ```json
    {
      "comprobante_id": "7b8a1c9e-1234-4567-89ab-cdef01234567",
      "estado": "EN_REVISION",
      "mensaje": "Comprobante recibido. En proceso de conciliación por la Junta Directiva."
    }
    ```

- **`POST /api/v1/pagos/{id}/conciliar`**
  - *Descripción:* La Junta aprueba o rechaza el comprobante.
  - *Request Body:*
    ```json
    {
      "decision": "APROBADO",
      "motivo_rechazo": null,
      "notas_internas": "Validado en extracto de cuenta BCP"
    }
    ```
  - *Response (200 OK):* Retorna la liquidación e imputación a cuotas y el nuevo saldo del departamento.

### 2.3 Módulo de Reservas (Brandon)
- **`POST /api/v1/reservas`**
  - *Descripción:* El residente solicita el uso de un área común.
  - *Request Body:*
    ```json
    {
      "area_id": "parrilla-01",
      "departamento_id": "dpto-302",
      "fecha": "2026-10-25",
      "hora_inicio": "19:00",
      "hora_fin": "22:00"
    }
    ```
  - *Response (201 Created) - Residente Solvente:*
    ```json
    {
      "reserva_id": "res-9988-aabb",
      "estado": "CONFIRMADA",
      "area": "Zona de Parrilla 1",
      "fecha": "2026-10-25",
      "horario": "19:00 - 22:00"
    }
    ```
  - *Response (403 Forbidden) - Residente con Deuda en Mora:*
    ```json
    {
      "error_code": "DEUDA_MORA_ACTIVA",
      "mensaje": "No es posible reservar: Su departamento mantiene cuotas vencidas pendientes."
    }
    ```
  - *Response (409 Conflict) - Horario Ocupado:*
    ```json
    {
      "error_code": "HORARIO_NO_DISPONIBLE",
      "mensaje": "El área común ya se encuentra reservada en el horario solicitado."
    }
    ```

### 2.4 Módulo de Notificaciones (Alejandro)
- **`POST /api/v1/notificaciones/despachar`**
  - *Descripción:* Envío manual o por webhook interno de comunicaciones masivas o alertas.
