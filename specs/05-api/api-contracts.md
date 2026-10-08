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

### 2.1 Módulo de Condominios (CON-2 / PROC-05)

Todos los endpoints de esta sección requieren `Authorization: Bearer <token>` y rol
global `SUPERADMIN`. La ausencia de credenciales responde `401 NO_AUTENTICADO`; un rol
distinto responde `403 ACCESO_DENEGADO`.

- **`POST /api/v1/condominios`**
  - *Descripción:* Crea la raíz persistente de un nuevo contexto multi-condominio y
    registra la auditoría `CONDOMINIO_CREADO` en la misma transacción.
  - *Request Body:*
    ```json
    {
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Principal 123, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 20,
      "dias_gracia": 2
    }
    ```
  - *Reglas condicionales:*
    - `MONTO_FIJO`: `monto_mora_fijo` es obligatorio y
      `tasa_mora_porcentaje` debe ser `null`.
    - `PORCENTAJE_SALDO`: `tasa_mora_porcentaje` es obligatoria y
      `monto_mora_fijo` debe ser `null`.
    - `activo`, `id` y `creado_en` son campos de servidor y se rechazan si el cliente
      intenta incluirlos.
  - *Response (201 Created):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Principal 123, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": null,
      "dia_vencimiento": 20,
      "dias_gracia": 2,
      "activo": true,
      "creado_en": "2026-10-08T15:30:00Z"
    }
    ```
  - *Response (422 Unprocessable Entity):* `DATOS_CONDOMINIO_INVALIDOS` cuando los
    campos no cumplen sus rangos o la combinación de mora es inconsistente.

- **`GET /api/v1/condominios/{condominio_id}`**
  - *Descripción:* Recupera exactamente el condominio persistido con el UUID indicado.
  - *Parámetro de ruta:* `condominio_id`, UUID obligatorio.
  - *Response (200 OK):* Mismo objeto de respuesta del alta.
  - *Response (404 Not Found):*
    ```json
    {
      "error_code": "CONDOMINIO_NO_ENCONTRADO",
      "mensaje": "No existe un condominio con el identificador solicitado.",
      "detalles": {
        "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      }
    }
    ```

### 2.2 Módulo de Cuotas (Anderson)
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

### 2.3 Módulo de Pagos y Moras (Tarqui)
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

### 2.4 Módulo de Reservas (Brandon)
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

### 2.5 Módulo de Notificaciones (Alejandro)
- **`POST /api/v1/notificaciones/despachar`**
  - *Descripción:* Envío manual o por webhook interno de comunicaciones masivas o alertas.

### 2.6 Módulo de Autenticación y RBAC (PROC-05)
- **`POST /api/v1/auth/login`**
  - *Descripción:* Autentica a un usuario y genera su token de acceso JWT con sus claims y permisos.
  - *Request Body:*
    ```json
    {
      "email": "admin@villabonita3.pe",
      "password": "Password123!"
    }
    ```
  - *Response (200 OK):*
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 3600,
      "usuario": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "email": "admin@villabonita3.pe",
        "nombre": "Carlos",
        "apellido": "Mendoza",
        "rol": "ADMIN_JUNTA",
        "condominio_id": "vb3-condo",
        "departamentos": []
      }
    }
    ```
  - *Response (401 Unauthorized):*
    ```json
    {
      "error_code": "CREDENCIALES_INVALIDAS",
      "mensaje": "Correo o contraseña incorrectos."
    }
    ```

- **`GET /api/v1/auth/me`**
  - *Descripción:* Retorna el perfil y contexto activo del usuario autenticado vía Bearer Token.
  - *Headers:* `Authorization: Bearer <token>`
  - *Response (200 OK):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "email": "residente102@villabonita3.pe",
      "nombre": "Ana",
      "apellido": "Gómez",
      "rol": "PROPIETARIO",
      "condominio_id": "vb3-condo",
      "departamentos": ["102"]
    }
    ```

