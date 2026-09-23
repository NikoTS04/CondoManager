# Guía Metodológica: Spec-Driven Development (SDD) en CondoManager

## 1. ¿Qué es Spec-Driven Development (SDD)?

**Spec-Driven Development (SDD)** es una disciplina de ingeniería de software en la cual **las especificaciones técnicas son la única fuente de verdad (Single Source of Truth) y preceden obligatoriamente a la implementación del código**. 

A diferencia de los proyectos donde la documentación es un subproducto secundario y desactualizado, en CondoManager:
- Si una funcionalidad no está especificada, **no existe**.
- Si el código no coincide con la especificación, **el código contiene un defecto**.
- Si una regla de negocio cambia, **la especificación se actualiza y aprueba primero**.

```
                ┌─────────────────────────────────────────────────────────┐
                │          FASE 1: ESPECIFICACIÓN FORMAL (SPEC)          │
                │  - Reglas de negocio y fórmulas matemáticas             │
                │  - Máquinas de estados y transiciones legales           │
                │  - Esquemas de eventos asíncronos                       │
                └────────────────────────────┬────────────────────────────┘
                                             │
                                             ▼
                ┌─────────────────────────────────────────────────────────┐
                │        FASE 2: CONTRATOS Y PRUEBAS BDD (CONTRACT)       │
                │  - Endpoints OpenAPI 3.1 en YAML                        │
                │  - Diccionario de datos y DDL en PostgreSQL             │
                │  - Escenarios ejecutables .feature (Gherkin puro)       │
                └────────────────────────────┬────────────────────────────┘
                                             │
                                             ▼
                ┌─────────────────────────────────────────────────────────┐
                │          FASE 3: IMPLEMENTACIÓN DE CÓDIGO (CODE)        │
                │  - Módulos en src/modules/ espejados 1:1                │
                │  - Precisión Decimal estricta (cero floats)             │
                │  - Registro inmutable de los 7 campos de auditoría      │
                └────────────────────────────┬────────────────────────────┘
                                             │
                                             ▼
                ┌─────────────────────────────────────────────────────────┐
                │          FASE 4: VERIFICACIÓN AUTOMATIZADA (QA)         │
                │  - pytest-bdd ejecuta los .feature contra el código     │
                │  - script verify_sdd_compliance.py valida integridad    │
                │  - Pull Request con revisión de pares aprobada          │
                └─────────────────────────────────────────────────────────┘
```

---

## 2. Los 5 Niveles de Especificación (L0 a L4)

| Nivel | Nombre | Directorio | Contenido | Responsable |
| :---: | :--- | :--- | :--- | :--- |
| **L0** | **Requerimientos y Metas de Negocio** | Archivos base / `specs/00-core/` | Contexto de Villa Bonita 3, glosario ubicuo y matriz de trazabilidad. | Product Owner / Stakeholders |
| **L1** | **Arquitectura de Sistema y Políticas** | `specs/01-architecture/` | Diagramas C4, modelo multi-edificio, ADRs, auditoría inmutable, idempotencia y bloqueos. | Tech Lead / Arquitecto |
| **L2** | **Especificaciones de Dominio Autocontenidas** | `specs/02-domains/[modulo]/` | Reglas funcionales, máquinas de estados y escenarios BDD por módulo. | **Anderson, Tarqui, Alejandro, Brandon** |
| **L3** | **Contratos Técnicos Ejecutables** | `specs/03-contracts/` | OpenAPI 3.1 YAML, diccionario de datos SQL y esquemas JSONSchema de eventos. | Ingenieros Backend / API |
| **L4** | **Verificación y Operaciones** | `specs/04-verification/` y `05-operations/` | Estrategia de testing, dataset de 139 dptos y runbooks de despliegue. | QA / DevOps |

---

## 3. Protocolo de Modificación de Reglas de Negocio

Cuando se requiera modificar una regla existente (por ejemplo, cambiar la tasa de recargo por mora del 10% a un monto fijo de S/ 20.00):
1. **Paso 1 (Spec Update):** Abrir rama `docs/PROC-02-ajuste-mora`.
2. **Paso 2 (Diff de Especificación):** Modificar la fórmula en `specs/02-domains/02-pagos-y-moras/spec.md`.
3. **Paso 3 (Ajuste BDD):** Actualizar los valores esperados en `specs/02-domains/02-pagos-y-moras/features/pagos_y_moras.feature`.
4. **Paso 4 (Ajuste de Código):** Actualizar el servicio en `src/modules/pagos/service.py`.
5. **Paso 5 (Validación):** Correr `pytest` para comprobar que las pruebas BDD ahora pasan con la nueva regla.
6. **Paso 6 (PR):** El revisor de código comprueba que la especificación y el código avanzaron en el mismo commit.

---

## 4. Guardarraíles Innegociables en Pull Requests

Ningún Pull Request puede fusionarse si viola alguno de los siguientes 4 principios:
1. **Regla Zero-Float:** Todo campo monetario debe ser `Decimal`. Cualquier uso de `float` en cálculos de cuotas o pagos bloquea el merge.
2. **Los 7 Campos de Auditoría:** Toda mutación de estado financiero o de reservas debe emitir su payload a `src/core/audit.py`.
3. **Invariante de Solvencia:** El módulo de reservas debe validar la deuda antes de confirmar una solicitud.
4. **Cumplimiento de Contratos OpenAPI:** Los endpoints de la API deben apegarse estrictamente a `condomanager.openapi.yaml`.
