# CON-22 / CON-70 / CON-42 — Integración financiera de Anderson

## Alcance y compatibilidad

Se reutilizan cuotas, lotes, presupuestos y aplicaciones de saldo a favor de Sprint
1. No se sustituyen identidad, catálogo, calendario ni notificaciones de otros
responsables. El reporte JSON y los nombres públicos actuales se conservan.
Los adaptadores de prueba no constituyen almacenamiento de producción.

## Voucher local temporal (decisión del responsable del proyecto)

Durante este periodo se reemplaza S3 por `uploads/vouchers/`, configurable mediante
`VOUCHERS_DIR`. `comprobantes_pago.url_voucher` contiene **solo el nombre generado
por el servidor** (`UUID.png`, `UUID.jpg` o `UUID.pdf`), nunca una ruta o URL.
Se conserva el tipo TEXT y no se reescriben referencias históricas automáticamente.
Los archivos no se versionan. Docker monta la carpeta del host. Compartir datos
requiere un mismo backend, PostgreSQL y carpeta; hacer push no comparte vouchers.

1. `POST /pagos/vouchers`, multipart con `departamento_id` y `voucher_file`, valida
   permisos, contenido real PNG/JPEG/PDF y un máximo de 5 MiB. Devuelve 201 con
   `url_voucher`, `content_type` y `size_bytes` después de guardar archivo y registro.
2. La subida queda vinculada al actor y departamento. Solo puede adjuntarse una
   vez; no se acepta un nombre arbitrario ni una subida de otro usuario/unidad.
3. `POST /pagos/reportar` conserva el JSON existente, pero `url_voucher` referencia
   una subida local válida. Un registro nuevo devuelve 202 EN_REVISION después del
   commit, sin cambiar cuotas, saldos ni solvencia.
4. `GET /pagos/{id}/voucher` entrega el archivo como adjunto solo a quienes pueden
   consultar el comprobante. Nunca se publica la carpeta como estáticos ni se
   descargan URLs históricas desde el servidor. Referencias históricas sin archivo
   local producen un error controlado, conservando el registro.
5. Una subida fallida limpia su archivo. Las subidas abandonadas se recuperan con
   limpieza de pendientes no adjuntados de más de 24 horas. La limpieza bloquea el
   registro y no borra evidencia adjuntada. Las interrupciones no producen un
   reporte exitoso incompleto; no existe transacción distribuida entre disco y SQL.

## Idempotencia y revisión

Se reutiliza SHA256(condominio|banco|operacion|fecha|monto), con normalización de
espacios, ceros no significativos y dos decimales. PostgreSQL impone unicidad.
Duplicado propio EN_REVISION: 200 y `VOUCHER_EN_EVALUACION`, mismo identificador.
Aprobado: 409 `VOUCHER_YA_CONCILIADO`. Otra unidad: 409
`VOUCHER_UNIDAD_DISTINTA`, sin revelar identificador ni estado ajenos. Otros estados
requieren revisión administrativa; no se crea un segundo comprobante equivalente.

EN_REVISION u OBSERVADO pueden pasar a APROBADO, OBSERVADO o RECHAZADO. Observar y
rechazar requieren motivo y no aplican fondos. APROBADO y RECHAZADO son terminales
en este alcance: una revisión repetida devuelve 409, nunca vuelve a imputar fondos.
La consulta mantiene el alias público CONCILIADO para APROBADO y añade OBSERVADO.

La aprobación bloquea condominio, departamento y cuotas; aplica primero mora,
después extraordinaria vencida, ordinaria vencida y ordinaria vigente, en orden
de vencimiento e identificador. Los pagos previos de una cuota se distribuyen por
ese mismo orden para calcular sus componentes pendientes. Los descuentos reducen
la obligación ordinaria; solo se imputan componentes existentes en el total
exigible. No se anticipan cuotas ordinarias futuras. El remanente incrementa saldo
a favor con validación de NUMERIC(12,2). Se persisten imputaciones y resultado de
revisión (monto aplicado, saldo restante, crédito y permiso de reserva).

Cambios, auditoría de siete campos con hashes encadenados y outbox se confirman en
una transacción. Se mantiene el bloqueo por condominio usado por emisión y saldos.
Un relay independiente publica el envelope existente en
`condomanager:domain-events` después del commit. Entrega al menos una vez con
event_id estable; el consumidor de Alejandro deduplica. Recepción, aprobación,
observación y rechazo tienen eventos y resultados persistidos, no datos simulados.

## Solvencia (contrato de integración CON-41)

La deuda en mora es la suma positiva `monto_total_exigible - monto_pagado` de cuotas
que ya agotaron `fecha_vencimiento + dias_gracia`, evaluada por fecha UTC. Una cuota
ya EN_MORA conserva esa condición mientras tenga saldo. La gracia se toma de la
configuración persistida, no de constantes de la interfaz. Un reporte EN_REVISION
no paga una deuda ni suspende una mora previa; la postergación protectora del motor
de nuevos recargos no equivale a solvencia. Las cuotas futuras no bloquean.

El guard transaccional de solvencia valida identidad contextual, unidad activa y
condominio activo, bloquea condominio/departamento y mantiene la sesión abierta
hasta que CON-41 termina su operación. Brandon puede usar esa misma sesión para
persistir la reserva; la persistencia del calendario sigue siendo CON-73/CON-41.
El bloqueo devuelve 403 DEUDA_MORA_ACTIVA, saldo autorizado y auditoría FALLIDO,
sin crear reserva ni evento de confirmación. No se mantienen permisos manuales o
en memoria: extinguir la deuda mediante pago confirmado habilita el siguiente
intento, independientemente para cada unidad de un usuario.

## Verificación

Migraciones en PostgreSQL vacío y con tablas preexistentes, conservación de datos,
sesiones independientes, reinicios, rollback, carreras de reporte/revisión,
seguridad del archivo, aislamiento por unidad y cuatro roles. Cada mutación usa
Decimal/NUMERIC, nunca float. Las pruebas de contrato de módulos ajenos pueden
aislar el guard mediante inyección; la aceptación financiera usa PostgreSQL real.
