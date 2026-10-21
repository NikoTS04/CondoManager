# CON-39 — Entrega y guion del catálogo de áreas comunes

Rama: `feat/proc-04-con-39-catalogo-areas`, desde `develop` con CON-05 integrado.
Contrato: [catálogo persistente](../../specs/02-domains/04-reservas/catalogo-areas.md).

## Preparación

Desde la raíz, con `.env` apuntando a la base de demostración:

```bash
docker compose up -d --build --wait --wait-timeout 180 backend frontend
```

El backend aplica `20261020_0010`: crea/adopta el catálogo, conserva los campos
históricos de edificio/duración y añade apertura/cierre. Las áreas existentes
reciben `00:00`–`23:59` sin cambiar sus costos o estados. El script siguiente carga
las cuatro áreas de demostración de forma explícita y conserva las ya existentes:

```bash
docker compose exec backend python -m scripts.seed_areas_demo
```

Requiere tener preparado el condominio demo de CON-04 (`scripts.seed_usuarios_demo`).
La pantalla permite registrar áreas reales directamente, asociadas al contexto
seleccionado. El catálogo no utiliza un fallback en memoria.

## Recorrido desde navegador

1. Entrar en `http://localhost:3000/login` como SuperAdmin demo
   (`superadmin@condomanager.pe` / `SuperAdmin123!`) y seleccionar el condominio.
2. Abrir **Áreas comunes**. Registrar nombre, descripción, aforo, costo por turno,
   apertura, cierre y duración máxima. Edificio vacío significa uso compartido.
   El costo se envía como cadena decimal y utiliza la moneda del condominio.
3. Verificar el área en el catálogo administrativo, editar sus condiciones y
   guardar. El mismo UUID debe conservarse. Repetir valores idénticos no agrega
   una nueva auditoría.
4. En una ventana independiente, entrar como residente con vínculo activo. El área
   debe aparecer con horario, aforo, duración y tarifa. Elegirla y reservar un turno
   dentro de sus condiciones; la respuesta y Mis reservas muestran la tarifa real.
5. Intentar un turno fuera del horario o mayor que la duración máxima: debe
   rechazarse sin ocupar el calendario. Los límites exactos están permitidos.
6. Desactivar el área desde administración y actualizar/recargar el catálogo del
   residente. Debe desaparecer de las opciones y nuevas solicitudes a ese UUID
   reciben `409 AREA_INACTIVA`. La reserva anterior se conserva y puede consultarse.
7. Reactivar y cambiar la tarifa: las nuevas reservas usan el costo actual; la
   instantánea de precio/nombre/moneda de la reserva previa se conserva.
8. Registrar un área exclusiva de un edificio. Solo residentes con unidades activas
   vinculadas en ese edificio la consultan; la unidad utilizada al reservar debe
   corresponder al edificio del área.
9. Como Junta, administrar únicamente el propio condominio. Como Auditor, consultar
   Áreas comunes sin formularios ni botones de escritura; la API rechaza mutaciones.
10. Probar en móvil y reiniciar el backend. El catálogo, sus condiciones y los estados
    deben conservarse. La persistencia completa de reservas/notificaciones se integra
    en CON-73; esta entrega proporciona su catálogo SQL y sus condiciones.

Los horarios son diarios, `HH:MM`, en America/Lima, sin cruce de medianoche.
Las reservas nuevas conservan esa interpretación para aplicar la frontera de 24
horas de cancelación. La moneda del condominio puede ser PEN o USD; no se convierte
el importe ni se multiplica la tarifa por horas de uso.

## Verificación automatizada

Configurar `CON39_TEST_DATABASE_URL` con PostgreSQL de pruebas y permiso para crear
esquemas. Las fixtures migran esquemas independientes y los eliminan al terminar;
CI también admite `CON13_TEST_DATABASE_URL`.

```bash
.venv/bin/python -m pytest -q src/tests/integration/test_catalogo_areas_db.py src/tests/bdd/test_catalogo_areas_bdd.py
```

Resultados de la entrega:

- **374 pruebas backend aprobadas**, cobertura **86,14 %** (mínimo 80 %).
- **49 operaciones del contrato ASGI aprobadas**, con el caso histórico no bloqueante
  de precisión extrema en pagos ejecutado por separado en CI.
- **14 pruebas Node aprobadas**; frontend lint, tipos y build correctos.
- **14 comprobaciones Chromium aprobadas** sobre build de producción y PostgreSQL
  aislado: CRUD real, condiciones del residente, reserva válida, desactivación e
  historial, Auditor/Junta, edificio exclusivo, aislamiento, PEN/USD, móvil de 390 px
  y conservación tras reinicio real de la API.
- Transacciones y rollback de auditoría, no-op, serialización de reserva/desactivación,
  revalidación del actor y frontera de cancelación Lima/UTC comprobados.
- Adopción de esquemas históricos con y sin edificio/duración, FK de reservas
  históricas y downgrade conservador comprobados. Ciclo Alembic completo correcto.
- SDD correcto; Spectral sin errores y con los 66 avisos documentales existentes.
