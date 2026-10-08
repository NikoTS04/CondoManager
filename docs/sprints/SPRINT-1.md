# Sprint 1 — Finanzas y datos

## Objetivo

Establecer la estructura funcional del condominio y entregar el flujo básico para registrar presupuestos, emitir cuotas, aplicar saldos a favor y reportar comprobantes de pago. El Sprint 1 contiene **8 historias de usuario y 44 puntos**.

## Alcance y asignación

| Jira | Historia | ID funcional | Puntos | Responsable | Dependencias |
|---|---|---|---:|---|---|
| **CON-2** | Configurar un condominio | USR-01 | 5 | **Gerardo** | Ninguna |
| **CON-3** | Registrar edificios y departamentos | USR-02 | 8 | **Jerson** | CON-2 |
| **CON-9** | Registrar el presupuesto mensual | CUE-01 | 3 | **Gerardo** | CON-2 |
| **CON-10** | Configurar el método de distribución | CUE-02 | 5 | **Alejandro** | CON-2 y CON-3 |
| **CON-11** | Emitir automáticamente las cuotas mensuales | CUE-03 | 8 | **Nicolás (Tarqui)** | CON-3, CON-9 y CON-10 |
| **CON-13** | Aplicar automáticamente saldos a favor | CUE-05 | 5 | **Alejandro** | Contrato de CON-11 para la integración final |
| **CON-22** | Reportar un comprobante de pago | PAG-01 | 5 | **Anderson** | Contrato de CON-3 para la integración final |
| **CON-23** | Evitar comprobantes duplicados | PAG-02 | 5 | **Brandon** | Contrato de CON-22 para la integración final |

La asignación corresponde únicamente a historias de usuario. Las tareas técnicas de PostgreSQL, migraciones generales, logs, infraestructura y datos semilla se gestionan por separado.

## Dependencias y trabajo en paralelo

```text
CON-2 ──┬──> CON-3 ──┬──> CON-10 ──┐
        │             │             ├──> CON-11 ──> CON-13
        └──> CON-9 ───┴─────────────┘

CON-22 ───────────────> CON-23
```

- **Flujo principal:** CON-2 → CON-3/CON-9 → CON-10 → CON-11.
- **Aplicación de saldos:** CON-13 puede desarrollar y probar su cálculo de forma aislada; se integra con cada cuota creada por CON-11.
- **Flujo paralelo de pagos:** CON-22 y CON-23 pueden construirse con contratos y datos de prueba sin esperar la emisión de cuotas. Su integración final utiliza los identificadores persistentes de condominio y departamento.
- CON-11 es la historia de integración del flujo de cuotas y solo queda terminada cuando consume un presupuesto aprobado y el método de distribución configurado.

## CON-2 — Configurar un condominio

**Historia:** Como superadministrador, quiero registrar y configurar un condominio, para que sus operaciones se administren de manera independiente.

**Debe incluir:**

- Registro de nombre, dirección, moneda y reglas generales de cobranza.
- Configuración del día de vencimiento, días de gracia y modalidad de mora.
- Acceso de creación restringido al rol `SUPERADMIN`.
- Persistencia del condominio como entidad activa y devolución de su identificador.
- Aislamiento: las consultas y operaciones deben conservar el contexto del condominio correspondiente.

**Se considera terminada cuando:** un SuperAdmin puede crear y consultar el condominio; un usuario sin autorización recibe un rechazo; y una prueba confirma que los datos de dos condominios no se mezclan.

**Trazabilidad:** [backlog](../../Backlog-Jira-Historias-Usuario-CondoManager.md), [lenguaje del dominio](../../specs/00-core/ubiquitous-language.md), [modelo de entidades](../../specs/03-data-models/domain-entities.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [seguridad y RBAC](../../specs/01-architecture/security-and-rbac.md).

## CON-3 — Registrar edificios y departamentos

**Historia:** Como administrador, quiero registrar o importar edificios y departamentos, para disponer de la estructura inmobiliaria sobre la cual operar.

**Debe incluir:**

- Registro de edificios pertenecientes a un condominio.
- Registro manual de departamentos con número, piso, edificio y coeficiente de participación.
- Importación mediante CSV con vista previa del resultado.
- Validación de números repetidos dentro del mismo edificio.
- Reporte por fila de datos inválidos, conservando las filas válidas sin duplicarlas al reintentar.
- Uso de precisión `NUMERIC(7,4)` o `Decimal` para los coeficientes.

**Se considera terminada cuando:** se pueden registrar e importar edificios y departamentos persistentes, se identifican los errores de importación y se impiden duplicados dentro del mismo edificio.

**Trazabilidad:** [dominio de usuarios y departamentos](../../specs/02-domains/05-usuarios-rbac/spec.md), [modelo de entidades](../../specs/03-data-models/domain-entities.md), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [datos piloto](../../specs/05-operations/seed-data-spec.md).

## CON-9 — Registrar el presupuesto mensual

**Historia:** Como miembro de la junta, quiero registrar el presupuesto aprobado del periodo, para utilizarlo como base de las cuotas de mantenimiento.

**Debe incluir:**

- Condominio, periodo `YYYY-MM`, moneda, monto total y fecha de vencimiento.
- Estados que permitan diferenciar como mínimo un presupuesto en preparación de uno aprobado.
- Aprobación y modificación restringidas a usuarios autorizados.
- Un presupuesto ordinario vigente por condominio y periodo.
- Registro del actor y fecha de aprobación.
- Bloqueo de la emisión de cuotas cuando no exista un presupuesto aprobado.

**Se considera terminada cuando:** el presupuesto queda persistido y aprobado, los usuarios no autorizados no pueden modificarlo y CON-11 puede recuperarlo por condominio y periodo.

**Trazabilidad:** [especificación de cuotas](../../specs/02-domains/01-cuotas/spec.md), [proceso de cuotas](../../specs/02-processes-and-automations/proc-01-cuotas-mantenimiento.md), [lenguaje del dominio](../../specs/00-core/ubiquitous-language.md), [auditoría](../../specs/01-architecture/audit-and-traceability.md).

## CON-10 — Configurar el método de distribución

**Historia:** Como administrador, quiero definir si las cuotas se calculan por alícuota o de forma equitativa, para aplicar la regla aprobada por el condominio.

**Debe incluir:**

- Selección entre distribución `POR_ALICUOTA` y `EQUITATIVA`.
- Persistencia de la modalidad que utilizará el periodo de emisión.
- Validación de que las alícuotas de todos los departamentos activos sumen exactamente `100.0000 %` antes de usar la modalidad porcentual.
- Distribución equitativa entre la cantidad de departamentos activos.
- Cálculos exclusivamente con `Decimal` y redondeo `ROUND_HALF_UP` a dos decimales.
- Mensaje claro cuando la configuración no pueda utilizarse por datos incompletos o coeficientes inválidos.

**Se considera terminada cuando:** ambas modalidades pueden configurarse y sus cálculos producen resultados deterministas, sin utilizar `float`.

**Trazabilidad:** [especificación de cuotas](../../specs/02-domains/01-cuotas/spec.md), [ADR de precisión decimal](../../specs/01-architecture/adr/ADR-002-decimal-accounting.md), [escenarios de cuotas](../../specs/02-domains/01-cuotas/features/cuotas.feature), [tipos decimales](../../src/shared/decimal_types.py).

## CON-11 — Emitir automáticamente las cuotas mensuales

**Historia:** Como administrador, quiero que el sistema emita las cuotas al comenzar el mes, para evitar cálculos y registros manuales repetitivos.

**Debe incluir:**

- Ejecución programada en el día configurado y una forma controlada de ejecución manual.
- Lectura del presupuesto aprobado desde CON-9; el cliente no debe poder sustituir libremente su monto durante la emisión.
- Lectura de los departamentos activos y del método configurado en CON-10.
- Generación transaccional de una cuota por departamento activo.
- Ajuste determinista de redondeo para que la suma emitida coincida exactamente con el presupuesto.
- Idempotencia por condominio y periodo: una segunda ejecución no crea cuotas duplicadas.
- Registro de auditoría y emisión del evento `CuotasEmitidasEvent`.

**Se considera terminada cuando:** el lote completo se genera desde información persistente, el total coincide con el presupuesto aprobado y repetir la operación no altera ni duplica el resultado.

**Trazabilidad:** [especificación de cuotas](../../specs/02-domains/01-cuotas/spec.md), [proceso de cuotas](../../specs/02-processes-and-automations/proc-01-cuotas-mantenimiento.md), [contrato de API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml), [escenarios BDD](../../specs/02-domains/01-cuotas/features/cuotas.feature), [idempotencia](../../specs/01-architecture/idempotency-and-deduplication.md).

## CON-13 — Aplicar automáticamente saldos a favor

**Historia:** Como residente, quiero que mi saldo a favor se descuente de las nuevas cuotas, para pagar únicamente el importe neto pendiente.

**Debe incluir:**

- Consulta del saldo a favor disponible al procesar cada nueva cuota.
- Si el saldo cubre toda la cuota, cambio de la cuota a `PAGADA` y conservación del remanente.
- Si el saldo cubre solo una parte, cambio de la cuota a `PENDIENTE` por la diferencia y consumo total del saldo disponible.
- Cálculos con `Decimal`, sin producir cuotas ni saldos negativos.
- Actualización atómica de la cuota y el saldo para impedir consumos dobles ante reintentos o concurrencia.
- Registro del descuento y del saldo restante en la auditoría inmutable.
- Integración con la emisión de CON-11 sin alterar el total bruto distribuido del presupuesto.

**Se considera terminada cuando:** los casos de cobertura total, parcial y saldo inexistente producen el importe neto correcto, conservan cualquier remanente y dejan evidencia auditable sin aplicar el mismo saldo dos veces.

**Trazabilidad:** [especificación de cuotas](../../specs/02-domains/01-cuotas/spec.md), [escenarios de cuotas](../../specs/02-domains/01-cuotas/features/cuotas.feature), [proceso de cuotas](../../specs/02-processes-and-automations/proc-01-cuotas-mantenimiento.md), [lenguaje del dominio](../../specs/00-core/ubiquitous-language.md), [auditoría](../../specs/01-architecture/audit-and-traceability.md), [máquina de estados](../../specs/02-domains/01-cuotas/state-machine.md).

## CON-22 — Reportar un comprobante de pago

**Historia:** Como residente, quiero registrar los datos y la evidencia de mi pago, para que la junta pueda validarlo.

**Debe incluir:**

- Solicitud `multipart/form-data` con departamento, banco, número de operación, fecha, monto y archivo del voucher.
- Voucher obligatorio en formato PNG, JPG o PDF, aplicando un límite de tamaño configurado y documentado.
- Validación de que el usuario pueda operar sobre el departamento indicado.
- Almacenamiento seguro del archivo y persistencia de su referencia, sin exponer rutas internas.
- Registro inicial del comprobante en estado `EN_REVISION`.
- Ninguna modificación del saldo o estado financiero antes de la conciliación.
- Respuesta `202 Accepted` con identificador, estado y mensaje de recepción.

**Se considera terminada cuando:** un residente autorizado puede enviar un voucher válido, el archivo y sus datos quedan persistidos en `EN_REVISION`, y las entradas inválidas o no autorizadas se rechazan sin afectar saldos.

**Trazabilidad:** [especificación de pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [proceso de pagos](../../specs/02-processes-and-automations/proc-02-pagos-y-morosidad.md), [contrato de API](../../specs/05-api/api-contracts.md), [OpenAPI](../../specs/03-contracts/openapi/condomanager.openapi.yaml), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [máquina de estados](../../specs/02-domains/02-pagos-y-moras/state-machine.md).

## CON-23 — Evitar comprobantes duplicados

**Historia:** Como tesorero, quiero que el sistema detecte vouchers repetidos, para evitar doble aplicación o reutilización de un pago.

**Debe incluir:**

- Función aislada y determinista para normalizar los datos y calcular el hash SHA-256.
- Fórmula canónica: `SHA256(condominio_id|banco|numero_operacion|fecha_operacion|monto)`.
- Banco en mayúsculas y sin espacios; operación sin espacios ni ceros iniciales; fecha `YYYY-MM-DD`; monto decimal con dos posiciones.
- Restricción única sobre `idempotency_hash` en la base de datos para proteger también solicitudes concurrentes.
- Si el comprobante ya está aprobado, respuesta `409` con `VOUCHER_YA_CONCILIADO`.
- Si continúa en revisión, devolución del registro previo con `VOUCHER_EN_EVALUACION`, sin crear otro.
- Pruebas unitarias, de integración y de concurrencia para confirmar que solo existe un registro.

**Se considera terminada cuando:** entradas equivalentes generan el mismo hash, ningún reintento crea un segundo comprobante y la respuesta distingue entre un voucher conciliado y uno todavía en evaluación.

**Trazabilidad:** [política de idempotencia](../../specs/01-architecture/idempotency-and-deduplication.md), [especificación de pagos](../../specs/02-domains/02-pagos-y-moras/spec.md), [escenario BDD](../../specs/02-domains/02-pagos-y-moras/features/pagos_y_moras.feature), [diccionario de datos](../../specs/03-contracts/database/data-dictionary.md), [resiliencia y excepciones](../../specs/01-architecture/resilience-and-exceptions.md).

> Para este sprint, la política de idempotencia enlazada arriba es la fuente canónica. El proceso PROC-02 contiene una versión abreviada de la combinación y deberá alinearse posteriormente para evitar interpretaciones distintas.

## Definición de Terminado del Sprint

Una historia se considera terminada cuando cumple sus criterios de aceptación, persiste los datos requeridos, respeta autorización y aislamiento por condominio, actualiza sus contratos o especificaciones si corresponde, incluye pruebas automatizadas y pasa la revisión de otro integrante del equipo.

