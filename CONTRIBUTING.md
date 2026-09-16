# Guía de Contribución y Flujo de Trabajo en Git (CONTRIBUTING)

¡Bienvenido al equipo de desarrollo de **CondoManager**!

Este proyecto se rige por la metodología **Spec-Driven Development (SDD)**. Para garantizar un desarrollo ordenado, trazable y colaborativo entre todos los integrantes (**Anderson, Tarqui, Alejandro, Brandon, Junta Directiva**), todos los cambios en el repositorio deben seguir las pautas detalladas en esta guía.

---

## 1. Regla de Oro del SDD (Spec-First)

> **Ningún código o cambio en las reglas de negocio se fusiona sin su especificación correspondiente.**
> Si agregas un nuevo cálculo, un nuevo estado o un endpoint, la especificación en `specs/` (y sus escenarios BDD) debe crearse o actualizarse en la misma rama antes de solicitar revisión.

---

## 2. Estrategia de Ramas (Branching Model)

Utilizamos un modelo de ramas basado en ramas de características (*Feature Branches*) integradas sobre una rama principal:

```
 main (Producción / Estable)
   │
 develop (Integración continua)
   │
   ├──▶ feat/PROC-01-emision-cuotas       (Anderson)
   ├──▶ feat/PROC-02-conciliacion-yape    (Tarqui)
   ├──▶ feat/PROC-03-notificaciones-motor (Alejandro)
   └──▶ feat/PROC-04-reservas-solvencia   (Brandon)
```

### 2.1 Ramas Principales
- **`main`**: Contiene únicamente código estable, probado y listo para despliegue. Protegida contra commits directos; solo se actualiza mediante Pull Request aprobado desde `develop` o `hotfix`.
- **`develop`**: Rama base de integración diaria donde convergen todas las características completadas.

### 2.2 Convención de Nombres de Ramas

Las ramas de trabajo deben crearse a partir de `develop` y nombrarse con prefijos estandarizados en minúsculas y separados por guiones:

| Tipo de Rama | Formato de Nombre | Ejemplo | Asignación / Propósito |
| :--- | :--- | :--- | :--- |
| **Nueva Característica** | `feat/PROC-XX-[nombre-corto]` | `feat/PROC-01-emision-cuotas` | Anderson (Cuotas) |
| | `feat/PROC-02-conciliacion-pagos` | Tarqui (Pagos y Moras) |
| | `feat/PROC-03-motor-alertas` | Alejandro (Notificaciones) |
| | `feat/PROC-04-reservas-parrillas` | Brandon (Reservas) |
| | `feat/CORE-[nombre-corto]` | `feat/CORE-audit-logger` | Módulos transversales |
| **Corrección de Bugs** | `fix/[identificador]-[descripcion]` | `fix/mora-calculo-dias-gracia` | Corrección de lógica |
| **Documentación SDD** | `docs/[seccion]-[descripcion]` | `docs/proc-02-reglas-plin` | Actualización de specs/ADR |
| **Refactorización** | `refactor/[modulo]-[descripcion]` | `refactor/cuotas-decimal-types`| Mejoras internas sin cambio de regla |
| **Hotfix Urgente** | `hotfix/[descripcion]` | `hotfix/fallo-pago-duplicado` | Sale de `main` hacia `main` y `develop` |

---

## 3. Convención de Mensajes de Commit (Conventional Commits)

Cada commit debe describir claramente el propósito del cambio siguiendo la especificación de **Conventional Commits**:

$$\text{tipo}(\text{alcance}): \text{descripci\acute{o}n en presente y min\acute{u}sculas}$$

### Tipos Permitidos:
- **`feat`**: Nueva funcionalidad (ej. `feat(cuotas): agregar emision masiva automatica mensual segun PROC-01`)
- **`fix`**: Corrección de un defecto o error (ej. `fix(pagos): corregir validacion de codigo de operacion duplicado`)
- **`docs`**: Cambios exclusivos en especificaciones o documentación (ej. `docs(specs): actualizar matriz de roles en security-and-rbac.md`)
- **`test`**: Creación o actualización de pruebas unitarias o BDD (ej. `test(reservas): agregar escenarios BDD para rechazo por mora activa`)
- **`refactor`**: Cambios de código que no corrigen bugs ni agregan funcionalidades (ej. `refactor(audit): optimizar hashing SHA-256`)
- **`chore`**: Mantenimiento de dependencias o configuración (ej. `chore(deps): actualizar fastapi a version 0.111.0`)

### Ejemplos Válidos:
```bash
git commit -m "feat(reservas): validar solvencia de cuotas antes de confirmar reserva"
git commit -m "docs(adr): agregar ADR-002 para estrategia de migraciones con alembic"
git commit -m "fix(moras): aplicar recargo solo tras expirar los 2 dias de gracia"
```

---

## 4. Flujo de Trabajo Paso a Paso (Workflow)

### Paso 1: Actualizar la copia local
Antes de iniciar cualquier trabajo, sincroniza tu entorno local con la rama de integración:
```bash
git checkout develop
git pull origin develop
```

### Paso 2: Crear tu rama de trabajo
```bash
# Ejemplo para Brandon trabajando en el módulo de reservas:
git checkout -b feat/PROC-04-bloqueo-solvencia
```

### Paso 3: Verificar y actualizar la especificación (SDD First)
Si el requerimiento introduce una nueva regla o altera un flujo:
1. Abre el archivo correspondiente en `specs/02-processes-and-automations/proc-XX.md`.
2. Actualiza la sección de reglas o máquina de estados.
3. Si impacta la API, actualiza `specs/05-api/api-contracts.md`.
4. Si introduce un nuevo criterio de prueba, actualiza `specs/04-acceptance-criteria/*.feature.md`.

### Paso 4: Implementar el código y las pruebas
- Escribe el código en tu módulo asignado dentro de `src/modules/[tu-modulo]/`.
- Respeta la precisión contable usando las utilidades de `src/shared/decimal_types.py`.
- Si tu operación altera saldos o estados, registra la auditoría con los 7 campos en `src/core/audit.py`.

### Paso 5: Ejecutar pruebas y linters locales
Antes de enviar tu código al repositorio remoto:
```bash
# Formato y verificación estática
ruff check .
ruff format --check .

# Ejecución de pruebas unitarias y BDD
pytest
```

### Paso 6: Publicar tu rama y abrir un Pull Request (PR)
```bash
git push -u origin feat/PROC-04-bloqueo-solvencia
```
Dirígete a GitHub y abre el Pull Request apuntando hacia la rama **`develop`**.

---

## 5. Plantilla Estándar para Pull Requests (PR Checklist)

Al abrir tu Pull Request, completa la siguiente lista de verificación en la descripción:

```markdown
## Descripción del Cambio
[Breve resumen de la funcionalidad implementada o problema resuelto]

## Proceso / Módulo SDD Vinculado
- **Módulo:** PROC-XX ([Nombre del proceso])
- **Responsable:** [Anderson / Tarqui / Alejandro / Brandon / Junta]

## Checklist de Calidad SDD
- [ ] ¿Se actualizó o validó la especificación técnica en `specs/`?
- [ ] ¿Se incluyeron / actualizaron los escenarios de prueba BDD correspondientes en `specs/04-acceptance-criteria/`?
- [ ] ¿Si el cambio expone o modifica endpoints, se actualizó `specs/05-api/api-contracts.md`?
- [ ] ¿Las operaciones financieras utilizan precisión decimal estricta (`Decimal`, no `float`)?
- [ ] ¿Los cambios de estado transaccionales registran los 7 campos mínimos de auditoría inmutable?
- [ ] ¿Todas las pruebas unitarias y de integración pasan satisfactoriamente?
```

---

## 6. Políticas de Revisión y Fusión (Merge Rules)

1. **Aprobaciones Requeridas:** Todo PR requiere al menos **una aprobación (Peer Review)** de otro miembro del equipo antes de fusionarse.
2. **Historial Limpio (Squash and Merge):** Las ramas de características se fusionan utilizando la opción **Squash and Merge** en GitHub para condensar los commits de desarrollo en un único commit semántico en `develop`.
3. **Eliminación de Ramas:** Una vez fusionada la rama de característica, debe eliminarse tanto local como remotamente para mantener limpio el repositorio.
