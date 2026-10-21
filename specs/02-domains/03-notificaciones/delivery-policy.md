# Política de Entrega y Reintentos de Notificaciones (Delivery Policy — CON-37)

## 1. Clasificación de Errores de Transporte

El motor de entrega (`src/modules/notificaciones/transportes.py` y `entrega.py`) clasifica toda respuesta fallida del proveedor en dos categorías disjuntas:

| Categoría | Resultado en `notificacion_intentos` | Códigos y Condiciones | Acción del Motor |
| :--- | :---: | :--- | :--- |
| **Temporal** | `FALLO_TEMPORAL` | `429` (Too Many Requests), `500`, `502`, `503`, `504`, `TIMEOUT`, `CONNECTION_ERROR`, `NETWORK_ERROR` y excepciones de red/socket transitorias. | Si `intentos < 4`, pasa a `REINTENTANDO` y agenda `proximo_intento_en`. Si ocurre en el intento 4, agota la cuota y pasa a `FALLIDO_PERMANENTE`. |
| **Definitivo** | `FALLO_DEFINITIVO` | `550` (User unknown / Mailbox does not exist), `131026` (WhatsApp undeliverable), destinatario inválido (`DESTINATARIO_INVALIDO`, `INVALID_EMAIL`, `USER_UNKNOWN`, `MAILBOX_NOT_FOUND`), y códigos HTTP `4xx` distintos de `429` (`400`, `401`, `403`, `404`, `422`). | Aborta reintentos inmediatamente: pasa a `FALLIDO_PERMANENTE` con `proximo_intento_en = NULL` y genera alerta administrativa. |

---

## 2. Esquema de Reintentos Exponenciales (Exponential Backoff)

Toda notificación se registra inicialmente en `EN_COLA` con `intentos = 0`, `ciclo = 1` y `proximo_intento_en = ahora`. En cada ciclo (`ciclo >= 1`), el motor permite **1 intento inicial + hasta 3 reintentos** (máximo `4` intentos por ciclo, restricción SQL `intentos BETWEEN 0 AND 4`):

| Intento (`numero`) | Estado previo | Espera programada si falla temporalmente | Jitter | Acción si falla temporalmente |
| :---: | :---: | :--- | :---: | :--- |
| **1 (Inicial)** | `EN_COLA` (`intentos = 0`) | **+2 minutos** (`120 s`) para el intento 2 | **±15 segundos** (`[-15 s, +15 s]`, inyectable en pruebas) | `intentos = 1`, `estado = REINTENTANDO`, `proximo_intento_en = finalizado_en + 120s ± 15s`. |
| **2 (Reintento 1)** | `REINTENTANDO` (`intentos = 1`) | **+10 minutos** (`600 s`) para el intento 3 | Sin jitter (`0 s`) | `intentos = 2`, `estado = REINTENTANDO`, `proximo_intento_en = finalizado_en + 600s`. |
| **3 (Reintento 2)** | `REINTENTANDO` (`intentos = 2`) | **+30 minutos** (`1800 s`) para el intento 4 | Sin jitter (`0 s`) | `intentos = 3`, `estado = REINTENTANDO`, `proximo_intento_en = finalizado_en + 1800s`. |
| **4 (Reintento 3 / Final)** | `REINTENTANDO` (`intentos = 3`) | Sin nuevos reintentos (`NULL`) | — | `intentos = 4`, `estado = FALLIDO_PERMANENTE`, `proximo_intento_en = NULL` + alerta administrativa. |

---

## 3. Estados de Entrega y Evidencia del Transporte

1. **`EN_COLA`**: Notificación registrada transaccionalmente, pendiente de despacho (`intentos = 0` en el `ciclo` vigente).
2. **`REINTENTANDO`**: Tuvo al menos un `FALLO_TEMPORAL` (`intentos` entre 1 y 3) y aguarda `proximo_intento_en`.
3. **`ACEPTADO`**: El proveedor aceptó el mensaje (`proveedor_message_id` registrado y `aceptado_en` poblado). Nunca vuelve a reclamarse ni reenviarse.
4. **`ENTREGADO`**: Confirmación final de entrega (`confirmar_entrega` por `notificacion_id` o `proveedor_message_id`, poblando `entregado_en`). Nunca se reenvía.
5. **`FALLIDO_PERMANENTE`**: Error definitivo o agotamiento de los 4 intentos del ciclo actual.

Cada intento registra `ciclo`, `numero`, `transporte` (`SIMULADO` o `SMTP`) y `transporte_simulado` (`true` o `false`) en `notificacion_intentos`.

---

## 4. Coordinación entre Workers y Protección de Arrendamiento (`FOR UPDATE SKIP LOCKED`)

1. **Reclamo (`reclamar_lote`)**: En una transacción corta, el worker selecciona hasta `limite` filas con:
   - `estado IN ('EN_COLA', 'REINTENTANDO')`
   - `intentos < 4`
   - `proximo_intento_en IS NULL OR proximo_intento_en <= ahora`
   - `bloqueado_hasta IS NULL OR bloqueado_hasta < ahora`
   usando `FOR UPDATE SKIP LOCKED`, asigna `bloqueado_por = worker_id` y `bloqueado_hasta = ahora + lease`, y confirma la transacción.
2. **Protección contra expiración de arrendamiento antes del envío**: Antes de invocar el transporte para cada elemento del lote reclamado, `despachar_pendientes` verifica que `ahora_actual + margen_timeout < bloqueado_hasta` (`margen = SMTP_TIMEOUT_SEGUNDOS`). Si un envío podría finalizar después de que expire su arrendamiento, se omite en esa pasada (`omitidas_arrendamiento`) para impedir que otro worker lo reclame simultáneamente y se envíe dos veces.
3. **Envío fuera de transacción**: El worker invoca el transporte sin mantener conexiones ni bloqueos abiertos en PostgreSQL.
4. **Persistencia condicionada del resultado**: En una segunda transacción corta, el worker bloquea la fila de `notificaciones` y verifica que:
   - El estado no sea `ACEPTADO` ni `ENTREGADO`.
   - `bloqueado_por == worker_id` (si el arrendamiento venció y otro worker la reclamó, no pisa el estado).
   - Inserta el registro en `notificacion_intentos` con `(notificacion_id, ciclo, numero)` protegido por `uq_intento_numero`.
5. **Recuperación tras reinicio**: Si un worker se detiene abruptamente después de reclamar un lote, cuando `bloqueado_hasta < ahora` cualquier worker activo vuelve a reclamar la notificación y completa el envío.

---

## 5. Alertas Administrativas y Reprogramación Manual por Ciclos (`reprogramar_manual`)

### 5.1 Alerta Administrativa
Al pasar a `FALLIDO_PERMANENTE` (por error definitivo o tras el cuarto intento fallido), se registra de forma idempotente (`uq_alerta_notificacion_tipo`) una fila en `alertas_administrativas`:
- `tipo`: `'NOTIFICACION_FALLIDA'`
- `severidad`: `'BAJA'`
- `mensaje`: *"El correo del residente del Dpto. 402 rebotó. Actualice los datos de contacto."* (sin incluir contraseñas, tokens ni datos sensibles).

### 5.2 Reprogramación Manual por Ciclos (`ciclo`)
Cuando un administrador corrige el contacto y ejecuta `reprogramar_manual(session, notificacion_id, nuevo_destinatario)`:
- **Precondición**: Solo se permite si `estado == 'FALLIDO_PERMANENTE'`; en cualquier otro estado se rechaza con `409 Conflict` (`REENVIO_NO_PERMITIDO`).
- **Conservación íntegra del historial mediante `ciclo`**:
  - `notificaciones` incluye la columna `ciclo INTEGER NOT NULL DEFAULT 1 CHECK (ciclo >= 1)` y `notificacion_intentos` incluye `ciclo INTEGER NOT NULL DEFAULT 1` con unicidad `UNIQUE (notificacion_id, ciclo, numero)` (`uq_intento_numero`).
  - `reprogramar_manual` incrementa `notificacion.ciclo += 1`, reinicia `notificacion.intentos = 0`, pasa `estado = 'EN_COLA'`, fija `proximo_intento_en = ahora`, actualiza `destinatario` (si se proporciona y es válido), limpia `error_codigo`, `error_mensaje` y el arrendamiento, y marca la alerta abierta en `alertas_administrativas` con `atendida_en = ahora`.
  - Los intentos de los ciclos anteriores permanecen intactos en `notificacion_intentos` como evidencia auditable, mientras el nuevo ciclo vuelve a numerar sus intentos de `1` a `4`.
