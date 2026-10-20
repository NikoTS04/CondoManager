# Dominio 04: Reservas de Áreas Comunes y Control de Solvencia (Brandon)

## 1. Ficha del Dominio
- **Identificador:** DOM-04 / PROC-04
- **Responsable:** **Brandon**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/reservas/`

---

## 2. Propósito y Límites del Dominio
El dominio de Reservas es responsable de:
1. Publicar el catálogo de áreas comunes activas (parrillas, salones sociales, gimnasio, zonas recreativas) con aforos, horarios permitidos y costos asociados.
2. Gestionar la disponibilidad en calendario en tiempo real mediante transacciones atómicas con bloqueo pesimista (`SELECT FOR UPDATE`).
3. **Aplicar la Invariante Crítica de Solvencia:** Todo intento de reserva por parte de un departamento con cuotas vencidas en mora debe ser rechazado inmediatamente.
4. Generar cargos por derecho de uso o depósito de garantía en el estado de cuenta si el área tiene tarifa.
5. Permitir la cancelación voluntaria con liberación inmediata de horarios para otros copropietarios.

---

## 3. Invariante Innegociable de Solvencia Financiera

$$\forall\ d \in \text{Departamentos},\ \text{DeudaMora}(d) > 0.00 \implies \text{AccesoReservas}(d) = \text{DENEGADO}$$

El servicio ejecuta la comprobación de solvencia como primer filtro obligatorio antes de consultar disponibilidad física:
```python
saldo_en_mora = await cuotas_repo.obtener_saldo_en_mora(solicitud.departamento_id)
if saldo_en_mora > Decimal("0.00"):
    raise DeudaMoraActivaException(
        departamento_id=solicitud.departamento_id,
        saldo_vencido=saldo_en_mora
    )
```

---

## 4. Control de Concurrencia y Disponibilidad
- Las áreas comunes dividen su disponibilidad en bloques configurables (ej. bloques de 3 o 4 horas).
- Para evitar que dos residentes adquieran el mismo horario de parrilla simultáneamente, se aplica bloqueo pesimista sobre el intervalo en PostgreSQL (`specs/01-architecture/concurrency-and-locking.md`).

---

## 5. Contratos DTO Principales

### `CrearReservaDTO` (Request)
```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "area_id": "parrilla-01",
  "departamento_id": "dpto-302",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00",
  "hora_fin": "22:00"
}
```

### `ReservaResponseDTO` (Response 201 Created)
```json
{
  "id": "e4f5a6b7-8c9d-4e0f-1a2b-3c4d5e6f7a8b",
  "estado": "CONFIRMADA",
  "area_nombre": "Zona de Parrilla 1",
  "costo_reserva": "30.00",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00",
  "hora_fin": "22:00",
  "creado_en": "2026-09-22T20:30:00Z"
}
```
