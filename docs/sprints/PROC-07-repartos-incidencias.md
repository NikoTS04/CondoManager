# Incremento: proveedores y reparto de costos de incidencias

## Alcance

- Proveedor real del directorio activo del condominio; datos de contacto resueltos en backend.
- Reparto independiente de cada costo, con todos los departamentos activos o una selección.
- Partes iguales o alícuotas normalizadas entre participantes, con centavos exactos.
- Previsualización, confirmación idempotente, cargos inmutables y auditoría.
- Selección individual o conjunta de cargos de una unidad y conciliación con voucher.
- Cargos y pagos en el estado de cuenta, sin reasignación por el motor de cuotas.

No se habilitan envíos ni pasarelas. Sin moras, aplicación de crédito, mezcla con cuotas
en el mismo comprobante ni edición/cancelación compensatoria de cargos publicados.
CON-82/83/85 son un bloque separado: este incremento no los declara implementados.

## Migraciones y precaución de despliegue

La base `a49c2c8` contenía dos archivos con revisión `20261127_0027`: asignación de
incidencias y egresos/caja. Se conserva la identidad histórica de incidencias y se
reubica egresos/caja como `20261202_0032`, después de proveedores `20261201_0031`.
El reparto y los destinos de pagos se añaden en `20261203_0033`.
La ejecución SQL de egresos también reveló una FK compuesta hacia reversos sin la
unicidad requerida; se añade `UNIQUE(condominio_id, id)` al modelo y a esa migración.

**No ejecutar el upgrade en Supabase sin inspeccionar antes `alembic_version` y las
tablas de egresos/caja.** Si la antigua migración duplicada de egresos ya se ejecutó,
se necesita una reconciliación específica y respaldo: no volver a crear sus tablas
ni hacer `stamp` ciego. Esta rama no modifica ni migra la base remota.

Las tres tablas nuevas tienen RLS sin políticas públicas y acceso por backend.
No se añaden FK a proveedores históricos ficticios de incidencias: las nuevas
asignaciones sí validan el directorio y las anteriores se conservan.

## Validación local del incremento

- 46 pruebas de reparto, asignación y estado de cuenta aprobadas, con PostgreSQL aislado.
- Cobertura de los tres módulos nuevos de backend: 92,53 %.
- 49 pruebas del frontend aprobadas; TypeScript y build de producción aprobados.
- Verificador SDD aprobado; Spectral sin errores (con advertencias del contrato).
- Cadena Alembic completa ejecutada desde cero en PostgreSQL temporal; RLS de las
  tres tablas nuevas comprobada sin políticas de acceso público.

Pendiente aceptación en navegador y reconciliación del estado real de migraciones
antes de cualquier despliegue. No se ha aplicado este incremento en Supabase.
