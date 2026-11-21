# Estado actual y prioridades — 18/11/2026

## Incremento PROC-03 — 21/11/2026

Integración Mailjet implementada en `feat/PROC-03-mailjet-produccion`:
despacho desde cola SQL, callback autenticado, job de Supabase Cron y recordatorios
deduplicados. Guía de activación: [Mailjet producción](../procesos/MAILJET-PRODUCCION.md).
Remitente autorizado: nicolas.tarqui@unmsm.edu.pe. Mailjet sigue deshabilitado en
el archivo privado de despliegue; los recursos remotos no se configuran desde código.
No se acredita recepción real ni programación remota. WhatsApp/RPA sigue pendiente.
Las secciones siguientes conservan evidencia histórica del corte anterior.

Validación final de este incremento: **869 pruebas backend aprobadas, 0 fallos,
0 omitidas**, 350,96 s, Python 3.14/PostgreSQL 18.7 temporal UTF-8.
JUnit: `/tmp/opencode/mailjet-produccion-final.xml`. **39 pruebas frontend**
aprobadas. Ruff de los archivos de la integración, verificador SDD, contratos
YAML/JSON, registro de rutas/rewrites y `git diff --check` correctos.
No se midió cobertura ni se repitió CI Python 3.12/PostgreSQL 16.

El primer ensayo global usó erróneamente SQL_ASCII: 66 fallos y 15 errores;
se corrigió únicamente la base temporal. En UTF-8 quedaron dos regresiones de
timeouts del simulador (866 aprobadas): se restauró su reintento sin debilitar
la aceptación incierta de PROVEEDOR, con prueba adicional. El pase final anterior
ya incorpora esa corrección. Se conservan 17 warnings de dependencias/pruebas.

Prueba real controlada: Mailjet aceptó una solicitud para cada uno de los dos
correos personales autorizados y devolvió MessageID en ambos casos, sin reintentos
ni consumo de la cola productiva. Esto prueba aceptación del transporte, no
recepción en bandeja ni callback remoto. `.env.deploy` conserva MAILJET_ENABLED=false.

## Continuación: Hobby y Supabase

Ver [guía de despliegue Hobby](../procesos/VERCEL-HOBBY.md). Se incorporan Storage
privado REST, configuración segura, pool sin conexiones persistentes opcional,
CORS explícito, un proyecto Vercel Services y cron diario con lock PostgreSQL.
Redis puede declararse `disabled` en readiness. No se eligió proveedor de correo
ni se configuraron recursos remotos. El perfil remoto usa 3 MiB por voucher,
sin migración automática de archivos anteriores.

Bloqueos preventivos ya tienen API e interfaz en Áreas: crear intervalo futuro,
consultar y levantar sin borrado, con auditoría y exclusión de reservas.
Si afecta una reserva confirmada se rechaza: cancelación/reprogramación y avisos
automáticos siguen pendientes. No se altera la contabilidad de reservas.
Los módulos de extraordinarias, cargos de reserva, egresos y cierres permanecen
pendientes; no se declaran desarrollados mediante esta entrega de infraestructura.

### Preparación para PR a main: Services y Mailjet

Usuario confirmó `app`/`frontend`, binding runtime `APP_URL`, frontend público y
excepción pública protegida de cron. El resto de API atraviesa el proxy Next.js.
Mailjet API/secret ya existen localmente: adapter preparado y desactivado, sin
envíos reales ni despacho automático. Remitente verificado sigue pendiente.
El .env local fue revisado sin divulgar valores y permanece fuera de Git.
Ver correcciones necesarias en `docs/procesos/VERCEL-HOBBY.md`; importar el .env
local tal cual no prepara producción. No se alteró su contenido.

Reconciliación con `origin/main` local (`13c0d16`): se conservaron los cambios
CON-24/79 y sanitización de login ya integrados por otro integrante. La bandeja
usa su contrato canónico `fecha_desde`, `fecha_hasta`, `limit` (1–100, default 50),
su interfaz y catálogo de documentos. Se añadieron descarte de respuestas tardías,
no-cache y Storage Supabase sin sustituir esas capacidades. Las evidencias previas
de esta sesión son cortes anteriores al rebase; la validación final se registra aparte.
`git fetch` no pudo actualizar referencias por falta de autenticación SSH.

Validación final del candidato Services reconciliado: **832 pruebas backend
aprobadas, sin omisiones**, PostgreSQL efímero; **39 frontend** y build Next.js
correctos. Schema oficial Vercel validado. Ver [preparación del PR](PR-MAIN-SERVICES.md)
para alcance, evidencia y bloqueos de publicación. No se enviaron correos reales
ni se alteró/versionó el .env del usuario.

### Verificación de Hobby y bloqueos

- Suite backend final: **804 aprobadas, 0 fallos y 0 omitidas**, 491,59 s,
  Python 3.14/PostgreSQL 18.7 efímero. Salida y JUnit:
  `/tmp/opencode/condo-hobby-verificado.log` y `.xml`.
- Frontend: **36 pruebas aprobadas**, TypeScript, ESLint y build correctos.
- Ruff de todos los archivos Python modificados/nuevos, verificador SDD y contratos
  YAML/JSON correctos. No se afirma que se haya ejecutado Spectral.
- Pruebas de Storage usan transporte HTTP sustituido: validación de contenido y
  tamaño, nombres seguros, autenticación privada, no redirección de credenciales,
  errores saneados y descarga privada. **No son pruebas contra Supabase remoto.**
- Cron: secreto, preview, exclusión, orden estricto y error controlado probados.
  Bloqueos: calendario, conflicto con reserva, liberación repetible y auditoría
  comprobados con PostgreSQL real.
- El primer pase general tuvo 802 aprobadas/1 fallida por una expectativa antigua
  del recuperador de pagos: ahora incluye fondos/moras. La prueba se actualizó
  para verificar consumo completo e idempotente y la suite final pasó íntegra.
- No se desplegó ni se probó Chromium o la cuota real de Vercel. Falta CI
  Python 3.12/PostgreSQL 16, bucket privado remoto, migración de evidencia local
  y ensayo del padrón real dentro del presupuesto de ejecución diario.

Base inspeccionada: `22b8f3b` (PR #40). Este inventario describe el código local,
no certifica Jira, aprobación del equipo ni despliegue. Cabeza: `20261113_0021`.

## Implementación existente

| Área | Implementado | Pendiente relevante |
|---|---|---|
| Estructura e identidad | Condominios, edificios, CSV, usuarios, vínculos, roles, invitación/activación y relevos | Recepción real de invitaciones y avisos de seguridad |
| Cuotas | Presupuesto, distribución, emisión idempotente, créditos, prorrateo, PDF/DOCX | Recorrido completo de extraordinarias con acta/fracciones |
| Pagos | Voucher privado, deduplicación, revisión, subsanación, recibo, parciales, excedentes | Aceptación integrada y correo real del resultado |
| Finanzas | Estado de cuenta, mora diaria, fecha bancaria, fondos y cobertura; ruta manual ficticia retirada con 410 | La evaluación diaria la ejecuta el worker SQL; no hay ejecución manual HTTP sustitutiva |
| Reservas | Catálogo, disponibilidad, solvencia, locks, cancelación, outbox y bloqueos preventivos; fuente única SQL | Cargos contables, reprogramación y avisos de bloqueos afectados |
| Notificaciones | Cola SQL, eventos, intentos, reintentos, alertas y plantillas | **Proveedor por decidir**; recordatorios programados y WhatsApp/RPA |
| Administración integral | Conceptos presupuestales y resumen operativo | Proveedores/contratos/egresos, tickets, cierre contable y balance mensual |

Un PDF de prorrateo no es un balance de ingresos/egresos; una tarifa de reserva no
es un cargo cobrado; ENVIADO simulado no acredita recepción.

## Incrementos de esta rama

1. **Bandeja de conciliación:** filtros SQL combinados, paginación opcional,
   permisos aplicados antes del límite y consulta privada sin caché. Interfaz con
   fechas bancarias inclusivas, unidad, banco y estado, páginas de 25, error/reintento
   y descarte de respuestas anteriores. Conserva el contrato CON-24 de main.
2. **Readiness:** `/api/v1/health/ready` y `/health/ready` comprueban PostgreSQL
   y Redis con timeout. `/health` sigue siendo liveness para no romper sondas
   existentes. Readiness no acredita workers, correo ni acceso al volumen.

No hay nuevas dependencias, migraciones ni cambios de cálculo monetario.
La carga general del portal conserva el listado limitado de CON-24; la tabla
filtrada usa páginas SQL. Sustituir los contadores de esa carga por un resumen agregado es trabajo
posterior si el volumen lo requiere.

3. **CON-80 / fuente única de reservas:** eliminados almacén productivo, mezcla de
   fuentes, rama de creación simulada y adopción piloto durante cancelación.
   Los dobles de memoria viven solo en `src/tests/`. Los errores SQL y las tablas
   requeridas ausentes producen 503. Se conservan transacciones, locks, solvencia,
   auditoría, outbox y respuesta repetible de cancelación.
4. **Mora manual retirada:** `/moras/evaluar` devuelve 410
   `EVALUACION_MANUAL_RETIRADA` a administradores autorizados; no devuelve
   contadores ficticios ni modifica saldos. El worker diario SQL no cambia.

Compatibilidad: clientes que esperaban 200 del simulador manual deben dejar de
invocarlo. Antes de apagar un proceso antiguo, reconciliar expresamente cualquier
reserva que solo existiera en memoria; no se importa ni elimina historia SQL.

## Prioridad siguiente

1. Validar ambiente compartido y recuperación con migración 0021.
2. Tras elegir proveedor: conectar correo y aceptación de identidad/pagos;
   añadir recordatorios deduplicados. No elegir proveedor implícitamente.
3. Egresos/proveedores y cierre mensual; después tickets. IA/RPA de tickets
   permanece como mejora futura, no prerrequisito del flujo básico.

## Evidencia y límites

Las cifras de CON-7/76 (756 pruebas y 92,41 %) son históricas de su corte, no una
nueva ejecución de esta rama ni una medida de compleción de las 61 historias.
Verificación de esta rama (Python 3.14 local):

| Comprobación | Resultado |
|---|---|
| `pytest src/tests/unit src/tests/integration/test_api_endpoints.py src/tests/integration/test_bandeja_db.py -q -rs` | 313 aprobadas, 2 omitidas por falta de PostgreSQL de pruebas |
| `node --test tests/*.test.mjs` desde frontend | 35 aprobadas |
| TypeScript, ESLint y build Next.js de producción | Correctos |
| Ruff y formato en Python de la entrega | Correctos |
| Verificador SDD y `git diff --check` | Correctos |

Las pruebas nuevas cubren validación HTTP, compatibilidad, generación de SQL con
autorización antes de paginar, filtros combinados, timeout/cancelación de la sonda,
fallos sin secretos, parámetros del cliente y controles etiquetados de la interfaz.
Se agregó prueba de filtros sobre PostgreSQL real, **no ejecutada** porque Docker
no tiene daemon accesible y no hay URL exclusiva de pruebas configurada.
Ese límite corresponde al primer incremento. En la continuación se encontró
PostgreSQL local y se creó un clúster efímero bajo `/tmp/opencode`, limitado a
localhost:55489, con esquemas exclusivos por prueba. Se comprobaron 24 casos de
reservas/notificaciones y cancelación, y 11 casos de fuente SQL/retirada manual/
bandeja, sin omisiones. La prueba de bandeja SQL antes omitida ahora pasa.
El segundo proceso ASGI usa otra conexión/fábrica de sesiones sobre ese esquema
de pruebas: consulta historial/calendario, cancela y el proceso original recupera
el mismo resultado, con una única cancelación/evento.
La corrida final de la continuación terminó con **784 pruebas backend aprobadas,
0 fallos y 0 omitidas**, en 560,46 s, sobre Python 3.14 y PostgreSQL **18.7**
local efímero. Incluye los casos SQL/BDD existentes y la prueba de retirada manual
que compara la huella de todas las tablas ORM antes/después del 410.
Las 35 pruebas frontend se repitieron correctamente. Ruff/formato pasan en los
19 archivos Python modificados/nuevos; Ruff global conserva 38 hallazgos previos
fuera del alcance, sin mezclarlos con esta entrega.
JUnit y salida local: `/tmp/opencode/condo-prioridades-final.xml` y
`/tmp/opencode/condo-prioridades-final.log`. El primer intento general se detuvo
por timeout; no se contabiliza como una ejecución completa.
Los contratos YAML y la deprecación del OpenAPI generado se comprobaron, y el
verificador SDD y `git diff --check` pasan. El clúster efímero se detuvo al cerrar.
No se consultó la base operativa ni se ejecutaron Chromium o Spectral.
No se midió nueva cobertura ni se desplegó esta rama; esta ejecución local no
sustituye repetir CI en Python 3.12/PostgreSQL 16 ni la aceptación compartida.
