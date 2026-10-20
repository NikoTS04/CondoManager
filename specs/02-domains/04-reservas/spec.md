# Dominio 04: Reservas de Áreas Comunes y Control de Solvencia (Brandon)

## 1. Ficha del Dominio
- **Identificador:** DOM-04 / PROC-04
- **Responsable:** **Brandon**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.0 (SDD Detallado)
- **Módulos de Código:** `src/modules/reservas/`

Contrato objetivo del Sprint 2: [CON-72](../../05-api/sprint-2-contratos.md#4-catálogo-disponibilidad-y-reservas), con OpenAPI, tipos compartidos, permisos y errores. La implementación persistente se distribuye entre CON-39/40/41/42/43/46/73; el estado de esta especificación no acredita que todos esos recorridos ya estén integrados.

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
- Horarios semanales del catálogo en America/Lima, con precisión de minuto e intervalos `[inicio, fin)`. Un área inactiva o un horario fuera de esas reglas no admite nuevas reservas.
- La consulta de disponibilidad devuelve intervalos ocupados sin identidad de otras unidades y considera bloqueos persistentes. La creación vuelve a comprobar disponibilidad y solvencia dentro de su transacción.
- La protección SQL debe funcionar incluso sin reservas previas: bloquear el recurso de área persistente antes de consultar solapamientos o usar una exclusión equivalente. Creación y cancelación comparten el mismo mecanismo; consultar solo filas de reservas existentes no protege un intervalo vacío.

---

## 5. Contratos DTO Principales

### `CrearReservaDTO` (Request)
```json
{
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "area_id": "01d385b5-6a49-42f8-a32f-f0ceddc69a43",
  "departamento_id": "6c78c3b5-1efb-4d0b-a5f8-78fc17364083",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00:00",
  "hora_fin": "22:00:00"
}
```

### `ReservaResponseDTO` (Response 201 Created)
```json
{
  "id": "e4f5a6b7-8c9d-4e0f-1a2b-3c4d5e6f7a8b",
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "area_id": "01d385b5-6a49-42f8-a32f-f0ceddc69a43",
  "departamento_id": "6c78c3b5-1efb-4d0b-a5f8-78fc17364083",
  "estado": "CONFIRMADA",
  "area_nombre": "Zona de Parrilla 1",
  "costo_reserva": "30.00",
  "fecha_reserva": "2026-10-25",
  "hora_inicio": "19:00:00",
  "hora_fin": "22:00:00",
  "zona_horaria": "America/Lima",
  "creado_en": "2026-09-22T20:30:00Z"
}
```
