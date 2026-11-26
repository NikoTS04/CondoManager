# Contrato de integración CON-48/49 con CON-51/52

**Estado:** contrato técnico para implementación; no acredita que CON-48/49 ni
CON-51/52 estén integradas o terminadas.

## 1. Objetivo y límites

CON-51/52 define el contrato que consumirá el módulo de egresos. El desarrollo de
`src/modules/egresos/` puede comenzar sin esperar la FK física de proveedores. La
integración desplegable requiere posteriormente las tablas reales de CON-48/49,
la migración de FK y pruebas conjuntas.

Responsabilidades:

- **CON-48/49 — proveedores:** administrar proveedores, contratos/pólizas,
  versiones y sus documentos. No administrar egresos, aprobaciones, pagos a
  proveedor ni caja.
- **CON-51/52 — egresos:** registrar gasto, relacionar referencias opcionales,
  gestionar evidencia, aprobación, confirmación de pago y ledger operativo.
- **`src/modules/pagos/`:** conservar conciliación de ingresos y comprobantes de
  residentes. No reutilizar modelos, estados ni endpoints para pagos salientes.
- **Presupuestos y fondos de moras:** el presupuesto define conceptos/importes
  previstos; las moras financiadas conservan su ledger 0020 separado. Ninguno
  representa una transferencia al proveedor.

## 2. Contrato de proveedor

`egresos.proveedor_id` es un UUID nullable. Si no aplica proveedor, permanece
`NULL`. Si tiene valor, el servicio de egresos valida que el proveedor exista,
esté dentro del mismo condominio y sea asociable conforme a la política de
proveedores inactivos que acuerde el equipo.

El módulo de egresos conserva la relación por UUID; no replica campos editables.
La lectura usada por selector/detalle debe exponer como mínimo:

| Campo | Tipo | Requisito |
|---|---|---|
| `id` | UUID | Identificador estable consumido por egresos. |
| `condominio_id` | UUID | Validación de aislamiento; nunca confiar solo en el parámetro enviado por UI. |
| `ruc` | string de 11 dígitos | Mostrar y reconocer la identidad fiscal. |
| `razon_social` | string | Mostrar en selección, detalle e historial. |
| `activo` | boolean | Informar disponibilidad para nuevos egresos; el tratamiento histórico/inactivo se confirma con negocio. |

El DTO de detalle de egreso puede contener una proyección de lectura con esos cinco
campos. No convierte esos datos en una copia autoritativa ni sustituye la relación
al proveedor.

## 3. Contrato de contrato/póliza

`egresos.contrato_id` es nullable. Si se envía, el servicio debe validar:

1. El contrato existe y pertenece al `condominio_id` del egreso.
2. El contrato pertenece al `proveedor_id` seleccionado.
3. El estado/vigencia cumple cualquier regla que Tesorería apruebe.

No se exige contrato para todos los gastos sin una regla expresa. El DTO mínimo
de lectura del contrato incluye `id`, `condominio_id`, `proveedor_id`, `estado`,
`fecha_inicio`, `fecha_fin`, `moneda` y `numero_contrato`; contrato y vigencia no
son sinónimos de factura, egreso ni pago.

## 4. Conceptos, presupuesto y pagos

- `concepto_id` referencia `ConceptoPresupuestal`; egresos no mantiene su propio
  catálogo de categorías.
- El vínculo a `presupuesto_id`/`item_presupuesto_id` es opcional y contextual.
  No edita presupuestos aprobados, no cambia cuotas emitidas y no afirma que el
  proveedor cobró.
- El alta del gasto no crea pago ni movimiento de caja.
- Aprobar autoriza el importe/versiones establecidos por la política; no acredita
  que se ejecutó una transferencia.
- Confirmar pago requiere evidencia bancaria, apertura de caja conciliada e
  idempotencia. Fondo de moras no es caja de proveedores.

## 5. Referencias antes y después de integrar proveedor

Antes de la integración de CON-48/49, el contrato y el módulo de egresos definen
`proveedor_id`/`contrato_id` como UUID nullable. Egresos puede implementar
schemas, servicios, endpoints, UI, auditoría y pruebas unitarias con un port/
adapter de lectura que se resuelve al integrar el módulo real. No se crean
proveedores falsos, tablas placeholder, imports a clases inexistentes ni una FK
que apunte a una tabla aún ausente.

En esta fase, si se recibe uno de esos UUID y el proveedor no está disponible para
validarlo, la operación debe responder `409 PROVEEDOR_NO_DISPONIBLE` (no asumir
que existe ni persistir una referencia no comprobada). Proveedor ausente (`NULL`)
continúa permitido. Una vez integrado, el adapter consulta la tabla/API real.

La primera migración del módulo puede crear columnas UUID nullable sin FK. Tras
integrar `proveedores` y `contratos_proveedor`, una migración posterior comprueba
que toda referencia existente sea válida/contextual y añade FKs. Si no se puede
garantizar consistencia con una FK simple, validar con servicio y coordinar una
clave única compuesta de contexto antes de modificar el esquema proveedor.

## 6. Documentos y almacenamiento

Documentos de contratos/pólizas son responsabilidad de CON-49. Sustentos de
egreso, evidencia de pago y evidencia de apertura de caja son responsabilidad de
CON-51/52. No se debe enlazar directamente una versión de contrato como si fuera
factura o constancia de pago.

Ambos módulos deben coordinar un adapter de almacenamiento privado con:

- validación binaria/contenido, MIME y límite de tamaño;
- clave opaca generada por servidor, hash y tamaño persistidos;
- autorización por condominio/recurso al consultar;
- respuesta inline no-cache, sin URL pública ni ruta local;
- preservación de versiones y actor/fecha de cada carga.

La implementación de CON-49 en la rama de referencia usa PDF y 3 MiB en su
servicio y persiste `archivo_binario` en DB. No se declara automáticamente
compatible con los documentos de egreso: formato, tamaño, ubicación final y
migración del storage deben acordarse; no se exige rehacer CON-49 si supera los
controles y se puede interoperar de forma segura.

## 7. Roles y autorización

Se usan los roles existentes `ADMIN_JUNTA`, `SUPERADMIN` y `AUDITOR`. Egresos
valida condominio real y relaciones de proveedor/contrato. Auditor consulta, no
escribe. El registrador no aprueba su egreso. No crear roles nuevos ni confiar en
un `condominio_id` seleccionado desde frontend como autorización.

Qué rol administra el umbral, configura pagos parciales o abre caja se confirma
con Tesorería/producto. Mientras no haya política vigente, bloquear esa operación
con error explícito; no conceder permiso por defecto.

## 8. Archivos compartidos que requieren coordinación

Evitar modificaciones simultáneas sin dividir tareas/revisar el diff conjunto:

- `src/main.py` (registro de routers).
- `frontend/src/features/junta/JuntaNav.tsx`.
- `frontend/src/features/junta/JuntaPortal.tsx`.
- `frontend/src/lib/api.ts`.
- `specs/03-contracts/openapi/condomanager.openapi.yaml`.
- `specs/03-contracts/database/data-dictionary.md`.
- `migrations/versions/*` y configuración de tests PostgreSQL.
- adapter de almacenamiento común, si el equipo acuerda extraerlo.

No cambiar `src/modules/pagos/` para reutilizar su conciliación en egresos.

## 9. Alembic y divergencia

Estado de la rama de trabajo al definir este contrato: `HEAD` `0ee2389`, igual a
`origin/develop`, árbol limpio. `alembic heads` informa una cabeza:
`20261126_0026`; la cadena es `20261124_0024` → `20261125_0025` →
`20261126_0026`.

La rama remota de CON-48/49 referencia `20261124_0025` con `down_revision =
20261124_0024`. No repite literalmente el revision ID de develop
(`20261125_0025`), pero compartir el padre histórico produciría una rama Alembic
paralela al integrarla sin adaptar.

Orden requerido para la integración:

1. Brandon prepara una rama de integración actualizada sobre `develop` vigente,
   sin reescribir ni alterar su rama remota compartida.
2. Como la migración de proveedores no está integrada/aplicada según el estado
   revisado, incorporar sus operaciones en una revisión nueva y única cuyo
   `down_revision` sea la cabeza vigente al crearla (en este corte,
   `20261126_0026`). Revisión/fecha exactas las asigna el equipo al generar el
   archivo; no se reutiliza `20261124_0025`.
3. Integrar/probar proveedores y contratos primero. La alerta CON-50 actualmente
   documenta `contrato_id` sin FK; añadir esa FK solo si se acuerda como parte de
   la revisión de integración y no se cambian migraciones ya aplicadas.
4. La migración de egresos crea sus tablas y UUID nullable sin FK a proveedor si
   el módulo avanza antes de aquella integración.
5. Una migración posterior añade FKs hacia proveedores/contratos después de
   validar referencias; caja/ledger se incorpora en la secuencia aprobada, sin
   bifurcar la cabeza.
6. Ejecutar `alembic heads` y exigir una salida única; revisar `alembic history`
   y probar la cadena completa en base de pruebas.

Si se descubre que una revisión de proveedores ya se aplicó en cualquier
ambiente compartido, no editar/reemplazar su historial: detener esa propuesta y
coordinar con el responsable de DB una revisión forward-only compatible.

## 10. Checklist previo a integración

- [ ] DTO proveedor cumple campos mínimos, UUID estable y contexto.
- [ ] Servicio de egresos prueba referencias válidas, inexistentes e intercondominio.
- [ ] Contrato opcional no se convierte en obligatorio por el modelo proveedor.
- [ ] Auditor es solo lectura y los documentos usan autorización contextual.
- [ ] Formato/tamaño/storage/document versioning están acordados.
- [ ] Alembic tiene una única cabeza y no se alteraron revisiones aplicadas.
- [ ] `src/main.py`, OpenAPI y rutas frontend integran ambas features sin duplicarlas.
- [ ] Tests proveedor, egresos, RBAC y documentos pasan en PostgreSQL de pruebas.
- [ ] Conciliación de residentes permanece sin cambios funcionales.
