# CON-3 / USR-02 — Edificios, departamentos e importación CSV

## Persistencia y contexto

La estructura canónica es `condominios → edificios → departamentos`, compatible
con el backup de Supabase del 18/10/2026. Un departamento se identifica por UUID,
no por su número. `edificios.condominio_id` determina el contexto de sus unidades.
Los modelos se mantienen en `src/modules/condominios/models.py`; los casos de uso
se implementan en `src/modules/condominios/estructura/`.

- Escritura: `SUPERADMIN` y `ADMIN_JUNTA` del condominio.
- Consulta: esos roles y `AUDITOR` del condominio.
- Toda solicitud requiere JWT con identidad y rol. Salvo SUPERADMIN, el claim
  `condominio_id` debe coincidir con la ruta. Se exige condominio activo existente.
- Se devuelve 401 sin identidad, 403 sin permiso/contexto, 404 para recursos
  inexistentes en el contexto autorizado, 409 para duplicados y 422 para datos inválidos.

## Datos y reglas

- Edificio: UUID del servidor, condominio, `nombre_bloque` (1–100 caracteres tras
  trim), `total_pisos` entero 1–32767. Nombre único por condominio sin distinguir
  mayúsculas ni espacios exteriores.
- Departamento: UUID del servidor, edificio, `numero` (1–20 caracteres, trim y
  mayúsculas, conservando ceros iniciales), `piso` entero 1–total_pisos,
  `coeficiente_participacion` como cadena decimal finita, >0 y <=100, máximo cuatro
  decimales. Se normaliza a cuatro decimales con Decimal; nunca float.
- Saldo inicial `0.00`, estado financiero `AL_DIA` y `activo=true` los establece
  el servidor. Activar/desactivar solo cambia `activo` y conserva el historial.
- Identidad natural: edificio + número normalizado. Puede repetirse el número en
  otro edificio. PostgreSQL protege también las claves normalizadas.
- Es posible registrar parcialmente el padrón. La suma 100.0000% se exige en
  CON-10 al utilizar POR_ALICUOTA, sobre todos los departamentos activos del condominio.
- El alta y cada cambio de estado generan auditoría en la misma transacción,
  encadenada bajo bloqueo del condominio. Repetir el mismo estado es un no-op.
- Desactivar excluye futuras distribuciones/emisiones; no impide pagar cuotas
  históricas ni aplicar crédito a obligaciones existentes.

## API (prefijo `/api/v1/condominios/{condominio_id}`)

| Método | Ruta | Resultado |
|---|---|---|
| GET / POST | `/edificios` | Lista / alta 201 |
| GET | `/departamentos?edificio_id=UUID&activo=true` | Lista contextual; filtros opcionales |
| POST | `/edificios/{edificio_id}/departamentos` | Alta 201 |
| PATCH | `/departamentos/{departamento_id}/estado` | `{ "activo": false }`; recurso actualizado |
| POST | `/importaciones/previsualizar` | multipart `archivo`; validación sin escrituras |
| POST | `/importaciones/confirmar` | mismo archivo multipart; revalidación y alta de filas válidas |

## CSV

UTF-8 con BOM opcional, separador coma o punto y coma, lector CSV con comillas.
Cabecera obligatoria: `numero,piso,edificio,coeficiente,total_pisos`. Se admite
`coeficiente_participacion` como alias de `coeficiente`; `total_pisos` es opcional
para edificios existentes y obligatorio para nuevos. Máximo 2 MiB y 5000 filas.

Los pisos declarados para un mismo edificio deben ser consistentes. Se informa
número de fila original, errores y estado `NUEVA`, `YA_EXISTENTE`, `ERROR` o
`CREADA`. Reintentar una unidad idéntica no modifica su saldo, estado financiero ni
actividad; datos diferentes constituyen conflicto. Duplicados idénticos del archivo
se omiten tras la primera fila; duplicados con datos diferentes se rechazan.

La confirmación vuelve a consultar la base y serializa escrituras por condominio.
Errores de datos no invalidan otras filas. Un fallo inesperado de persistencia o
auditoría revierte la solicitud completa; nunca se devuelve éxito sin commit.

## Migración y verificación

`20261018_0005` crea edificios/departamentos en bases nuevas y adopta las tablas
existentes solo tras verificar columnas, tipos, nulabilidad, unicidad, checks y FK.
Añade `activo BOOLEAN NOT NULL DEFAULT TRUE`, límites de coeficiente e índices
normalizados. Rechaza un esquema incompatible sin transformarlo silenciosamente.
Las tablas creadas por esta revisión llevan una marca de procedencia en su comentario;
el downgrade conserva tablas preexistentes y elimina solo las creadas por la revisión.

La prueba de BD usa migraciones reales y un PostgreSQL aislado. Se cubren adopción
del esquema del backup, persistencia, precisión, duplicados, aislamiento, auditoría,
activación, CSV parcial/reintentos y lectura de activos por CON-10.
