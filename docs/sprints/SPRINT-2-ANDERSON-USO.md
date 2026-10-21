# Sprint 2 — Uso y verificación de las entregas de Anderson

Alcance: **CON-22, CON-70 y CON-42**. Contrato:
[`sprint-2-anderson.md`](../../specs/02-domains/02-pagos-y-moras/sprint-2-anderson.md).
Resultados: [registro de verificación](SPRINT-2-ANDERSON-VERIFICACION.md).
No sustituye las entregas de catálogo, calendario persistente, exclusión de horarios
ni notificaciones de otros integrantes.

## Preparación

1. Usar Python 3.11+ (verificado con 3.12), Node.js y PostgreSQL 16.
2. Copiar `.env.example` a `.env` y configurar una **base de desarrollo**. No subir
   `.env`, contraseñas, tokens o vouchers. Antes de migrar una base con datos,
   respaldarla y comprobar primero la adopción en una copia.
3. Instalar dependencias y aplicar las migraciones desde la raíz:

```bash
python -m pip install -r requirements.txt
python -m pip install "pytest-cov>=6.0.0" "jsonschema>=4.0.0"
python -m alembic upgrade head
```

La revisión `20261020_0009` crea/adopta `comprobantes_pago` e
`imputaciones_pago`, conserva sus filas y añade subidas, revisiones y outbox.
Un esquema preexistente incompatible detiene la migración: no borrar tablas,
reescribir revisiones anteriores ni ejecutar un downgrade para "resolverlo".
No ejecutar pruebas ni ciclos downgrade/upgrade en la base del equipo.

## Arranque local

En terminales separadas, desde la raíz:

```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
python -m src.modules.pagos.worker
```

En `frontend/`:

Para usar login manual y para el recorrido de navegador, configurar
`NEXT_PUBLIC_DEMO_MODE=false` en `frontend/.env.local` (archivo no versionado) antes
de arrancar o compilar. Se utiliza la configuración existente, sin modificar el
módulo de identidad. Así se evita que el autologin demo de Junta compita con un
login manual al abrir una sesión vacía.

```bash
npm ci
npm run dev
```

Frontend: `http://localhost:3000`. API/documentación: `http://localhost:8000/docs`.
Redis debe estar disponible en `REDIS_URL` para publicar eventos. Si Redis falla,
el reporte/revisión confirmado sigue persistido y el worker reintenta el outbox.
Una publicación pendiente no equivale a notificación entregada.

### Alternativa Docker

Con `.env` configurado y una base de desarrollo accesible desde Docker:

```bash
docker compose up --build -d backend redis pagos-worker frontend
```

El backend aplica las migraciones al arrancar, como ya hacía el proyecto.
Backend y `pagos-worker` montan `./uploads/vouchers:/app/uploads/vouchers`.
En Linux la carpeta del host debe permitir lectura/escritura al usuario UID 1000
del contenedor. No cambiar permisos de otras carpetas. El worker de cuotas y las
configuraciones MinIO existentes no se eliminan ni se reemplazan.

## Almacenamiento temporal de evidencia

- Carpeta por defecto: **`uploads/vouchers/`**, relativa a la raíz del repositorio,
  no al directorio desde el que se ejecuta Python. Se crea automáticamente al subir.
- Configurable con `VOUCHERS_DIR`; en Docker debe corresponder al volumen montado.
- Solo contiene evidencia: UUID generado y extensión `.png`, `.jpg` o `.pdf`.
- `comprobantes_pago.url_voucher` contiene **ese nombre**, no URL/ruta/`blob:`.
- PNG y JPEG se verifican y decodifican; PDF se parsea, no admite cifrado y se limita
  a 100 páginas; máximo común de 5 MiB e imágenes de hasta 20 millones de píxeles.
- La descarga se hace autenticada por comprobante, como adjunto y sin caché
  compartida. No abrir la carpeta como directorio público ni usar `public/` de Next.
- `uploads/` queda fuera de Git y del contexto Docker. Respaldar **base y carpeta**
  conjuntamente. Recrear un contenedor no debe borrar el volumen del host.
- Un nombre histórico que contenía una URL se conserva; la descarga local devuelve
  404 controlado si no existe evidencia local. No se siguen enlaces externos.
- Las subidas abandonadas de más de 24 horas se limpian por el worker; una evidencia
  adjuntada no se elimina. Si la BD no está disponible, no se borra por conjetura.

**Hacer push no comparte archivos ni la BD.** Para que todo el equipo consulte los
mismos comprobantes debe usar el mismo backend, PostgreSQL y carpeta persistente.
En un despliegue frontend, configurar `NEXT_PUBLIC_API_URL` **antes del build**.
No usar `localhost` como URL para usuarios que acceden desde otras máquinas.

## Datos y recorrido de demostración (solo entorno aislado)

Activar `DEMO_MODE=true` exclusivamente en una base de demostración y ejecutar:

```bash
python -m scripts.seed_usuarios_demo
python -m scripts.seed_pagos_sprint2_demo --confirmar-datos-demo
```

La segunda orden añade una cuota demo de S/ 170.00 a la unidad 402 en el periodo
anterior; no sobrescribe cuotas existentes. No se ejecuta durante el arranque.
Las credenciales demo ya documentadas en `src/modules/usuarios/demo.py` son públicas
y **no se deben utilizar en producción**.

1. Entrar como `moroso402@villabonita3.pe`: verificar bloqueo y deuda S/ 170.00.
2. Reportar PNG/JPG/PDF real por ese importe. Obtener recepción `EN_REVISION`.
3. Descargar el voucher y verificar su contenido. La deuda sigue en mora.
4. Desde Junta, observar con motivo: no debe aplicar fondos; después aprobar.
5. La aprobación aplica S/ 170.00 una sola vez, persiste el resultado y genera evento.
6. En el residente, usar **Actualizar solvencia**: se habilita un nuevo intento.
7. Recargar y reiniciar API/worker, sin eliminar la carpeta: verificar comprobante,
   resultado y descarga. Otro residente no puede consultar esa evidencia.
8. Reintentar un reporte equivalente: 200 con el identificador existente si sigue
   EN_REVISION; 409 si ya se concilió. El nuevo reporte original recibe 202.

El motor de nuevos recargos no forma parte de estos tres tickets. Reportar no
regulariza una deuda existente. La consulta distingue obligaciones futuras/gracia
de deuda exigible en mora, independientemente por departamento.

## Verificación automatizada

Configurar `CON13_TEST_DATABASE_URL` con una **base PostgreSQL de pruebas**, nunca
con la base compartida. Las fixtures crean esquemas aislados y nuevas sesiones.
La prueba histórica de API de condominios también necesita el esquema base migrado.
Para los casos CON-3 puede utilizarse esa misma URL como `CON3_TEST_DATABASE_URL`.

```bash
python -m pytest -q --cov
python scripts/verify_sdd_compliance.py
ruff check .
ruff format --check .
```

El repositorio conserva deuda histórica de lint/formato; CI compara los archivos
modificados contra la base y rechaza deuda nueva. No reformatear módulos ajenos
para ocultarla. Deben pasar lint/formato de los archivos de esta entrega.

```bash
npx --yes @stoplight/spectral-cli lint specs/03-contracts/openapi/condomanager.openapi.yaml
```

Desde `frontend/`: `npm run lint`, `npx tsc --noEmit`, `npm run build`.
Para Chromium, instalar el complemento de prueba (no es dependencia productiva):

```bash
python -m pip install playwright
python -m playwright install chromium
python -m scripts.verificar_pagos_navegador --confirmar-entorno-demo
```

La instancia debe estar arrancada, con cuota demo aún impaga. Este recorrido genera
y aprueba un comprobante real; repetirlo requiere otra base demo limpia.
`--evidencia-dir <carpeta-local>` guarda capturas de apoyo fuera de Git.
Después de reiniciar la API, comprobar el mismo identificador sin crear otro pago:

```bash
python -m scripts.verificar_pagos_navegador --confirmar-entorno-demo --comprobante-reinicio <uuid-del-comprobante>
```

## Integración con el equipo

- **Brandon:** se conserva el hash público y la unicidad SQL. El guard
  `SolvenciaService.para_reserva(solicitud, usuario)` mantiene locks financieros y
  expone `service.session`; CON-41 puede persistir la reserva con esa misma sesión.
  El adaptador actual conserva el calendario existente, que aún es de memoria.
- **Alejandro:** resultados en `revisiones_pago`, consulta
  `/pagos/{id}/resultado` y eventos recuperables en `eventos_pago_outbox`. Usar
  `pago-sprint-2.schema.json` y deduplicar por event_id. PagoConciliadoEvent conserva
  también los campos planos históricos para facilitar una integración compatible.
- **Nicolás:** el relay propio publica en `condomanager:domain-events`, con el
  envelope de CON-11, sin cambiar su worker ni la persistencia de notificaciones.
- **Jerson:** se utilizan sesión y vínculos persistidos vigentes; no se modifica
  la gestión de usuarios o roles.
- **Gerardo:** BDD y pruebas SQL están en `src/tests/bdd/test_pagos_sprint2_bdd.py`
  y `src/tests/integration/test_pagos_db.py`; este documento proporciona el guion.

## Publicación

Rama `feat/CORE-sprint-2-anderson`, commits convencionales y PR hacia `develop`.
No hacer push directo a `develop`/`main`. Se requiere revisión de otro integrante
y Squash and Merge. La aprobación y el cierre funcional corresponden al equipo;
no se declaran completadas las dependencias ajenas al alcance de Anderson.
