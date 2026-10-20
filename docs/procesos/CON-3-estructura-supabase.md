# CON-3: registro de edificios y departamentos en Supabase

## Uso

1. Arrancar la API y el frontend con la conexión PostgreSQL de Supabase configurada.
2. Ingresar con SUPERADMIN y crear/seleccionar un condominio en Configuración.
3. Abrir Estructura: registrar nombre y total de pisos de cada edificio.
4. Registrar unidades con número, piso y coeficiente porcentual (ej. `0.7200`).
5. Para carga masiva descargar la plantilla, seleccionar CSV, revisar vista previa e
   importar filas válidas. El resultado informa filas creadas, existentes y errores.
6. Activar/desactivar unidades desde la tabla. Solo las activas participan en futuras
   distribuciones; los saldos y el historial permanecen asociados al mismo UUID.

ADMIN_JUNTA utiliza el UUID persistido en su claim `condominio_id`. Para el catálogo
piloto configurar `CONDOMINIO_PILOTO_ID` con el UUID creado por CON-2 y renovar sesión.
AUDITOR tiene acceso de consulta. La pantalla Estructura y los indicadores de Junta
consultan datos persistentes, sin sustituir errores de conexión por departamentos demo.

## Migración desde el backup conocido

El backup del 18/10/2026 tiene revisión `20261008_0002`, tablas `edificios` y
`departamentos` vacías, y relación por edificio. `alembic upgrade head` aplica las
revisiones 0003 y 0004 pendientes y la nueva `20261018_0005`.

0005 verifica tipos, columnas obligatorias, PK, FK CASCADE, claves únicas y checks
antes de adoptar tablas preexistentes. Añade `activo BOOLEAN NOT NULL DEFAULT TRUE`,
check de coeficiente máximo e índices únicos normalizados. Una incompatibilidad o
duplicados normalizados revierten la transacción; se debe corregir el baseline antes
de reintentar, no marcar versiones arbitrariamente con stamp.

En instalaciones nuevas crea las dos tablas. Su downgrade elimina activo y los
índices/check añadidos; conserva las tablas adoptadas. Las tablas nuevas se identifican
con un comentario de procedencia y se eliminan en el downgrade para permitir el ciclo
de CI. El rollback de activo pierde únicamente el dato de actividad, por lo que el
ciclo downgrade/upgrade se verifica en pruebas. Docker ejecuta upgrade head al arrancar.

## Verificación local

```bash
CON3_TEST_DATABASE_URL=postgresql+asyncpg://usuario:clave@localhost:5432/base_pruebas pytest -q src/tests/integration/test_estructura_db.py
pytest -q src/tests/unit/test_estructura_validacion.py src/tests/bdd/test_estructura_bdd.py
```

Las pruebas de integración crean esquemas aleatorios con migraciones y revierten sus
transacciones; no dependen del dataset de demostración. En CI también se admite
`CON13_TEST_DATABASE_URL`, ya configurada en Backend / Migraciones.
