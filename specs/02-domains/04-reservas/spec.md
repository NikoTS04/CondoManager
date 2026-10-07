# Dominio 04: Reservas de Áreas Comunes y Control de Solvencia (Brandon)

## 1. Ficha del Dominio
- **Identificador:** DOM-04 / PROC-04
- **Responsable:** **Brandon**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.1 (Persistencia en PostgreSQL)
- **Módulos de Código:** `src/modules/reservas/`

---

## 2. Propósito y Límites del Dominio
El dominio de Reservas es responsable de:
1. Publicar el catálogo de áreas comunes activas (parrillas, salones sociales, gimnasio, zonas recreativas) con aforos, horarios permitidos y costos asociados.
2. **Registrar nuevas áreas comunes** en el catálogo mediante un alta explícita (`POST /api/v1/areas/crear`).
3. Gestionar la disponibilidad en calendario en tiempo real mediante transacciones atómicas con bloqueo pesimista (`SELECT FOR UPDATE`).
4. **Aplicar la Invariante Crítica de Solvencia:** Todo intento de reserva por parte de un departamento con cuotas vencidas en mora debe ser rechazado inmediatamente.
5. Generar cargos por derecho de uso o depósito de garantía en el estado de cuenta si el área tiene tarifa.
6. Permitir la cancelación voluntaria con liberación inmediata de horarios para otros copropietarios.

---

## 3. Persistencia (PostgreSQL)

Todo el estado del dominio se persiste en las tablas descritas en `specs/03-contracts/database/data-dictionary.md`:

| Operación | Tabla | Mapeo |
| :--- | :--- | :--- |
| Catálogo de áreas | `areas_comunes` | Modelo `AreaComun` (`src/modules/reservas/models.py`) |
| Reservas y disponibilidad | `reservas` | Modelo `Reserva` |
| Solvencia del solicitante | `departamentos` (columna `estado_financiero`) | Modelo `Departamento` (`src/modules/condominios/models.py`) |
| Alta de áreas / departamentos | `areas_comunes` / `departamentos` | Servicios `ReservasService.crear_area` y `CondominiosService.crear_departamento` |

Reglas de persistencia:
- **No existe estado en memoria:** ninguna operación usa diccionarios ni datos sembrados en el proceso; los datos sobreviven a un reinicio del servicio.
- **`condominio_id` de una reserva:** la tabla `reservas` no almacena `condominio_id`; el valor de la respuesta se deriva de `areas_comunes.condominio_id` (fuente de verdad). El campo del *request* es **informativo** y se ignora si no coincide con el del área.
- **Confirmación antes de responder:** los endpoints de escritura hacen `commit` antes de devolver la respuesta para que la siguiente petición siempre observe el dato (evita condiciones de carrera entre peticiones consecutivas).
- El catálogo `GET /api/v1/areas` puede retornar `[]` si aún no se han dado de alta áreas en el condominio (no hay carga automática de datos piloto).

---

## 4. Invariante Innegociable de Solvencia Financiera

$$\forall\ d \in \text{Departamentos},\ \text{DeudaMora}(d) > 0.00 \implies \text{AccesoReservas}(d) = \text{DENEGADO}$$

La fuente de verdad del bloqueo es la columna **`departamentos.estado_financiero`**: si el departamento está en `EN_MORA` la solicitud se rechaza antes de evaluar la disponibilidad física del horario.

```python
departamento = await _obtener_departamento(session, request.departamento_id)
if departamento.estado_financiero == "EN_MORA":
    saldo_vencido = await _saldo_mora_informativo(session, departamento.id)
    raise DeudaMoraActivaException(
        departamento_id=str(departamento.id),
        saldo_vencido=saldo_vencido,
    )
```

- `saldo_vencido` es **informativo**: suma el pendiente de `cuotas_mantenimiento` en estado `VENCIDA`/`EN_MORA` si existe; si no hay cuotas emitidas se informa sin monto. El bloqueo **no** depende de esa suma.
- Respuesta: `403 Forbidden` con `error_code: DEUDA_MORA_ACTIVA`.

---

## 5. Control de Concurrencia y Disponibilidad
- Las áreas comunes dividen su disponibilidad en bloques configurables (ej. bloques de 3 o 4 horas).
- Para evitar que dos residentes adquieran el mismo horario de parrilla simultáneamente, `POST /api/v1/reservas` abre la transacción con **bloqueo pesimista sobre la fila del área** (`SELECT ... FROM areas_comunes WHERE id = :area_id FOR UPDATE`) y recién entonces reconsulta las reservas `CONFIRMADA` del área (`specs/01-architecture/concurrency-and-locking.md`).
- La cancelación bloquea la fila de la reserva (`FOR UPDATE`) para que dos cancelaciones simultáneas no se pisen; la segunda recibe `422 CANCELACION_NO_PERMITIDA`.
- El solapamiento se evalúa con el intervalo semiabierto `[inicio, fin)`: `inicio_a < fin_b and fin_a > inicio_b`.

---

## 6. Endpoints Implementados (`/api/v1`)

| Método | Ruta | Persistencia | Errores principales |
| :--- | :--- | :--- | :--- |
| `GET` | `/areas` | `areas_comunes` (solo `esta_activa = true`) | - |
| `POST` | `/areas/crear` | `areas_comunes` | `404 CONDOMINIO_NO_ENCONTRADO`, `409 AREA_DUPLICADA`, `422` (validaciones Pydantic) |
| `GET` | `/reservas?area_id=&fecha=` | `reservas` (join con `areas_comunes`) | `404 AREA_NO_ENCONTRADA` |
| `POST` | `/reservas` | `reservas` | `404 AREA_NO_ENCONTRADA` / `DEPARTAMENTO_NO_ENCONTRADO`, `403 DEUDA_MORA_ACTIVA`, `409 HORARIO_NO_DISPONIBLE`, `400 HORARIO_INVALIDO` / `AREA_INACTIVA`, `422 DEPARTAMENTO_NO_PERTENECE_AL_CONDOMINIO` |
| `POST` | `/reservas/{id}/cancelar` | `reservas` (`estado = CANCELADA`) | `404 RESERVA_NO_ENCONTRADA`, `422 CANCELACION_NO_PERMITIDA` |

### Resolución del departamento titular
`departamento_id` acepta **UUID o número de departamento** (ej. `"402"`) para ser compatible con el frontend; el servicio lo normaliza a UUID antes de persistir. Si no existe se retorna `404 DEPARTAMENTO_NO_ENCONTRADO`.

### Coherencia de condominio
El departamento debe pertenecer al mismo condominio del área (`422 DEPARTAMENTO_NO_PERTENECE_AL_CONDOMINIO`).

### Cancelaciones
- Residente: requiere al menos **24 horas** de anticipación respecto al inicio de la reserva.
- Administrador (`es_admin: true`): puede cancelar en cualquier momento.

---

## 7. Contratos DTO Principales

### `CrearAreaRequest` (Request - `POST /areas/crear`)
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

### `CrearReservaDTO` (Request)
```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "area_id": "11111111-1111-1111-1111-111111111101",
  "departamento_id": "dpto-302",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00",
  "hora_fin": "22:00"
}
```
> `condominio_id` es informativo y `departamento_id` admite UUID o número.

### `ReservaResponseDTO` (Response 201 Created)
```json
{
  "id": "e4f5a6b7-8c9d-4e0f-1a2b-3c4d5e6f7a8b",
  "estado": "CONFIRMADA",
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "area_id": "11111111-1111-1111-1111-111111111101",
  "area_nombre": "Zona de Parrilla 1",
  "departamento_id": "0b1e2c3d-4f5a-6b7c-8d9e-0f1a2b3c4d5e",
  "costo_reserva": "30.00",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00",
  "hora_fin": "22:00",
  "creado_en": "2026-09-22T20:30:00Z"
}
```
