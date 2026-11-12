# Recuperación del despliegue — 26 octubre 2026

## Diagnóstico y alcance autorizado

La imagen coincide con el checkout. PostgreSQL registra solo `20261021_0013`,
pero contiene reservas adoptadas, cobros/cancelaciones y cuatro eventos históricos.
La rama hermana `20261021_0012` intenta recrearlos al arrancar. Además, el outbox
conserva `tipo` nullable y carece de unicidad `(reserva_id, tipo)`.
No se atribuye a una persona o herramienta el cambio del marcador.

No modificar migraciones históricas ni reutilizar el adaptador del 21 de octubre.
El nuevo adaptador se limita al marcador 0013 y head financiero 0020. Requiere
respaldo verificado y ensayo restaurado. En una transacción, bajo locks:

1. Validar contexto y evidencia de cancelación, tipos de eventos y ausencia de
   duplicados. Rechazar datos inconsistentes, no corregirlos inventando historia.
2. Completar únicamente nulabilidad/default/unicidad del outbox preexistente.
   Validar las tablas de reservas, pagos y notificaciones adoptadas.
3. Ejecutar 0015–0020 en orden canónico; no volver a ejecutar 0012 o 0013.
   Activar RLS en tablas nuevas para mantener el perímetro privado en Supabase.
4. Validar el modelo completo y huellas de todas las columnas/filas originales;
   solo entonces registrar 0020. Cualquier fallo revierte DDL y marcador.

No borrar tablas, publicar eventos, sembrar usuarios, importar caja histórica ni
modificar comprobantes, presupuestos, reservas, cancelaciones o auditorías.
La reparación no es un `alembic stamp` genérico y se niega a adoptar otro head.

## Aceptación operativa

- Dado un respaldo del estado observado, restaurarlo sin red externa; reparar y
  ejecutar `alembic upgrade head` nuevamente no produce DDL ni pérdida de hechos.
- Dado marcador incorrecto, cobro/contexto/evento incompatible o fallo final,
  rechazar y conservar las huellas originales, sin adopción parcial.
- Dado un build Docker, PDF/DOCX deben importar sus renderizadores declarados.
- Después del ensayo y comparación del respaldo con la base activa: reparar,
  reconstruir backend/workers y verificar HTTP y procesos. No tocar otros proyectos.

## Respaldo

`data/backups/reconciliation-20261026T140537Z/`, privado (0700/0600), contiene
dump custom de `public` y `public_legacy_20261021`, vouchers locales, huellas y
manifiesto SHA-256. No es respaldo integral de Supabase ni de objetos S3 remotos.
El directorio local `uploads/vouchers` estaba vacío; se archivó ese estado, no
se descargaron vouchers remotos. Las referencias históricas en SQL se conservaron.
Conservarlo fuera del equipo antes de limpiar los entornos de recuperación.

## Resultado aplicado

- Dos restauraciones limpias en PostgreSQL 17 sin red externa; reparación y
  arranque HTTP reales correctos. `alembic upgrade head` posterior no reaplica DDL.
- **650 pruebas aprobadas**, incluidas compatibilidad del adaptador anterior,
  errores de revisión/respaldo/contexto/eventos, esquema incompleto y rollback
  después del DDL. Ruff de los archivos cambiados y `git diff --check` correctos.
- Aplicación autorizada en la base activa: comparación bajo locks con el respaldo,
  migraciones 0015–0020 y validación completa en una transacción; revisión final
  `20261025_0020`. Se preservaron 32 tablas públicas originales más la tabla
  archivada: todas sus columnas y filas originales coinciden con las huellas.
- Las once tablas nuevas tienen RLS. Fondos, aplicaciones y ledger diario siguen
  vacíos: no se reconoció caja ni se generaron obligaciones históricas.
- Backend y los tres workers reconstruidos y **healthy**; frontend/Redis siguen
  healthy. Health HTTP y lecturas autenticadas (sesión, unidades, comprobantes,
  catálogo, edificios y fondos) respondieron 200. PDF/DOCX generan bytes válidos
  dentro de la imagen. La tabla histórica sin detalle no se altera para probar exports.
- Antes de arrancar workers se verificaron cero eventos sin consumir, notificaciones
  pendientes y presupuestos actuales por emitir. Las huellas originales siguen
  iguales tras su arranque. No se publicaron hechos nuevos para ensayar el despliegue.
- Vouchers respaldados; los entornos temporales de ensayo/pruebas se detuvieron.
  No se detuvieron servicios de otros proyectos ni se hizo commit/push.

El adaptador exige `--aplicar --respaldo RUTA_PRIVADA`, valida SHA-256 y el contenido
de la base contra el respaldo antes de mutar. No ejecutarlo de nuevo sobre 0020:
rechaza otro marcador. Ante deriva futura se necesita otro respaldo y ensayo.
