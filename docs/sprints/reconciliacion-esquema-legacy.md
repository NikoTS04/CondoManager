# Reconciliación del despliegue legacy — 21 octubre 2026

## Incidente

Docker construía correctamente. Tras corregir la conexión a PostgreSQL, el backend
no arrancaba: Supabase registraba `20261021_0012`, una revisión ajena al grafo
canónico (`20261020_0012` → `20261021_0013`). No era un simple error de fecha:
faltaban columnas de reservas y la cola durable de notificaciones.

## Respaldo y ensayo

- Respaldo local privado: `data/backups/reconciliation-20261021T173017Z/`.
  Contiene `public.dump`, `vouchers.tar.gz`, listado de restauración y manifiesto
  SHA-256. Directorio 0700, archivos 0600; `data/` no se versiona ni entra en Docker.
- `public.dump` es un archivo custom de `pg_dump` 17 con esquema público y datos,
  sin propietarios, ACL, publicaciones ni suscripciones. **No es un respaldo
  integral de Supabase**, ni reemplaza sus respaldos administrados. Los vouchers
  locales se respaldan aparte; no se incluyen objetos S3 remotos.
- Dos restauraciones nuevas sobre PostgreSQL 17 aislado, sin puertos expuestos ni
  conexión de red externa. La reparación se ensayó sobre ambas.
- 33 pruebas de migración/integración correctas; seis casos específicos cubren
  éxito, revisión incorrecta, notificaciones no adoptables, cancelación sin
  evidencia, cobros pendientes y rollback ante fallo posterior al DDL.
- Sobre la copia restaurada: health, sesión, departamentos, comprobantes, reservas
  y notificaciones respondieron 200 con autenticación y repositorios reales.
  No se fabricaron tokens ni se ejecutaron mutaciones funcionales en producción.

## Reparación explícita

`scripts/reconciliar_esquema_legacy.py` es un adaptador operativo **solo para este
marcador y head**, no una migración automática ni una alternativa a Alembic.
No altera archivos históricos ni agrega una segunda raíz ficticia al grafo.

En una única transacción:

1. Exige el marcador legacy exacto; bloquea escrituras y toma huellas de todas las
   columnas originales. Rechaza adopciones parciales, notificaciones legacy con
   registros, cobros de reserva pendientes, cruces de contexto y cancelaciones
   sin evidencia verificable.
2. Conserva la tabla vacía de notificaciones en
   `public_legacy_20261021.notificaciones_logs`, con RLS original y esquema sin
   permisos para PUBLIC. Crea las tablas canónicas faltantes con RLS habilitado.
3. Agrega contexto, moneda y nombre de área a reservas mediante sus relaciones.
   Recupera fecha, actor y motivo desde `cancelaciones_reserva`. No cambia horas,
   zonas horarias, UUID, costos, estados ni los registros originales de cancelación.
4. Conserva los outboxes con su columna `tipo` y su unicidad, que ya coinciden con
   el modelo vigente. No publica ni reescribe eventos históricos.
5. Ejecuta las migraciones canónicas 0013 y 0015 (0014 solo une ramas, sin DDL;
   0015 crea `notificaciones_alertas`), valida columnas, tipos, nulabilidad, PK,
   FK, unicidades y presencia de checks del modelo. Conserva restricciones,
   índices y RLS adicionales compatibles del despliegue.
6. Comprueba las huellas históricas; **solo entonces** cambia el marcador a
   `20261021_0015`. Cualquier fallo revierte también DDL y marcador.

## Aplicación y resultado

Se pausó únicamente el backend. Antes de aplicar se verificaron los SHA-256 del
respaldo y que los registros desplegados seguían coincidiendo con la restauración
ensayada. Se aplicó el adaptador explícitamente usando la configuración existente,
sin imprimir ni cambiar credenciales. Tras el commit se volvieron a comparar las
huellas de las **28 tablas originales**: ninguna columna o fila original cambió.

`docker compose up -d --no-deps --wait --wait-timeout 90 backend` terminó con estado
healthy; `GET http://localhost:8000/api/v1/health` respondió 200. No se iniciaron
workers ni se reprodujeron eventos históricos como parte de esta reparación.

## Procedimiento futuro

El incidente posterior del 26 de octubre tiene un marcador y head diferentes:
ver [recuperación 20261026](reconciliacion-esquema-20261026.md). Su adaptador no
relaja los guards de revisión de este script histórico.

No volver a ejecutar el adaptador contra el head: rechaza revisiones distintas del
legacy. No usar `alembic stamp` ni modificar manualmente `alembic_version` para
sortear errores nuevos. Ante deriva nueva: respaldo nuevo, restauración, comparación
y ensayo nuevo. El script se niega a funcionar si cambia el head canónico.

Para reproducir en una **copia restaurada**, configurar `DATABASE_URL` de esa copia:

```bash
python -m scripts.reconciliar_esquema_legacy --aplicar
```

No hay downgrade destructivo. La recuperación requiere un entorno separado y el
respaldo verificado; no restaurar sobre la base activa sin ventana de mantenimiento
y revisión de cambios posteriores. Copiar el respaldo privado a almacenamiento
seguro y duradero antes de limpiar este equipo.
