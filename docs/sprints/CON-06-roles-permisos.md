# CON-06 — Entrega y guion de prueba de roles

Rama: `feat/proc-05-con-06-roles-permisos`, desde `develop` con CON-04 integrado.
Contrato: [roles y permisos](../../specs/02-domains/05-usuarios-rbac/roles-y-permisos.md).

## Arranque de la demostración

Desde la raíz del proyecto, con `.env` apuntando a la base de demostración:

```bash
docker compose up -d --build --wait --wait-timeout 180 backend frontend
docker compose exec backend python -m scripts.seed_usuarios_demo
```

El backend aplica la migración `20261020_0008`, que añade actividad a los roles.
El seed conserva cuentas, contraseñas, permisos y revocaciones existentes.

## Recorrido desde navegador

1. Abrir `http://localhost:3000/login` como SuperAdmin demo
   (`superadmin@condomanager.pe` / `SuperAdmin123!`). Seleccionar el condominio
   en Configuración y abrir Usuarios.
2. Crear una cuenta de prueba. En su fila, elegir Admin/Junta y Guardar rol.
   Su cuenta debe continuar inactiva. Activarla y abrir una sesión independiente:
   el login debe conducir al portal de Junta con el rol persistido.
3. Con la nueva Junta, comprobar que su propia asignación y las de otras Juntas
   están protegidas. Solo debe ofrecer Auditor y Residente para roles operativos.
4. Abrir una sesión de residente demo. Desde SuperAdmin, cambiar su rol a Auditor.
   La sesión anterior debe rechazarse en su siguiente solicitud o recarga. Tras
   un nuevo login debe entrar al portal de Auditor sin acciones de escritura.
5. Revocar ese rol. La fila debe seguir visible como Rol revocado y la cuenta
   conservar su estado global. El login sin otro contexto activo debe rechazarse.
6. Elegir Residente y Restaurar rol. Un login nuevo debe recuperar sus vínculos;
   los tokens anteriores continúan revocados.
7. Como SuperAdmin, seleccionar otro condominio y utilizar el UUID mostrado en
   la fila para asignar un rol a la misma identidad existente. Al iniciar sesión,
   el selector debe permitir elegir el contexto y resolver su rol correspondiente.
8. Comprobar Guardar/Revocar/Restaurar en móvil y recargar o reiniciar el backend:
   las asignaciones y revocaciones deben conservarse.

## Verificación automatizada

Configurar `CON06_TEST_DATABASE_URL` con una base PostgreSQL de pruebas que permita
crear esquemas. Las fixtures aplican las migraciones en esquemas independientes
y los eliminan al terminar. CI también admite su `CON13_TEST_DATABASE_URL`.

```bash
.venv/bin/python -m pytest -q src/tests/integration/test_roles_permisos_db.py src/tests/bdd/test_roles_permisos_bdd.py
```

Verificación de la entrega:

- Suite completa: **288 pruebas aprobadas**, cobertura **87,19 %** (mínimo 80 %).
- Contrato ASGI: **41 operaciones aprobadas**, manteniendo separado el caso
  histórico no bloqueante de límites decimales de pagos.
- Frontend: **11 pruebas Node aprobadas**, lint, tipos y build correctos.
- Chromium sobre build de producción y PostgreSQL aislado: **11 comprobaciones
  aprobadas**, incluidos móvil de 390 px y reinicio real de la API.
- Ciclo Alembic `upgrade head → downgrade base → upgrade head`: correcto.
  El downgrade con roles revocados se rechaza para evitar rehabilitarlos
  implícitamente en una revisión que no puede representar esa revocación.
- SDD correcto; Spectral sin errores, con los 66 avisos documentales existentes.
