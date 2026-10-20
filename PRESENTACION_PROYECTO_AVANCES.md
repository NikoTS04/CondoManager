# CondoManager — Guía Integral para Presentación Ejecutiva (PPT)
## Overview del Proyecto, Avances en `feat/PROC-05` y Caso de Automatización con Bots

> **Propósito de este documento:**  
> Servir como base de conocimiento completa, estructurada y lista para alimentar a **Claude** (o herramientas de generación de diapositivas) y crear una presentación ejecutiva de alto impacto sobre el sistema **CondoManager**.
>
> **Edificio Piloto:** Condominio Villa Bonita 3 (139 departamentos, 14 pisos).  
> **Metodología Central:** Spec-Driven Development (SDD) con desarrollo guiado por comportamiento (BDD).  
> **Fecha de Elaboración:** Octubre 2026.

---

## Índice de Contenidos para Diapositivas

1. [Bloque 1: Overview del Proyecto CondoManager](#bloque-1-overview-del-proyecto-condomanager)
   - [1.1 Contexto del Problema y Justificación](#11-contexto-del-problema-y-justificación)
   - [1.2 Propuesta de Valor y Objetivos](#12-propuesta-de-valor-y-objetivos)
   - [1.3 Metodología Spec-Driven Development (SDD)](#13-metodología-spec-driven-development-sdd)
   - [1.4 Los 3 Guardarraíles Técnicos Innegociables](#14-los-3-guardarraíles-técnicos-innegociables)
   - [1.5 Arquitectura y Stack Tecnológico](#15-arquitectura-y-stack-tecnológico)
   - [1.6 Mapeo de Módulos Funcionales (PROC-01 a PROC-08)](#16-mapeo-de-módulos-funcionales-proc-01-a-proc-08)
2. [Bloque 2: Avances Realizados en la Rama `feat/PROC-05-alta-usuarios-y-roles`](#bloque-2-avances-realizados-en-la-rama-featproc-05-alta-usuarios-y-roles)
   - [2.1 Alcance y Commits Realizados](#21-alcance-y-commits-realizados)
   - [2.2 Módulo de Usuarios y Roles RBAC (PROC-05)](#22-módulo-de-usuarios-y-roles-rbac-proc-05)
   - [2.3 Módulo de Condominios y Departamentos](#23-módulo-de-condominios-y-departamentos)
   - [2.4 Módulo de Reservas y Áreas Comunes en PostgreSQL (PROC-04)](#24-módulo-de-reservas-y-áreas-comunes-en-postgresql-proc-04)
   - [2.5 Infraestructura y Correcciones Asíncronas](#25-infraestructura-y-correcciones-asíncronas)
   - [2.6 Especificaciones SDD, Contratos OpenAPI y Pruebas BDD](#26-especificaciones-sdd-contratos-openapi-y-pruebas-bdd)
   - [2.7 Recomendaciones de Integración con `main`](#27-recomendaciones-de-integración-con-main)
3. [Bloque 3: Resolución de las 4 Preguntas de Automatización con Bots](#bloque-3-resolución-de-las-4-preguntas-de-automatización-con-bots)
   - [Pregunta 1: ¿Qué tarea repetitiva existe en su proyecto?](#pregunta-1-qué-tarea-repetitiva-existe-en-su-proyecto)
   - [Pregunta 2: ¿Qué datos necesitaría un bot para ejecutarla?](#pregunta-2-qué-datos-necesitaría-un-bot-para-ejecutarla)
   - [Pregunta 3: ¿Qué regla aplicaría?](#pregunta-3-qué-regla-aplicaría)
   - [Pregunta 4: ¿Cómo comprobaría que el resultado es correcto?](#pregunta-4-cómo-comprobaría-que-el-resultado-es-correcto)
4. [Bloque 4: Prompt Recomendado para Generar Diapositivas en Claude](#bloque-4-prompt-recomendado-para-generar-diapositivas-en-claude)

---

# Bloque 1: Overview del Proyecto CondoManager

### 1.1 Contexto del Problema y Justificación
- **El reto habitacional:** En conjuntos residenciales de alta densidad (ej. Villa Bonita 3: 139 departamentos en 14 pisos), la administración sufre de fricciones operativas constantes:
  - Recaudación fragmentada a través de transferencias bancarias múltiples (BCP, BBVA, Interbank) y billeteras móviles (Yape, Plin).
  - Verificación visual y manual de capturas de pantalla de vouchers de pago, propensa a duplicidades y fraudes.
  - Retrasos en el cálculo de moras, generando discusiones vecinales por cobros extemporáneos.
  - Disputas por el uso de áreas comunes (parrillas, salones de eventos) cuando vecinos con deudas vencidas reservan espacios sin control de solvencia.
- **La solución CondoManager:** Una plataforma integral web orientada a eventos que automatiza la facturación por alícuotas, la conciliación de pagos, el corte nocturno de morosidad y el control de acceso en reservas con trazabilidad inmutable.

### 1.2 Propuesta de Valor y Objetivos
1. **Automatización Contable Cero-Error:** Reparto exacto de presupuestos mensuales mediante alícuotas con cierre contable al centavo.
2. **Conciliación Ágil e Idempotente:** Identificación unívoca de comprobantes mediante hashes criptográficos, evitando pagos clonados.
3. **Control Automático de Solvencia:** Inhabilitación en tiempo real para reservar áreas comunes ante deudas vencidas y desbloqueo instantáneo tras la conciliación bancaria.
4. **Transparencia Institucional:** Acceso a portales diferenciados para residentes (con estado de cuenta y botón de pago) y para la Junta Directiva / Auditor Fiscal (con bandejas operativas y métricas).

### 1.3 Metodología Spec-Driven Development (SDD)
CondoManager se rige bajo la regla inquebrantable de **Spec-First**:
- Ninguna línea de código en `src/` se escribe sin contar con su especificación técnica formal en `specs/02-processes-and-automations/proc-XX.md`.
- Toda regla de negocio se modela previamente como escenario BDD (Gherkin: *Dado - Cuando - Entonces*) en `specs/04-acceptance-criteria/`.
- Todos los endpoints y modelos de entrada/salida se congelan en `specs/05-api/api-contracts.md` y OpenAPI 3.0 antes de implementarse en FastAPI.

### 1.4 Los 3 Guardarraíles Técnicos Innegociables
| Guardarraíl | Principio | Implementación Técnica |
| :--- | :--- | :--- |
| **A. Precisión Decimal Absoluta (Zero-Float)** | Prohibido usar `float` para importes monetarios o coeficientes para evitar errores de coma flotante. | Módulo `src.shared.decimal_types` con redondeo `ROUND_HALF_UP`, tipo `Decimal` y columnas `NUMERIC(12, 2)` en PostgreSQL. |
| **B. Bitácora de Auditoría Inmutable** | Toda mutación crítica de saldo, rol, mora o pago debe registrar un snapshot inalterable. | `AuditoriaPayload` (`src.core.audit`) con **los 7 campos obligatorios**: `departamento_id`, `timestamp UTC`, `accion_ejecutada`, `motivo`, `resultado`, `estado_anterior`, `estado_posterior` y hash SHA-256. |
| **C. Invariante de Solvencia en Reservas** | Departamentos con mora vencida no pueden apartar áreas comunes. | Evaluación previa obligatoria en `PROC-04`: si `deuda_vencida > 0.00`, rechazo automático con `403 Forbidden` (`DEUDA_MORA_ACTIVA`). |

### 1.5 Arquitectura y Stack Tecnológico
- **Backend API:** FastAPI (Python 3.12+ / 3.14) con arquitectura asíncrona (`async`/`await`).
- **Persistencia Relacional:** PostgreSQL 16 con motor asíncrono SQLAlchemy 2.0 y soporte transaccional ACID (`asyncpg`).
- **Frontend SPA / SSR:** Next.js 14 App Router, TypeScript, React 18, Tailwind CSS, Lucide Icons.
- **Seguridad & Acceso:** Autenticación JWT con expiración estricta y control de acceso basado en roles (RBAC: `SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`).
- **Almacenamiento de Archivos:** MinIO (compatible con AWS S3) para vouchers de pago y contratos.
- **Infraestructura:** Docker & Docker Compose para orquestación de servicios locales y despliegue continuo.

### 1.6 Mapeo de Módulos Funcionales
| Módulo | Especificación | Descripción |
| :--- | :--- | :--- |
| **Cuotas de Mantenimiento** | `PROC-01` | Emisión mensual masiva basada en alícuotas porcentuales con cierre exacto. |
| **Pagos y Morosidad** | `PROC-02` | Reporte de vouchers, bandeja de conciliación y motor nocturno de moras (gracia de 2 días). |
| **Notificaciones** | `PROC-03` | Despacho multicanal (Email / WhatsApp) con política de reintentos exponenciales. |
| **Reservas y Áreas Comunes** | `PROC-04` | Gestión de parrillas y salones con bloqueo pesimista contra solapamientos de horario. |
| **Usuarios y Roles (RBAC)** | `PROC-05` | Directorio de usuarios, perfiles de residentes, asignación de roles y control de acceso. |
| **Egresos y Proveedores** | `PROC-06` | Registro de facturas, servicios básicos y gastos operativos del condominio. |
| **Incidencias y Tickets** | `PROC-07` | Reporte y seguimiento de averías en ascensores, bombas de agua y áreas comunes. |
| **Reportes e Inteligencia** | `PROC-08` | Reportes contables, balance de ingresos/egresos y métricas de morosidad. |

---

# Bloque 2: Avances Realizados en la Rama `feat/PROC-05-alta-usuarios-y-roles`

### 2.1 Alcance y Commits Realizados
La rama desarrollada por `elesel` (Jerson) incorpora **más de 4,300 líneas de código, contratos y pruebas**, distribuidas en dos hitos principales:
- `90ad0c1` — `feat(PROC-05): alta de usuarios/condominios + fix greenlet asyncio`
- `0af73af` — `feat:creando y conectando los endpoints de crear reserva, area, departamento`

Aunque la rama lleva por nombre `PROC-05`, el avance cubrió la **materialización de la persistencia real en PostgreSQL** para todo el ecosistema de entidades base: Condominios, Departamentos, Áreas Comunes y el circuito de Reservas (PROC-04).

### 2.2 Módulo de Usuarios y Roles RBAC (PROC-05)
- **Endpoints creados:**
  - `POST /api/v1/usuario/crear`: Da de alta a un usuario en el directorio general.
    - Normalización de correo a minúsculas y validación de unicidad (retorna `409 Conflict` con `EMAIL_YA_REGISTRADO` si existe).
    - Cifrado de contraseñas mediante **PBKDF2-SHA256** (`passlib`), asegurando almacenamiento no reversible.
    - Emisión obligatoria de bitácora inmutable con `accion_ejecutada = "ALTA_USUARIO"`.
  - `POST /api/v1/usuario/roles`: Asigna un rol formal (`SUPERADMIN`, `ADMIN_JUNTA`, `AUDITOR`, `RESIDENTE`) a un usuario en un condominio determinado.
    - Verificación de existencia del usuario y del condominio (`404 Not Found`).
    - Validación de unicidad de rol por condominio para evitar duplicidades (`409 Conflict` con `ROL_YA_ASIGNADO`).
    - Emisión de bitácora inmutable con `accion_ejecutada = "ASIGNACION_ROL_USUARIO"`.

### 2.3 Módulo de Condominios y Departamentos
- **Endpoints creados:**
  - `POST /api/v1/condominio/crear`: Registra condominios con su modelo financiero de morosidad (validación entre `regla_mora_tipo` y montos fijados, emitiendo `422 Unprocessable Entity` si la regla es incoherente).
  - `POST /api/v1/departamentos/crear`: Da de alta unidades inmobiliarias asociadas a un condominio.
    - Valida coeficiente de participación (alícuota porcentual).
    - Impide departamentos duplicados con el mismo número dentro del mismo edificio (`409 Conflict` con `DEPARTAMENTO_DUPLICADO`).

### 2.4 Módulo de Reservas y Áreas Comunes en PostgreSQL (PROC-04)
- **Tránsito de Mock a PostgreSQL:** El módulo de reservas abandonó los diccionarios en memoria y se vinculó a tablas relacionales reales (`areas_comunes`, `reservas`, `departamentos`).
- **Endpoints creados y conectados:**
  - `POST /api/v1/areas/crear`: Alta de espacios (aforo máximo, costo por hora, estado activo).
  - `GET /api/v1/areas`: Catálogo de áreas disponibles.
  - `POST /api/v1/reservas`: Generación de reservas con:
    - **Control de concurrencia pesimista:** Uso de `SELECT ... FOR UPDATE` sobre el área común para evitar que dos residentes reserven el mismo horario simultáneamente (`ConflictoHorarioException` $\to$ `409 Conflict`).
    - **Invariante de Solvencia:** Consulta al estado contable del departamento; si tiene deuda en mora, responde con `403 Forbidden` (`DEUDA_MORA_ACTIVA`).
  - `POST /api/v1/reservas/{id}/cancelar`: Liberación de franjas horarias con auditoría.

### 2.5 Infraestructura y Correcciones Asíncronas
- **Fix de concurrencia greenlet en asyncio:** Corrección técnica en [src/core/database.py](file:///home/nicolas/Github-repos/Repos/CondoManager/src/core/database.py) y [config.py](file:///home/nicolas/Github-repos/Repos/CondoManager/src/core/config.py) en la creación de las sesiones asíncronas de SQLAlchemy (`AsyncSessionLocal`), eliminando excepciones de contexto entre hilos (`greenlet_spawn`) al ejecutar consultas concurrentes en FastAPI.
- Integración del gestor de dependencias y lockfile `uv.lock`.

### 2.6 Especificaciones SDD, Contratos OpenAPI y Pruebas BDD
- **OpenAPI 3.0:** Se ampliaron más de 380 líneas en `specs/03-contracts/openapi/condomanager.openapi.yaml` describiendo esquemas y respuestas de los nuevos endpoints.
- **Diccionario de Datos:** Actualizado en `specs/03-contracts/database/data-dictionary.md` con índices, llaves foráneas y tipos `NUMERIC(12,2)`.
- **Criterios de Aceptación Gherkin:**
  - `specs/04-acceptance-criteria/usuarios-condominios.feature.md` (6 escenarios BDD).
  - `specs/04-acceptance-criteria/reservas-areas.feature.md` (7 escenarios BDD).
- **Pruebas Automatizadas:** Creación de suites de pruebas unitarias (`test_usuarios_condominios_service.py`), pruebas de integración de API (`test_usuarios_condominios_api.py`, `test_areas_departamentos_api.py`) y utilidades de limpieza transaccional (`src/tests/integration/db_pruebas.py`).

### 2.7 Recomendaciones de Integración con `main`
Para integrar esta rama en `main` sin fricciones, se deben coordinar los siguientes puntos:
1. **Unificación del módulo `usuarios`:** En `main` existe la lógica de autenticación JWT (`/login`, `/me`, `security.py`), mientras que en esta rama está el alta de usuarios (`/usuario/crear`, `/roles`). Se deben fusionar ambos servicios en lugar de sobreescribirlos.
2. **Estandarización de rutas:** Ajustar las URIs singulares (`/api/v1/usuario/crear`, `/api/v1/condominio/crear`) a la convención REST en plural del proyecto (`/api/v1/usuarios`, `/api/v1/condominios`).
3. **Aislamiento en pruebas de integración:** Añadir `pytest.skip` condicional en dos pruebas de `test_areas_departamentos_api.py` para que la suite de pruebas pueda ejecutarse sin exigir un contenedor PostgreSQL activo en entornos CI/CD sin base de datos.

---

# Bloque 3: Resolución de las 4 Preguntas de Automatización con Bots

A continuación se presentan las respuestas detalladas y fundamentadas en las especificaciones del proyecto (`PROC-01`, `PROC-02` y `PROC-04`) para estructurar la sección de agentes y bots en las diapositivas.

Se toma como **caso principal y paradigmático** la **Conciliación Inteligente de Comprobantes Bancarios e Imputación de Pagos (PROC-02)**, complementada con el **Motor Nocturno de Moras y Bloqueo de Solvencia**.

---

### Pregunta 1: ¿Qué tarea repetitiva existe en su proyecto?

#### Descripción de la Tarea:
**La Recepción, Validación, Conciliación Bancaria e Imputación Contable de Comprobantes de Pago (PROC-02).**

#### Contexto Operativo:
- En cada ciclo mensual (entre los días 1 y 20), los 139 residentes del edificio realizan pagos de cuotas de mantenimiento mediante diversos canales: transferencias móviles (Yape, Plin), transferencias BCP directas, transferencias interbancarias CCI o depósitos en ventanilla/agente.
- Cada residente sube una fotografía, captura de pantalla o PDF del comprobante al sistema.
- **El cuello de botella manual:** Un miembro de la Junta Directiva (el tesorero) debe:
  1. Abrir cada voucher reportado.
  2. Leer el banco, monto, número de operación y fecha.
  3. Ingresar a la banca por internet del condominio o descargar el extracto de movimientos en Excel.
  4. Comparar visualmente que el abono figure efectivamente en la cuenta corriente bancaria del edificio.
  5. Verificar que el número de operación no haya sido presentado previamente por otro vecino o en un mes anterior.
  6. Calcular mentalmente o en Excel si el importe cubre la deuda más antigua, si amortiza parcialmente una cuota o si genera un saldo a favor.
  7. Cambiar manualmente el estado del pago en el sistema y levantar las restricciones de reservas si el vecino estaba en mora.

#### Impacto del Proceso Manual:
- Consume entre **15 y 25 horas al mes** del tesorero durante los días de vencimiento.
- Sujeto a error humano (aprobar un voucher falso o editado digitalmente con Photoshop).
- Retrasos en la conciliación: si el tesorero demora 48 horas en revisar un voucher, el residente honesto corre el riesgo de ser marcado falsamente como moroso o no poder apartar una parrilla para el fin de semana.

---

### Pregunta 2: ¿Qué datos necesitaría un bot para ejecutarla?

Para que un bot o agente autónomo (ej. `BotConciliadorIA` o un job inteligente) ejecute la conciliación sin intervención humana, requiere consumir dos fuentes de datos sincronizadas:

#### A. Datos del Comprobante Reportado (Entrada del Residente):
1. **Identificador del emisor:** `departamento_id` (o `usuario_id` del residente).
2. **Archivo digital del voucher:** Imagen (PNG, JPG) o PDF almacenado en MinIO (S3).
3. **Metadatos declarados por el residente / extraídos por OCR/Vision:**
   - Entidad financiera / canal (`banco`: `"BCP"`, `"BBVA"`, `"INTERBANK"`, `"YAPE"`, `"PLIN"`).
   - Código unívoco de transacción (`numero_operacion`: ej. `"04928190"`).
   - Fecha y hora exacta de la transferencia (`fecha_operacion`: ej. `"2026-10-18T14:32:00"`).
   - Importe monetario reportado (`monto`: ej. `"S/ 154.29"`).
4. **Firma criptográfica de origen:** `idempotency_hash` generado como:
   $$\text{Hash} = \text{SHA256}(\text{departamento\_id} + \text{banco} + \text{numero\_operacion} + \text{monto} + \text{fecha})$$

#### B. Datos del Extracto Bancario Oficial (Fuente de Verdad Externa):
1. **Flujo de abonos de la cuenta corriente del condominio:** Obtenido mediante webhook de Open Banking, API bancaria de tesorería o ingesta automática del archivo de extracto diario (CSV/OFX).
2. **Campos por registro bancario:**
   - `banco_origen`
   - `numero_operacion_bancaria`
   - `fecha_hora_abono`
   - `monto_acreditado` (positivo en cuenta corriente)
   - `estado_conciliacion_bancaria` (`PENDIENTE` / `CONCILIADO`)

#### C. Datos de Contexto Financiero del Condominio (Base de Datos Interna):
1. **Historial de cuotas del departamento:** Tabla `cuotas_mantenimiento` filtrada por `departamento_id`, ordenada por antigüedad ascendente (`fecha_vencimiento`), con sus campos `monto_original`, `monto_pagado`, `saldo_pendiente` y `estado` (`PENDIENTE`, `EN_MORA`, `PAGO_PARCIAL`).
2. **Saldo a favor actual de la unidad:** `saldo_a_favor` en la tabla `departamentos`.

---

### Pregunta 3: ¿Qué regla aplicaría?

El bot debe aplicar un árbol de decisión estricto basado en las reglas de negocio de `PROC-02`, ejecutando el ciclo de 5 fases estandarizado por el SDD:

```
[ 1. EVENTO ] ──► [ 2. EVALUACIÓN ] ──► [ 3. DECISIÓN ] ──► [ 4. ACCIÓN ] ──► [ 5. VERIFICACIÓN ]
```

#### Regla 1: Unicidad e Idempotencia Criptográfica (Prevención de Fraude)
- Si el `idempotency_hash` del comprobante o el `numero_operacion` ya existen registrados en la tabla `comprobantes_pago` con estado `CONCILIADO` o `EN_REVISION`:
  - **Decisión:** **RECHAZO INMEDIATO**.
  - **Acción:** Marcar comprobante como `RECHAZADO`, motivo: `"Operación bancaria duplicada o ya conciliada previamente."`.

#### Regla 2: Cruce 1 a 1 contra el Extracto Bancario
- El bot busca en los abonos bancarios no conciliados una fila donde coincidan simultáneamente:
  1. `extracto.numero_operacion == comprobante.numero_operacion`
  2. `extracto.monto == comprobante.monto` (precisión Decimal exacta)
  3. `|extracto.fecha - comprobante.fecha| <= Tolerancia (ej. 24 horas)`
- Si no existe coincidencia en el banco:
  - **Decisión:** Mantener en `EN_REVISION` si el pago es reciente (posible retraso interbancario de 48h) o cambiar a `RECHAZADO` si ya transcurrió la ventana de compensación.

#### Regla 3: Prelación Contable de Imputación (Zero-Float)
Una vez validada la existencia del dinero real en el banco, el bot distribuye el importe recibido $\mathbf{M}$ aplicando la estricta **regla de prelación de deudas por antigüedad**:
1. **Paso A — Moras y Recargos:** Liquidar primero cualquier penalidad por mora pendiente de la cuota más antigua.
2. **Paso B — Cuotas Vencidas Anteriores:** Si resta saldo, aplicarlo a la cuota ordinaria/extraordinaria más antigua no cancelada:
   - Si $\mathbf{M} < \text{saldo\_pendiente}$: La cuota pasa a estado `PAGO_PARCIAL` y su saldo pendiente se reduce en $\mathbf{M}$. $\mathbf{M} \leftarrow 0$.
   - Si $\mathbf{M} \ge \text{saldo\_pendiente}$: La cuota pasa a estado `PAGADA`, su saldo pendiente queda en `0.00` y el sobrante se calcula: $\mathbf{M} \leftarrow \mathbf{M} - \text{saldo\_pendiente}$.
3. **Paso C — Cuota del Mes en Curso:** Si aún existe saldo, cubrir la cuota del mes actual.
4. **Paso D — Excedente Contable:** Si tras pagar el 100% de las deudas sobra dinero ($\mathbf{M} > 0.00$), acreditar íntegramente a `departamentos.saldo_a_favor`.

#### Regla 4: Desbloqueo Automático de la Compuerta de Solvencia (PROC-04)
- Si la suma total de cuotas en mora del departamento llega a `0.00`:
  - El estado financiero de la unidad cambia de `EN_MORA` a `AL_DIA`.
  - Se reactiva de manera instantánea la capacidad del residente de solicitar reservas de áreas comunes en el portal web.

#### Regla 5: Postergación Protectora en el Motor de Moras
- Si el cron nocturno de moras evalúa una cuota vencida pero encuentra un comprobante en estado `EN_REVISION`:
  - Se pospone la aplicación del recargo por mora durante 24 horas adicionales, protegiendo al residente honesto mientras el bot culmina la validación bancaria.

---

### Pregunta 4: ¿Cómo comprobaría que el resultado es correcto?

Para garantizar confiabilidad bancaria y apego a los estándares SDD, el sistema somete el resultado a **5 comprobaciones independientes**:

#### Comprobación 1: Ecuación de Cuadratura Contable Zero-Float
El bot evalúa que la suma de todos los movimientos generados coincida exactamente al centavo con el importe bancario, sin pérdida de precisión decimal:
$$\sum (\text{Moras Amortizadas}) + \sum (\text{Cuotas Pagadas}) + \Delta (\text{Saldo a Favor}) \equiv \text{Monto Bancario Depositado}$$
- **Verificación:** Evaluado con tipos `Decimal` en Python. Si la diferencia es distinta de `Decimal("0.00")`, se aborta la transacción y se ejecuta un `ROLLBACK` completo en PostgreSQL.

#### Comprobación 2: Invariante de Conciliación Bancaria Única
- El registro correspondiente en el extracto bancario pasa de `estado = 'PENDIENTE'` a `estado = 'CONCILIADA'`, enlazando la clave foránea `comprobante_id`.
- Se comprueba mediante consulta SQL que ningún registro bancario posea más de un comprobante asociado (relación 1:1 o 1:N controlada).

#### Comprobación 3: Consistencia en la Máquina de Estados
Se valida la coherencia entre el saldo exigible y los estados de negocio:
| Entidad | Estado Esperado | Verificación Lógica |
| :--- | :--- | :--- |
| `ComprobantePago` | `CONCILIADO` | Fecha de conciliación registrada y conciliador identificado como `"BOT_IA"`. |
| `CuotaMantenimiento` | `PAGADA` o `PAGO_PARCIAL` | Si `saldo_pendiente == 0.00` $\implies$ `estado == 'PAGADA'`. |
| `Departamento` | `AL_DIA` o `EN_MORA` | Si $\sum (\text{deuda\_vencida}) == 0.00 \implies \text{estado\_financiero} == \text{'AL\_DIA'}$. |

#### Comprobación 4: Bitácora de Auditoría Inmutable (Guardarraíl B)
Se verifica que la tabla `auditoria_logs` contenga un nuevo registro inmutable con los **7 campos obligatorios**:
```json
{
  "departamento_id": "302",
  "timestamp": "2026-10-18T14:35:01Z",
  "accion_ejecutada": "CONCILIACION_PAGO_AUTOMATICA",
  "motivo": "Cruce 1:1 con abono BCP op 04928190 y liquidacion de cuota 2026-10 segun prelacion PROC-02.",
  "resultado": "EXITOSO",
  "estado_anterior": {
    "cuota_2026_10_saldo": "154.29",
    "departamento_estado": "EN_MORA",
    "voucher_estado": "EN_REVISION"
  },
  "estado_posterior": {
    "cuota_2026_10_saldo": "0.00",
    "departamento_estado": "AL_DIA",
    "voucher_estado": "CONCILIADO",
    "saldo_a_favor": "0.00"
  }
}
```
*Se calcula y almacena el hash criptográfico SHA-256 del registro para prevenir cualquier alteración directa en la base de datos.*

#### Comprobación 5: Verificación de Entrega de Notificación al Residente
- El sistema comprueba que se haya insertado un registro en `notificaciones_logs` con `tipo_evento = 'PAGO_CONCILIADO'`, `estado = 'ENTREGADO'` (o `'PENDIENTE'`), y que el recibo de pago digital haya sido despachado al correo y teléfono del vecino vía `PROC-03`.

---

# Bloque 4: Prompt Recomendado para Generar Diapositivas en Claude

> **Instrucciones para el usuario:**  
> Copia y pega el texto a continuación directamente en **Claude** (o en Claude Artifacts) para generar automáticamente una presentación visual interactiva o un código HTML/Marp con diapositivas elegantes.

````markdown
Actúa como un Diseñador de Presentaciones Ejecutivas y Arquitecto de Software Senior.
Utilizando la información detallada en el documento de CondoManager, genera una presentación de 10 a 12 diapositivas con un diseño moderno, limpio y profesional (estilo Bento UI / Tech Corporate).

Estructura requerida de las diapositivas:
- Slide 1: Portada (CondoManager: Automatización de Cobranzas, Morosidad y Reservas bajo Spec-Driven Development).
- Slide 2: El Problema en Edificios de Alta Densidad (Caso Villa Bonita 3: 139 departamentos, fricción de pagos manuales).
- Slide 3: Propuesta de Valor y Metodología SDD (Spec-First, BDD Gherkin y trazabilidad absoluta).
- Slide 4: Los 3 Guardarraíles Técnicos Innegociables (Zero-Float con Decimal, Auditoría de 7 campos inmutable, Compuerta de solvencia).
- Slide 5: Arquitectura y Stack Tecnológico (FastAPI asíncrono, PostgreSQL 16, Next.js 14, MinIO, Docker).
- Slide 6: Avances Clave en la rama `feat/PROC-05` (Alta de condominios, persistencia real de reservas en PostgreSQL, roles RBAC).
- Slide 7: Desafío de Automatización con Agentes/Bots: ¿Qué tarea repetitiva existe? (La pesadilla de la conciliación manual de vouchers).
- Slide 8: Insumos y Datos que necesita el Bot (Vouchers OCR, hashes SHA-256, extracto bancario en tiempo real, histórico de cuotas).
- Slide 9: Reglas de Decisión del Bot (Idempotencia antifraude, cruce 1:1, prelación contable de imputación y gracia de 2 días).
- Slide 10: Validación y Control de Calidad: ¿Cómo sabemos que el resultado es correcto? (Cuadratura contable, máquina de estados, auditoría inmutable).
- Slide 11: Impacto y Resultados de la Automatización (Ahorro de 20 horas al mes, cero vouchers duplicados, habilitación instantánea de áreas comunes).
- Slide 12: Roadmap y Próximos Pasos (Unificación en rama main, integración de webhooks bancarios, despliegue a producción).

Por favor formatea cada diapositiva con:
- Título conciso.
- Subtítulo explicativo.
- Bullets estructurados con datos cuantitativos.
- Notas del presentador (Speaker Notes) para saber qué decir durante la exposición.
````
