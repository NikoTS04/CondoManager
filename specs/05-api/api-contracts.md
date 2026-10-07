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
Todos los datos de este módulo se persisten en PostgreSQL (`areas_comunes`, `departamentos`, `reservas`).

- **`GET /api/v1/areas`**
  - *Descripción:* Catálogo de áreas comunes activas del condominio.
  - *Response (200 OK):*
    ```json
    [
      {
        "id": "11111111-1111-1111-1111-111111111101",
        "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "nombre": "Zona de Parrilla 1",
        "descripcion": "Terraza piso 15",
        "aforo_maximo": 12,
        "costo_reserva": "25.00",
        "esta_activa": true
      }
    ]
    ```
  - *Nota:* Retorna `[]` si todavía no existen áreas dadas de alta en el condominio.

- **`POST /api/v1/areas/crear`**
  - *Descripción:* Alta de un área común en el catálogo (valida condominio existente y nombre único por condominio).
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "nombre": "Zona de Parrilla 1",
      "descripcion": "Terraza piso 15 con parrilla de acero inoxidable",
      "aforo_maximo": 12,
      "costo_reserva": "25.00",
      "esta_activa": true
    }
    ```
  - *Response (201 Created):* El objeto `AreaComunDTO` recién creado.
  - *Response (404 Not Found):* `CONDOMINIO_NO_ENCONTRADO`.
  - *Response (409 Conflict):* `AREA_DUPLICADA` cuando el nombre ya existe en ese condominio.
  - *Response (422 Unprocessable Entity):* validaciones de `aforo_maximo > 0`, `costo_reserva >= 0`, longitud de `nombre`.

- **`GET /api/v1/reservas`**
  - *Descripción:* Horarios ocupados de un área común (solo reservas `CONFIRMADA`).
  - *Query params:* `area_id` (UUID, obligatorio), `fecha` (`YYYY-MM-DD`, opcional).
  - *Response (200 OK):* Lista de `ReservaResponseDTO`.
  - *Response (404 Not Found):* `AREA_NO_ENCONTRADA`.

- **`POST /api/v1/reservas`**
  - *Descripción:* El residente solicita el uso de un área común. Se bloquea la fila del área (`FOR UPDATE`), se valida la solvencia y la disponibilidad.
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "area_id": "11111111-1111-1111-1111-111111111101",
      "departamento_id": "302",
      "fecha_reserva": "2026-10-25",
      "hora_inicio": "19:00",
      "hora_fin": "22:00"
    }
    ```
    - `condominio_id`: informativo (la fuente de verdad es el condominio del área).
    - `departamento_id`: UUID **o** número de departamento (ej. `"302"`).
  - *Response (201 Created) - Residente Solvente:*
    ```json
    {
      "id": "e4f5a6b7-8c9d-4e0f-1a2b-3c4d5e6f7a8b",
      "estado": "CONFIRMADA",
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "area_id": "11111111-1111-1111-1111-111111111101",
      "area_nombre": "Zona de Parrilla 1",
      "departamento_id": "0b1e2c3d-4f5a-6b7c-8d9e-0f1a2b3c4d5e",
      "fecha_reserva": "2026-10-25",
      "hora_inicio": "19:00:00",
      "hora_fin": "22:00:00",
      "costo_reserva": "25.00",
      "creado_en": "2026-10-07T20:30:00+00:00"
    }
    ```
  - *Response (403 Forbidden) - Residente con Deuda en Mora:*
    ```json
    {
      "error_code": "DEUDA_MORA_ACTIVA",
      "mensaje": "No es posible reservar: El departamento '...' mantiene cuotas vencidas pendientes en mora.",
      "detalles": {"departamento_id": "...", "saldo_vencido": "170.00"}
    }
    ```
    El bloqueo se decide con `departamentos.estado_financiero = 'EN_MORA'`.
  - *Response (404 Not Found):* `AREA_NO_ENCONTRADA` o `DEPARTAMENTO_NO_ENCONTRADO`.
  - *Response (409 Conflict) - Horario Ocupado:*
    ```json
    {
      "error_code": "HORARIO_NO_DISPONIBLE",
      "mensaje": "El área común ya se encuentra reservada en el horario solicitado."
    }
    ```
  - *Response (400 Bad Request):* `HORARIO_INVALIDO` (`hora_fin <= hora_inicio`) o `AREA_INACTIVA`.
  - *Response (422 Unprocessable Entity):* `DEPARTAMENTO_NO_PERTENECE_AL_CONDOMINIO`.

- **`POST /api/v1/reservas/{reserva_id}/cancelar`**
  - *Descripción:* Cancela una reserva confirmada y libera la franja. Residente: mínimo 24 h de anticipación; administrador (`es_admin`): sin restricción de horario.
  - *Request Body:*
    ```json
    { "motivo": "Cambio de planes del residente", "es_admin": false }
    ```
  - *Response (200 OK):*
    ```json
    {
      "id": "e4f5a6b7-8c9d-4e0f-1a2b-3c4d5e6f7a8b",
      "estado": "CANCELADA",
      "mensaje": "Reserva cancelada exitosamente. Motivo: Cambio de planes del residente",
      "fecha_cancelacion": "2026-10-07T20:30:00+00:00"
    }
    ```
  - *Response (404 Not Found):* `RESERVA_NO_ENCONTRADA`.
  - *Response (422 Unprocessable Entity):* `CANCELACION_NO_PERMITIDA` (ya cancelada, estado no `CONFIRMADA` o sin las 24 h de anticipación).

### 2.4 Módulo de Notificaciones (Alejandro)
- **`POST /api/v1/notificaciones/despachar`**
  - *Descripción:* Envío manual o por webhook interno de comunicaciones masivas o alertas.

### 2.5 Módulo de Usuarios y RBAC (Junta Directiva / PROC-05)
- **`POST /api/v1/usuario/crear`**
  - *Descripción:* Da de alta un usuario en el directorio validando la unicidad del correo y almacenando la contraseña únicamente como hash irreversible.
  - *Request Body:*
    ```json
    {
      "email": "residente101@gmail.com",
      "password": "claveSegura123",
      "nombre": "María",
      "apellido": "Flores",
      "documento_identidad": "74125896",
      "telefono": "987654321"
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "email": "residente101@gmail.com",
      "nombre": "María",
      "apellido": "Flores",
      "telefono": "987654321",
      "documento_identidad": "74125896",
      "esta_activo": true,
      "creado_en": "2026-10-07T06:00:00Z"
    }
    ```
  - *Response (409 Conflict):* `EMAIL_YA_REGISTRADO` cuando el correo ya existe en el directorio.
  - *Nota:* Nunca se expone `password_hash` en la respuesta.

- **`POST /api/v1/usuario/roles`**
  - *Descripción:* Asigna un rol RBAC contextual (`SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`) a un usuario dentro de un condominio.
  - *Request Body:*
    ```json
    {
      "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
      "rol": "RESIDENTE"
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
      "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
      "rol": "RESIDENTE"
    }
    ```
  - *Response (404 Not Found):* `USUARIO_NO_ENCONTRADO` o `CONDOMINIO_NO_ENCONTRADO`.
  - *Response (409 Conflict):* `ROL_YA_ASIGNADO` por la unicidad `uq_usuario_condo_rol`.

### 2.6 Módulo de Condominios
- **`POST /api/v1/condominio/crear`**
  - *Descripción:* Da de alta un condominio con su parametrización de mora (regla, monto/tasa, día de corte y días de gracia) usando precisión decimal estricta.
  - *Request Body:*
    ```json
    {
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Los Rosales 245, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": "0.0000",
      "dias_corte": 20,
      "dias_gracia": 2
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa9",
      "nombre": "Villa Bonita 3",
      "direccion": "Av. Los Rosales 245, Lima",
      "moneda": "PEN",
      "regla_mora_tipo": "MONTO_FIJO",
      "monto_mora_fijo": "20.00",
      "tasa_mora_porcentaje": "0.0000",
      "dias_corte": 20,
      "dias_gracia": 2,
      "creado_en": "2026-10-07T06:00:00Z"
    }
    ```
  - *Response (422 Unprocessable Entity):* `CONFIGURACION_MORA_INVALIDA` cuando la regla de mora no es coherente con sus parámetros (ej. `MONTO_FIJO` sin monto mayor a 0.00).

- **`POST /api/v1/departamentos/crear`**
  - *Descripción:* Da de alta una unidad inmobiliaria dentro de un condominio. El par `(condominio_id, numero)` es único y `estado_financiero` es la fuente que usa el dominio de Reservas para la invariante de solvencia.
  - *Request Body:*
    ```json
    {
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "numero": "302",
      "piso": 3,
      "coeficiente_participacion": "0.7143",
      "saldo_a_favor": "0.00",
      "estado_financiero": "AL_DIA"
    }
    ```
  - *Response (201 Created):*
    ```json
    {
      "id": "0b1e2c3d-4f5a-6b7c-8d9e-0f1a2b3c4d5e",
      "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "numero": "302",
      "piso": 3,
      "coeficiente_participacion": "0.7143",
      "saldo_a_favor": "0.00",
      "estado_financiero": "AL_DIA"
    }
    ```
  - *Response (404 Not Found):* `CONDOMINIO_NO_ENCONTRADO`.
  - *Response (409 Conflict):* `DEPARTAMENTO_DUPLICADO` por la restricción `uq_condominio_departamento`.
  - *Response (422 Unprocessable Entity):* validaciones de `piso >= 1`, `coeficiente_participacion > 0` y `saldo_a_favor >= 0`.
