# CON-72 — Convergencia de contratos e integración

Responsable de integración: Nicolás. Rama `feat/CORE-con73-con74-integracion`.
Implementación local; revisión de pares y verificación del esquema desplegado
pendientes. Se reutilizan la contabilidad de Anderson y la persistencia CON-73.

## Cambio coordinado

- `POST /pagos/reportar` multipart único con `archivo_voucher`; no acepta JSON
  ni claves privadas. Retira `POST /pagos/vouchers`. Reintentos equivalentes no
  guardan otro archivo, auditoría ni evento. Conserva el hash canónico existente.
- Respuestas con `codigo`, estado público APROBADO, dinero de dos decimales y
  `url_voucher` hacia la descarga autenticada con MIME real y `no-store`.
- `PUT /pagos/{id}/voucher` solo subsana OBSERVADO. Conserva UUID, hash y datos
  bancarios; agrega evidencia sin destruir la anterior y vuelve a EN_REVISION.
- Cada revisión nueva identifica el archivo revisado y conserva notas internas
  separadas del motivo público. No puede aprobarse directamente un OBSERVADO.
  Repetir la misma decisión, motivo y notas devuelve el resultado original sin
  otra imputación. Otra decisión sobre el estado final responde 409.
- `GET /pagos/{id}/resultado` no devuelve la revisión del archivo anterior tras
  subsanar. Las respuestas nunca incluyen notas internas.
- Nuevos eventos canónicos con schema_version/correlation_id/causation_id.
  Observación y rechazo usan PagoRevisadoEvent. El consumidor reconoce también
  los envelopes históricos version: 1, sin editar ni republicar esos hechos.
- Frontend actual actualizado conjuntamente: reporte único, subsanación desde
  historial, botones de revisión solo EN_REVISION y mensajes de error canónicos.
- Errores públicos raíz con detalles.errores sin valores sensibles. Reservas y
  comunicados tienen respuestas tipadas y verificadas contra los esquemas.

## Migración y despliegue

`20261021_0013` sucede a `20261020_0012`. Retira la unicidad por comprobante del
registro de archivos y añade archivo_nombre y notas_internas a revisiones_pago.
No cambia resultados JSON, hashes, saldos, auditorías ni eventos anteriores.
Asocia históricos con su archivo registrado; no inventa evidencia ausente.
Los motivos históricos ya persistidos se conservan: revisar los datos existentes
si anteriormente se usaron notas internas como motivo público.

1. Revisar una copia del esquema y un respaldo verificable; no ejecutar seeds demo
   en producción. Confirmar compatibilidad de consumidores externos.
2. Aplicar `python -m alembic upgrade head` con la conexión de despliegue.
3. Publicar juntos backend, workers y frontend actualizado. Clientes antiguos con
   reporte JSON deben actualizarse; no hay una API paralela de compatibilidad.
4. Compilar Next.js con NEXT_PUBLIC_API_URL del entorno y refrescar clientes.

El downgrade destructivo está deshabilitado para conservar las versiones.
No se ejecutó ninguna migración en Supabase ni en servicios del usuario.

## Verificación reproducible

Definir CON73_TEST_DATABASE_URL y CON13_TEST_DATABASE_URL sobre PostgreSQL
aislado; DATABASE_URL debe apuntar a ese entorno, con esquema público migrado.

```bash
pytest -q
pytest -q src/tests/integration/test_convergencia_con72.py src/tests/integration/test_migracion_con72.py
python -m pytest -q scripts/ci/verify_api_contract.py
```

La suite de contratos usa los YAML/JSON canónicos, no copias de DTOs. Incluye
reporte/subsanación concurrentes, rollback del archivo y SQL, aislamiento por
unidad, errores 413/415/422, precisión, notas privadas, conservación de versiones,
consumo histórico y recuperación de resultados. CI deja de exceptuar el reporte
de pagos y ejecuta explícitamente el chequeo de respuestas/eventos CON-72.

En `frontend/`: `node --test tests/*.test.mjs`, `npx tsc --noEmit`, `npm run lint`
y `npm run build`.

Con servicios y seeds de demostración explícitos en una base aislada:

```bash
python -m scripts.verificar_pagos_navegador --url http://localhost:3000 --confirmar-entorno-demo --evidencia-dir /tmp/opencode/con72-evidencia
```

Chromium verificó el comprobante `e364a783-3d5f-4a6f-ae22-e0ff35ac174e`, su
subsanación con el mismo UUID, aprobación, descarga y aviso desde evento canónico.
Las capturas temporales estaban en `/tmp/opencode/con72-evidencia/`; el reinicio
del entorno eliminó ese directorio y la base demo, no los cambios del repositorio.
El script permite reproducir el recorrido en otro entorno demo. El build Next.js y las
17 pruebas JavaScript pasaron; la tanda enfocada pasó 103 pruebas.

## Resultado final de verificación

| Verificación | Resultado |
|---|---|
| Suite completa final, PostgreSQL migrado | 466 aprobadas; cobertura 92,51 % (mínimo 80 %). |
| Contratos CON-72 y adopción histórica | 25 aprobadas; incluye commit confirmado con respuesta perdida y error 500 sanitizado. |
| Fuzzing ASGI de todas las operaciones | 54 aprobadas, sin exceptuar pagos. |
| Cliente JavaScript | 17 aprobadas. |
| TypeScript / ESLint / build Next.js | Correctos. |
| Chromium reporte → observación → subsanación → aprobación → descarga → aviso | Correcto antes del reinicio del entorno. |
| Spectral OpenAPI | 0 errores; 63 advertencias documentales. |
| Verificador SDD / git diff --check | Correctos. |
| Ruff | Sin diagnósticos nuevos frente a HEAD en archivos de esta entrega; no se limpió la deuda heredada. |

Después del reinicio se recreó únicamente PostgreSQL de pruebas para verificar
la suite final y el fuzzing. No se volvió a provisionar la demostración perdida.
Cambios sin commit/push; el despliegue y la revisión del equipo siguen pendientes.

Fuera de alcance: rediseño, proveedor externo, limpieza de lint preexistente y
aprobación final de las historias del equipo. SIMULADO no acredita entrega física.
