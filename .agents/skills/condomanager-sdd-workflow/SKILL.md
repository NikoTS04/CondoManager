---
name: condomanager-sdd-workflow
description: >-
  Guía y flujo de desarrollo estricto para el proyecto CondoManager bajo Spec-Driven Development (SDD).
  Activar al implementar, refactorizar o probar cualquier funcionalidad (cuotas, conciliación de pagos,
  cálculo de moras, reservas de áreas comunes, notificaciones o auditoría), garantizando la regla Spec-First,
  los 7 campos obligatorios de auditoría, precisión decimal contable y las convenciones de ramas Git.
---

# Flujo de Desarrollo y Guardarraíles de CondoManager (SDD)

Esta skill define el procedimiento paso a paso para desarrollar y verificar características en **CondoManager**, asegurando la sincronización permanente entre las especificaciones técnicas (`specs/`) y el código fuente (`src/`).

---

## 1. Regla de Oro: Spec-First

Antes de escribir o modificar código en `src/`:
1. **Identificar la especificación del proceso:** Ubicar el archivo correspondiente en `specs/02-processes-and-automations/proc-XX.md`.
2. **Actualizar la regla o máquina de estados:** Si el requerimiento altera una regla (ej. cambiar los días de corte o la fórmula de mora), reflejar el cambio primero en el documento `proc-XX.md`.
3. **Actualizar el criterio BDD:** Modificar o añadir el escenario `Dado - Cuando - Entonces` en `specs/04-acceptance-criteria/`.
4. **Sincronizar el contrato API:** Si se agregan o cambian campos de entrada/salida, actualizar `specs/05-api/api-contracts.md`.

---

## 2. Mapa de Responsabilidades y Módulos

| Responsable | Módulo Funcional | Especificación SDD | Directorio de Código |
| :--- | :--- | :--- | :--- |
| **Anderson** | Cuotas de Mantenimiento | `specs/02-processes-and-automations/proc-01-cuotas-mantenimiento.md` | `src/modules/cuotas/` |
| **Tarqui** | Pagos, Conciliación y Moras | `specs/02-processes-and-automations/proc-02-pagos-y-morosidad.md` | `src/modules/pagos/` |
| **Alejandro** | Notificaciones y Comunicaciones | `specs/02-processes-and-automations/proc-03-notificaciones.md` | `src/modules/notificaciones/` |
| **Brandon** | Reservas y Control de Solvencia | `specs/02-processes-and-automations/proc-04-reservas-areas-comunes.md` | `src/modules/reservas/` |
| **Junta / Core** | Usuarios, Egresos, Tickets, Reportes | `proc-05` al `proc-08` | `src/modules/{usuarios,egresos,tickets,reportes}/` |

---

## 3. Los 3 Guardarraíles Técnicos Innegociables

### A. Precisión Contable Decimal Absoluta (Zero-Float)
- **Nunca usar `float`** para importes de dinero, cuotas, recargos o saldos.
- Importar y utilizar siempre las utilidades de `src/shared/decimal_types.py`:
  ```python
  from src.shared.decimal_types import redondear_moneda, Decimal

  monto = redondear_moneda(presupuesto * (alicuota / Decimal("100.0000")))
  ```
- En base de datos (PostgreSQL), usar columnas `NUMERIC(12, 2)`.

### B. Bitácora de Auditoría Inmutable (Los 7 Campos)
Toda mutación de saldo, aprobación de pago, corte de mora o reserva confirmada DEBE registrar un log inmutable utilizando `AuditoriaPayload` en `src/core/audit.py`:
1. `departamento_id`: Identificador de la unidad (o `"CONDOMINIO_GENERAL"`).
2. `timestamp`: UTC (`datetime.now(timezone.utc)`).
3. `accion_ejecutada`: Código en mayúsculas (ej. `"CONCILIACION_PAGO_APROBADA"`).
4. `motivo`: Justificación de negocio o regla evaluada.
5. `resultado`: `"EXITOSO"` o `"FALLIDO"`.
6. `estado_anterior`: Diccionario con la instantánea antes del cambio.
7. `estado_posterior`: Diccionario con la instantánea después del cambio.

### C. Invariante de Solvencia en Reservas (PROC-04)
Al procesar una solicitud de reserva de área común, se debe consultar primero la deuda exigible:
```python
if deuda_vencida_departamento > Decimal("0.00"):
    # RECHAZO AUTOMÁTICO INMEDIATO
    return ResultadoReservaDTO(es_exitosa=False, motivo="Deuda vencida en mora activa.")
```

---

## 4. Ciclo de Automatización Estandarizado

Al implementar cualquier tarea automática o cron job, estructurar la clase o función bajo las 5 fases:
1. **Evento:** Captura del disparador (tiempo o webhook).
2. **Evaluación:** Consulta de reglas del condominio y saldos en base de datos.
3. **Decisión:** Bifurcación condicional documentada.
4. **Acción:** Mutación transaccional ACID en PostgreSQL.
5. **Verificación:** Validación del resultado esperado y despacho a la cola de auditoría/notificaciones.

---

## 5. Convención de Ramas y Commits en Git

- **Crear rama desde `develop`:** `feat/PROC-XX-[nombre-corto]`
  - Ejemplo: `git checkout -b feat/PROC-02-conciliacion-yape`
- **Mensaje de commit:** `tipo(alcance): descripción en minúsculas`
  - Ejemplo: `feat(pagos): validar unicidad de voucher segun PROC-02`
- **Antes de abrir Pull Request:**
  - Ejecutar linter: `ruff check .`
  - Ejecutar pruebas: `pytest`
  - Verificar que la especificación y BDD estén al día.
