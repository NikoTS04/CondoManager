# CON-25–28 — Recuperación y validación puntual, Fase B

Fecha: 08/11/2026. Rama: `feat/CON-25-conciliacion-pagos`.
Respaldo conservado: `28fe57e21c7347dcb755d33b1212d26eb12dab68`.
Alcance autorizado: cuatro variantes inicialmente pendientes y pruebas puntuales
de brechas. **No se ejecutó la suite completa ni se hicieron commits o pushes.**

## Entorno nuevo y evidencia preservada

- PostgreSQL **16.15**, en el contenedor exclusivo
  `condomanager-anderson-s3-phaseb-20261108-pg`.
- Datos efímeros mediante tmpfs; red Docker interna exclusiva
  `condomanager-anderson-s3-phaseb-20261108-net`, sin puertos publicados.
- Cuatro contenedores pytest independientes, con healthcheck HTTP heredado
  desactivado por `--no-healthcheck` (`Test: ["NONE"]`). No cambia la configuración
  productiva ni el Dockerfile del proyecto.
- Imagen pytest fijada por ID:
  `sha256:009038208cf298023f6b80f8795f5de8a173e44c9fda1505d4194d087bf44b66`.
- Python 3.12.15, pytest 9.0.3, pytest-bdd 9.0.0, SQLAlchemy 2.1.5,
  asyncpg 0.32.0. Resto de versiones en `versiones.json`.
- El código base se copia desde `git archive HEAD`; para las pruebas nuevas solo
  se añade `src/tests/integration/test_pagos_fase_b_db.py`. No se copia `.env` ni
  se usa un directorio de trabajo modificable durante las pruebas.
- Todas las URLs SQL apuntan al PostgreSQL nuevo por su alias interno. Las
  fixtures aplican upgrades sobre esquemas vacíos propios y limpian únicamente
  esos esquemas; no se ejecutan downgrades ni migraciones sobre una base compartida.
- PostgreSQL estuvo running/healthy en las **62 muestras** registradas durante
  las cuatro ejecuciones, y saludable al terminar cada una. La comprobación final
  encontró cero esquemas residuales `con04_%` de las fixtures.

Los contenedores de la interrupción (`condomanager-anderson-s3-suite` y
`condomanager-anderson-s3-tests`) no se arrancaron, modificaron ni eliminaron.
Se compararon sus IDs y estados completos antes/después: permanecen idénticos,
con sus códigos anteriores 137 y 0, respectivamente.

## Resultados comprobados

| Etapa | Selección | Resultado | Tiempo pytest |
|---|---|---|---:|
| 01-revision | `test_revision_sin_aplicar_y_motivo_obligatorio`, OBSERVADO y RECHAZADO | 2 aprobadas, 0 fallos/errores/omisiones | 7,89 s |
| 02-vary | `test_aprobacion_exacta_recibo_inmutable_y_reintento_sin_efectos`, legacy y diaria | 2 aprobadas, 0 fallos/errores/omisiones | 9,39 s |
| 03-brechas | 8 casos nuevos y 7 casos existentes reutilizados | 15 aprobadas, 0 fallos/errores/omisiones | 69,80 s |
| 04-transporte | Repetición de los 2 casos de transporte tras retirar una deprecación del helper nuevo | 2 aprobadas, 0 fallos/errores/omisiones | 10,13 s |

Son **19 casos distintos**, no 21: la última etapa repite dos casos ya contados.
Todos los contenedores pytest terminaron normalmente con código 0. No se
reclasifica como aprobada la ejecución Docker interrumpida de la sesión anterior.

Los errores originales no se reprodujeron con PostgreSQL estable. La aserción de
Vary ya corregida en el respaldo acepta Authorization junto con Origin. No fue
necesario cambiar producción, autorización, cuotas, reservas o notificaciones.

## Brechas cubiertas, sin duplicar funcionalidades

Archivo nuevo: `src/tests/integration/test_pagos_fase_b_db.py` (8 casos):

- **CON-27, 2 variantes:** POST real de reserva devuelve 403 tras el parcial, sin
  reserva/evento propio; después de pagar el pendiente devuelve 201 y persiste una
  reserva CONFIRMADA con un evento. Legacy deja 60.00; diaria deja 70.00 por los
  diez devengos posteriores al abono oportuno de 40.00. No se condona mora.
- **CON-27, otra deuda:** liquidar una cuota no habilita reservar si otra cuota
  permanece vencida. Se verifica 403 y ausencia de reserva/evento de confirmación.
- **CON-25/26, 3 estados:** una referencia de evidencia nullable de revisión legacy
  permite recuperar y repetir APROBADO/OBSERVADO/RECHAZADO sin modificar la huella
  SQL o los archivos. La nulificación de referencia es solo una fixture sintética;
  no se elimina evidencia ni se cambia una migración.
- **CON-26, 2 decisiones:** el transporte inyectado falla, el aviso se programa
  para reintento y conserva el recibo, pagos, cuotas, crédito, auditoría y outbox.
  El worker no reenvía antes de tiempo; al reintentar conserva un aviso y dos
  intentos. La aceptación posterior es **SIMULADA**, no un correo real.

Se reutilizaron, sin modificar, siete casos de `test_pagos_sprint3_db.py`:
revisión/evidencia vigente con timestamps iguales; rollback tardío por outbox en
legacy/diario; origen y consumo único CON-13 en legacy/diario; aprobación y emisión
CON-13 concurrentes en legacy/diario. Esto cubre CON-25/26 y CON-28 sin otro motor.

## Advertencias y cambios

- La nueva fotografía financiera usaba inicialmente `Result.tuples()`, deprecado
  por SQLAlchemy 2.1. Se cambió exclusivamente ese helper a `Result.all()` y se
  repitieron los dos casos que lo utilizan: aprobados y sin esa advertencia.
- Persiste una advertencia previa Starlette/TestClient sobre httpx. No impide
  estos resultados y no se mezcló una actualización de dependencias con Fase B.
- Ruff check y format --check del archivo nuevo: aprobados.
- No se modificó ningún archivo productivo ni ninguna prueba ya respaldada.

## Artefactos y continuación

En `tmp/sprint3/phase-b/` (ignorado por Git):

- `01-revision`, `02-vary`, `03-brechas` y `04-transporte`: XML, log UTF-8,
  JSON de entorno/salud y TAR de las fuentes usadas, con SHA-256.
- `entorno.json`, `versiones.json` y `resumen.json`.
- `ejecutar.py`: orquestador temporal con selecciones explícitas; no tiene opción
  de suite completa y no reutiliza o elimina los contenedores antiguos.

**Listo técnicamente para solicitar Fase C**, no para declarar terminadas las
historias o preparar un PR definitivo. Sigue pendiente la regresión completa,
renovación final de evidencia de navegador y revisión del equipo. CON-26 conserva
su dependencia externa de correo real CON-78; no se implementó su proveedor.
La precisión de fecha bancaria/emisión requiere la revisión funcional acordada.

Los recursos nuevos quedan conservados para inspección: PostgreSQL saludable y
contenedores de pruebas detenidos con código 0. No se ejecutó limpieza automática.
