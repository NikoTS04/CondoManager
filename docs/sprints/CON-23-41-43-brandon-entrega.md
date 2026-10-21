# CON-23, CON-41 y CON-43 — Entrega Técnica de Brandon (Sprint 1 y Sprint 2)

**Responsable:** Brandon (Full Stack Developer)  
**Rama de trabajo:** `feat/brandon-sprint-1-2`  
**Base:** `develop`  

---

## 1. Resumen de Historias Entregadas

| Historia | Jira | Dominio | Alcance Implementado |
|---|---|---|---|
| **CON-23** | PAG-02 | Pagos | Deduplicación determinista de comprobantes con hash SHA-256 canónico, constraint única en base de datos, retorno idempotente de comprobantes en evaluación y rechazo controlado ante comprobantes ya conciliados o reusados en otra unidad. |
| **CON-41** | RES-03 | Reservas | Reservas exclusivas para departamentos solventes: validación de usuario y vínculo activo, verificación de solvencia financiera (bloqueo inmediato si mora activa > 0), validación de aforo/horarios del catálogo y creación atómica de reserva `CONFIRMADA` con auditoría inmutable. |
| **CON-43** | RES-05 | Reservas | Prevención de reservas simultáneas y solapadas: control de concurrencia mediante `ReservasRepository` con bloqueo pesimista en base de datos (`SELECT FOR UPDATE`), manejo de colisiones (409 `HORARIO_NO_DISPONIBLE`) y soporte de horarios contiguos sin conflicto. |

---

## 2. Componentes Técnicos Implementados

### Módulo de Pagos (CON-23)
- `src/modules/pagos/repository.py`: Repositorio asíncrono `PagosRepository` con búsqueda por hash de idempotencia, guardado transaccional y captura de `IntegrityError` ante carreras concurrentes.
- `src/modules/pagos/service.py`: 
  - `calcular_hash_idempotencia()`: Función canónica `SHA256(condominio_id|banco|numero_operacion|fecha_operacion|monto)`.
  - `procesar_reporte_pago_persistente()`: Lógica transaccional que asegura no duplicar filas y responde según la política SDD (`VOUCHER_EN_EVALUACION`, `VOUCHER_YA_CONCILIADO`, `VOUCHER_UNIDAD_DISTINTA`).
- `src/modules/pagos/router.py`: Inyección de dependencias `Depends(get_pagos_repository)` con fallback en memoria para entornos de pruebas sin base de datos activa.

### Módulo de Reservas (CON-41 y CON-43)
- `src/modules/reservas/models.py`: Modelo relacional `Reserva` con índices optimizados `idx_reservas_area_fecha_estado` e `idx_reservas_depto_estado`.
- `src/modules/reservas/repository.py`: Repositorio asíncrono `ReservasRepository` que implementa:
  - `buscar_solapamientos()` con soporte para bloqueo pesimista `with_for_update()`.
  - `listar_disponibilidad()` y `listar_reservas()`.
  - `guardar()` y `actualizar_estado()` con commits transaccionales.
- `src/modules/reservas/service.py`:
  - `procesar_reserva_persistente()`: Orquesta la verificación de horario de catálogo, invariante de solvencia (`DEUDA_MORA_ACTIVA`), exclusión de solapamientos (`HORARIO_NO_DISPONIBLE`) y persistencia con auditoría inmutable de 7 campos.
  - `hay_solapamiento_horario()`: Evaluación estricta de intervalos semiabiertos $[hora\_inicio, hora\_fin)$.
- `src/modules/reservas/router.py`: Endpoints `POST /reservas`, `GET /reservas`, `GET /areas/{id}/disponibilidad` y `POST /reservas/{id}/cancelar` respaldados por `ReservasRepository`.

---

## 3. Evidencia Automatizada de Pruebas

Toda la suite de pruebas corre exitosamente bajo Python 3.11+:

```bash
# Pruebas de deduplicación de pagos (CON-23)
py -3.11 -m pytest src/tests/unit/test_deduplicacion_pagos.py src/tests/bdd/test_pagos_moras_bdd.py

# Pruebas de solvencia y concurrencia de reservas (CON-41 y CON-43)
py -3.11 -m pytest src/tests/unit/test_reservas_concurrencia.py src/tests/unit/test_reservas.py src/tests/bdd/test_reservas_bdd.py

# Suite completa del proyecto (228 pasadas, 0 fallidas)
py -3.11 -m pytest src/tests
```

### Casos de prueba destacados:
1. **Deduplicación canónica:** Verificación de equivalencia con espacios, ceros iniciales y mayúsculas.
2. **Carrera concurrente en vouchers:** Simulación de dos peticiones simultáneas con captura de `IntegrityError` y retorno idempotente del registro ganador.
3. **Bloqueo por mora activa:** Verificación de rechazo inmediato con código `403` y `DEUDA_MORA_ACTIVA`.
4. **10 solicitudes concurrentes de reserva:** Simulación de 10 corrutinas simultáneas sobre el mismo intervalo exacto, produciendo 1 reserva `CONFIRMADA` (201) y 9 rechazos con `HORARIO_NO_DISPONIBLE` (409).
5. **Horarios contiguos:** Verificación de que reservas consecutivas (ej. 10:00-14:00 y 14:00-18:00) se confirmen sin falsos positivos de conflicto.
