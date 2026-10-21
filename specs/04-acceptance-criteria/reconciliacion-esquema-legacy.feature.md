# Reparación controlada del despliegue legacy 20261021_0012

No cambia reglas PROC-02/03/04, contratos API ni migraciones históricas. La reparación es explícita y nunca se ejecuta automáticamente al arrancar la API.

- Dado un respaldo privado del esquema público y sus datos, cuando se prepara la reparación, entonces se restaura en PostgreSQL aislado y se ensaya allí antes de aplicar al despliegue. Los vouchers locales se respaldan por separado; esto no sustituye un respaldo integral administrado de Supabase.
- Dado el marcador legacy exacto `20261021_0012`, cuando se reconcilia, entonces se bloquean escrituras durante la transacción y se agregan las estructuras faltantes; solo después de validar la compatibilidad se reemplaza el marcador por el head canónico. Otra revisión se rechaza sin cambios.
- Dadas reservas históricas, cuando se agregan contexto, moneda y nombre de área, entonces se obtienen de sus relaciones existentes; fechas, costos, UUID, zona horaria, estados y usuario originales se conservan. Las cancelaciones se recuperan de `cancelaciones_reserva`; si falta evidencia o cruza contexto, se revierte todo.
- Dada la tabla legacy de notificaciones sin identidad/evento/cuerpo, cuando está vacía, entonces se conserva en un esquema privado y se crea la cola canónica; si contiene registros, se rechaza la reparación para exigir una política explícita de adopción, sin inventar identidad ni entrega.
- Dados saldos, auditorías, pagos, imputaciones, revisiones y outboxes existentes, cuando termina la reparación, entonces sus columnas originales conservan exactamente sus valores. No se publican ni reescriben eventos y no se elimina ninguna tabla o registro legacy.
- Dado un fallo de validación o de DDL, cuando se aborta, entonces se revierten también el marcador, el esquema de archivo y todos los cambios. Se conservan las políticas RLS y restricciones adicionales compatibles; nunca se desactiva RLS para igualar el esquema vacío.
