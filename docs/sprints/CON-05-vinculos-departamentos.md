# CON-05 — Entrega y guion de vínculos con departamentos

Rama: `feat/proc-05-con-05-vinculos-departamentos`, desde `develop` con CON-06
integrado. Contrato: [vínculos persistentes](../../specs/02-domains/05-usuarios-rbac/vinculos-departamentos.md).

## Arranque de la demostración

Con `.env` apuntando a la base de demostración, desde la raíz:

```bash
docker compose up -d --build --wait --wait-timeout 180 backend frontend
```

El backend aplica la migración `20261020_0009`: índice de consulta de titulares
activos; conserva los vínculos existentes. Para preparar cuentas demo en una base
que aún no las tenga:

```bash
docker compose exec backend python -m scripts.seed_usuarios_demo
```

## Recorrido funcional

1. Entrar en `http://localhost:3000/login` como SuperAdmin demo
   (`superadmin@condomanager.pe` / `SuperAdmin123!`). Seleccionar condominio.
2. En **Estructura**, crear un edificio y un departamento de prueba. Utilizar
   una unidad nueva permite verificar que los datos proceden del padrón SQL.
3. En **Usuarios**, crear o escoger dos identidades con rol contextual vigente.
   Pueden estar inactivas durante su incorporación; vincular no activa la cuenta.
4. En la fila del primer usuario, pulsar **Gestionar vínculos**. El panel se abre
   debajo de la tabla. Elegir la unidad, relación **Propietario titular** y
   **Guardar vínculo**.
5. En el segundo usuario, abrir Gestionar vínculos y registrar **Inquilino** o
   **Copropietario** en esa unidad. Intentarlo antes del paso 4 debe devolver un
   error visible `TITULAR_REQUERIDO` sin crear relaciones.
6. Activar las cuentas desde SuperAdmin. Iniciar sesión en una ventana independiente
   como residente: debe ver las unidades vinculadas. Si hay varias, el selector
   usa UUID y distingue edificio, número y piso. Cambiar de unidad actualiza la
   etiqueta de Propietario/Copropietario/Inquilino según su relación.
7. Desactivar el vínculo del inquilino desde administración: su siguiente solicitud
   o recarga rechaza la sesión anterior. Un nuevo login excluye la unidad y las
   operaciones sobre ella reciben 403. La relación continúa visible como inactiva.
8. **Restaurar vínculo** recupera la misma fila. **Editar relación** permite
   seleccionar otra relación en el formulario. Todo cambio real exige nuevo login.
9. Intentar retirar o cambiar al último titular debe ser rechazado. Para traspasar
   la tenencia, registrar otro titular primero y después retirar/cambiar al anterior.
10. Repetir en móvil, recargar y reiniciar el backend: unidades, UUID de vínculos,
    relaciones y revocaciones deben conservarse. Los recursos de pago/reserva siguen
    el alcance de persistencia de sus propias historias del sprint.

Junta administra vínculos solo en su condominio. Auditor y Residente no acceden
al padrón administrativo. Un rol revocado no permite nuevas vinculaciones;
retirar un vínculo no titular existente sigue permitido para limpiar el padrón.

## Pruebas automatizadas y evidencia

Configurar `CON05_TEST_DATABASE_URL` con una base PostgreSQL de pruebas que permita
crear esquemas. Las fixtures migran esquemas independientes y los eliminan al
terminar; en CI se admite también `CON13_TEST_DATABASE_URL`.

```bash
.venv/bin/python -m pytest -q src/tests/integration/test_vinculos_db.py src/tests/bdd/test_vinculos_bdd.py
```

Resultados de esta entrega:

- Suite backend completa: **320 pruebas aprobadas**, cobertura **85,98 %**.
- Contrato ASGI: **44 operaciones aprobadas**; el caso histórico no bloqueante
  de límites decimales de pagos conserva su ejecución separada.
- Frontend: **13 pruebas Node aprobadas**, lint, tipos y build correctos.
- Chromium con build de producción y PostgreSQL aislado: **13 comprobaciones
  aprobadas**. Creación desde Estructura, errores de titular, relaciones mixtas,
  unidades de igual número en edificios distintos, reserva sobre unidad nueva,
  revocación, restauración/edición móvil, Junta/Auditor y reinicio real de API.
- PostgreSQL: unicidad/idempotencia concurrente, retirada simultánea de titulares,
  revalidación de actor revocado durante un bloqueo y rollback de vínculo/revisión/
  auditoría comprobados. La carga demo no restablece vínculos revocados.
- Ciclo Alembic `upgrade head → downgrade base → upgrade head`: correcto.
- SDD correcto; Spectral sin errores, con los 66 avisos documentales existentes.
