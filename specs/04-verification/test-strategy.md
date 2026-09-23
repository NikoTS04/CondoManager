# Estrategia de Pruebas y Verificación (Test Strategy)

La estrategia de aseguramiento de calidad en CondoManager responde estrictamente al paradigma **Spec-Driven Development (SDD)**: toda prueba automatizada es la implementación ejecutable de un escenario formalmente descrito en las especificaciones.

---

## 1. Pirámide de Pruebas

```
                  ┌────────────────────────┐
                  │      BDD / E2E         │  (pytest-bdd ejecutando .feature)
                  │  - Cuotas y Alícuotas  │
                  │  - Bloqueo por Mora    │
                  │  - Concurrencia Parril.│
                  └───────────┬────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │       PRUEBAS DE INTEGRACIÓN       │  (PostgreSQL + Redis en Docker)
            │  - Transacciones ACID             │
            │  - Bloqueos SELECT FOR UPDATE     │
            │  - Claves de Idempotencia Únicas  │
            └─────────────────┬─────────────────┘
                              │
      ┌───────────────────────┴───────────────────────┐
      │               PRUEBAS UNITARIAS               │  (Aisladas en memoria)
      │  - Redondeo Decimal (ROUND_HALF_UP)          │
      │  - Fórmulas de prorrateo y saldo a favor     │
      │  - Generación de hashes SHA-256 de auditoría │
      └───────────────────────────────────────────────┘
```

---

## 2. Marco de Ejecución BDD con `pytest-bdd`

Los archivos `.feature` ubicados en `specs/02-domains/[dominio]/features/*.feature` son consumidos directamente por los módulos de test en `src/tests/bdd/`:
- Los escenarios `Dado - Cuando - Entonces` en español vinculan los DTOs de entrada y validan las mutaciones de estado en base de datos.
- Si una prueba BDD falla, **la regla de negocio especificada no se está cumpliendo**.

---

## 3. Pruebas de Estrés y Concurrencia (Race Conditions)
Para el módulo de reservas (Brandon):
- Se ejecutan tests asíncronos con 10 corrutinas concurrentes intentando reservar el mismo horario exacto.
- **Criterio de Éxito:** Exactamente 1 corrutina obtiene respuesta `201 Created` y 9 corrutinas obtienen `409 Conflict`, sin excepciones no controladas ni reservas dobles en base de datos.
