# Glosario Ubicuo de Dominio (Ubiquitous Language)

Este glosario define la terminología formal y estricta utilizada en el diseño del sistema **CondoManager**. Todos los integrantes del equipo (**Anderson, Tarqui, Alejandro, Brandon, Junta Directiva**), así como las especificaciones, contratos de API, modelos de datos y nombres de clases en el código fuente, deben adherirse rigurosamente a estas definiciones para evitar ambigüedades semánticas.

---

## 1. Estructura Inmobiliaria y Organizacional

| Término en Español | Término en Código (Inglés/Español) | Definición Formal | Invariantes / Restricciones |
| :--- | :--- | :--- | :--- |
| **Condominio** | `Condominio` / `Condo` | Entidad jurídica o agrupación habitacional superior que agrupa uno o varios edificios/torres bajo un mismo reglamento interno y presupuesto común; es la raíz del aislamiento multi-tenant. | Posee UUID generado por el servidor, estado `activo`, moneda principal (`PEN`, `USD`), `dia_vencimiento`, `dias_gracia` y una política de mora global. |
| **Edificio / Torre** | `Edificio` / `Building` | Estructura física vertical o bloque dentro de un condominio que contiene un conjunto determinado de departamentos. | Pertenece a exactamente un condominio. |
| **Unidad / Departamento** | `Departamento` / `Unit` | Bien inmueble de propiedad exclusiva (departamento, flat, dúplex, estacionamiento o depósito) sujeto al régimen de propiedad horizontal. | Posee un número identificador único por edificio y un coeficiente de participación (alícuota). |
| **Alícuota / Coeficiente** | `alicuota` / `share_percentage` | Porcentaje de participación de una unidad sobre las áreas comunes y cargas financieras del condominio. Expresado con 4 decimales (`NUMERIC(7,4)`). | La sumatoria de alícuotas de todas las unidades activas del condominio debe ser exactamente igual a `100.0000%`. |
| **Área Común** | `AreaComun` / `CommonArea` | Espacio o instalación compartida susceptible de uso o reserva (ej. zona de parrillas, salón de eventos, gimnasio, sala de coworking). | Posee aforo máximo, tiempo límite de uso y puede tener costo o depósito de garantía. |

---

## 2. Finanzas, Cobranzas y Recaudación

| Término en Español | Término en Código | Definición Formal | Invariantes / Restricciones |
| :--- | :--- | :--- | :--- |
| **Presupuesto Ordinario** | `PresupuestoOrdinario` | Estimación mensual consolidada de gastos operativos necesarios para el mantenimiento, servicios y seguridad del condominio. | Aprobado periódicamente en asamblea de propietarios. Base para el cálculo de cuotas. |
| **Cuota Ordinaria** | `CuotaOrdinaria` | Obligación financiera periódica (mensual) devengada a cargo de cada departamento para cubrir el presupuesto común. | Calculada mediante alícuota porcentual o cuota fija equitativa. |
| **Cuota Extraordinaria** | `CuotaExtraordinaria` | Aporte dinerario extraordinario fijado para financiar proyectos específicos no cubiertos por el presupuesto (obras, pintura, mejoras). | Fraccionable en 1 a N cuotas mensuales. Requiere acta de aprobación. |
| **Fecha de Vencimiento** | `fecha_vencimiento` / `due_date` | Fecha límite calendario hasta la cual el residente puede abonar su cuota sin incurrir en penalidades (ej. día 20 del mes a las 23:59:59). | Configurable por condominio. |
| **Periodo de Gracia** | `dias_gracia` / `grace_period` | Ventana temporal de tolerancia (ej. 2 días hábiles o calendario) posterior al vencimiento en la que no se aplican recargos aún. | Si transcurre sin pago registrado, se dispara automáticamente el corte de mora. |
| **Mora / Penalidad** | `RecargoMora` / `LateFee` | Cargo punitorio automático que se añade a la deuda exigible de un departamento al vencer la fecha límite más el periodo de gracia. | Puede ser un monto fijo (`S/ 20.00`) o una tasa porcentual sobre el saldo vencido. |
| **Deuda Exigible** | `deuda_exigible` / `total_due` | Suma algebraica de cuotas ordinarias, extraordinarias y moras pendientes de pago menos los saldos a favor acumulados. | $\text{Deuda} = \sum \text{Cargos} - \sum \text{Abonos}$. Precisión estricta `Decimal(12,2)`. |
| **Saldo a Favor** | `saldo_a_favor` / `credit_balance` | Excedente monetario registrado a favor de un departamento, originado por pagos que superaron la deuda o notas de crédito compensatorias. | Se aplica automáticamente como descuento prioritario en la siguiente emisión de cuotas. |
| **Comprobante de Pago** | `ComprobantePago` / `PaymentSlip` | Declaración formal de pago realizada por el residente, respaldada por un voucher digital (captura Yape/Plin o transferencia CCI). | Estado inicial `EN_REVISION`. No afecta el saldo hasta ser validado o conciliado. |
| **Conciliación Bancaria** | `Conciliacion` / `Reconciliation` | Proceso administrativo mediante el cual la Junta Directiva verifica que un comprobante reportado tiene su abono efectivo e idéntico en la cuenta bancaria. | Al aprobarse, genera una transacción inmutable e imputa el saldo a las deudas más antiguas. |
| **Imputación de Pago** | `ImputacionPago` / `PaymentAllocation` | Asignación matemática y contable de los fondos de un pago conciliado siguiendo la regla de prelación legal (Moras $\rightarrow$ Cuotas Antiguas $\rightarrow$ Cuota Actual). | No se puede imputar un monto superior al valor total del comprobante aprobado. |

---

## 3. Estado de Residente y Solvencia

| Término en Español | Término en Código | Definición Formal | Impacto en el Sistema |
| :--- | :--- | :--- | :--- |
| **Al Día / Solvente** | `AL_DIA` / `SOLVENT` | Estado del departamento que no registra cuotas vencidas impagas fuera del periodo de gracia. | Habilitado para solicitar reservas de áreas comunes y emitir votos en asambleas. |
| **En Mora / Moroso** | `EN_MORA` / `DELINQUENT` | Estado del departamento con una o más cuotas vencidas que han superado el periodo de gracia establecido. | **Inhabilitación inmediata y automática para reservar áreas comunes (Invariante PROC-04).** |
| **Observado** | `OBSERVADO` / `UNDER_REVIEW` | Estado de un departamento que reportó un pago que se encuentra en evaluación por discrepancia o voucher borroso. | Se suspende temporalmente la aplicación de mora por 24 horas hábiles. |

---

## 4. Auditoría y Arquitectura de Datos

| Término en Español | Término en Código | Definición Formal |
| :--- | :--- | :--- |
| **Bitácora Inmutable** | `AuditoriaLog` / `AuditLog` | Registro append-only de eventos de negocio donde queda documentada toda mutación de estado con 7 campos mínimos y encadenamiento SHA-256. |
| **Asiento Compensatorio** | `AjusteCompensatorio` | Transacción inversa que anula o rectifica un error contable sin eliminar físicamente ningún registro histórico de la base de datos. |
| **Idempotency Key** | `idempotency_hash` | Hash único generado por operación (`SHA256(condominio + banco + operacion + fecha + monto)`) para evitar transacciones o cargos duplicados. |
| **Bloqueo Pesimista** | `PessimisticLock` (`SELECT FOR UPDATE`) | Mecanismo de concurrencia en PostgreSQL que bloquea transaccionalmente un recurso temporal (área común) para evitar reservas dobles simultáneas. |
