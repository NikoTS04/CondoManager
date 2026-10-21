# Merge de Anderson con develop (2026-10-20)

Se revisaron los siete archivos en conflicto contra HEAD y MERGE_HEAD.

- Alembic registra modelos financieros y el catalogo de areas.
- Pagos conserva persistencia, vouchers privados, idempotencia, conciliacion,
  auditoria y outbox. Su repositorio ya valida vinculos activos, condominio,
  unidad activa y permisos de escritura; no se reintroduce la simulacion de develop.
- Cuotas usa el catalogo comun del portal con edificio y vinculos vigentes.
  La deuda y el estado se calculan con las cuotas reales y dias de gracia.
- Reservas combina catalogo, horarios, zona horaria, restricciones de edificio
  y solvencia real. Catalogo y solvencia comparten sesion y transaccion para
  evitar bloquear el mismo condominio desde dos sesiones de la misma solicitud.
- Las pruebas conservan los catalogos aislados y el contrato financiero.

## Cadena Alembic

Ambas ramas definian 20261020_0009 para cambios diferentes. Se conserva ese
identificador para vinculos y se asigna 20261020_0009_pagos a pagos persistentes.
20261020_0010_catalogo_areas.py permanece presente y enlazada a vinculos.
La revision vacia 20261020_0011 une ambas ramas en una unica cabeza.

No se consulto ni modifico la base compartida. Si algun entorno ya registro
20261020_0009 como pagos, su version es ambigua respecto de develop: antes de
aplicar esta cadena debe inspeccionarse el historial y el esquema de ese entorno
para definir su reconciliacion. Este merge no ejecuta upgrade, stamp ni seeds.

## Verificacion

- Backend: 231 pruebas aprobadas y 181 omitidas; sin URLs de bases de pruebas,
  con DATABASE_URL local aislada y conexiones externas bloqueadas en el proceso.
- Frontend: 14 pruebas aprobadas (api.test.mjs y session.test.mjs).
- Ruff pasa en todos los archivos resueltos y adicionales de esta integracion.
  El analisis global reporta 50 hallazgos, todos presentes en alguno de los padres.
- Sintaxis Python valida en src, scripts y migrations.
- Alembic heads/history y prueba del grafo: una cabeza, sin ejecutar migraciones.
- Sin cambios a .env, sin push y sin operaciones sobre Supabase.
