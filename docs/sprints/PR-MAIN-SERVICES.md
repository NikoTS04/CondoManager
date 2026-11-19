# PR a main: consolidación funcional y Vercel Services Hobby

Rama: `feat/PROC-02-conciliacion-operacion`. Destino: `main`.
Base reconciliada: referencia local `origin/main`, `13c0d16`.
No fue posible actualizarla desde GitHub: autenticación SSH rechazada.

## Cambios

- Conserva CON-24/79 de main: contratos, interfaz, documentos PDF/DOCX,
  validación binaria, protección de archivos y sanitización de login.
- Reservas solo SQL y bloqueos preventivos auditados, con interfaz y conflictos
  explícitos ante reservas afectadas. Retira simulador manual de mora con 410.
- Supabase Storage privado opcional, límite Hobby 3 MiB, configuración segura,
  readiness y ejecución diaria SQL sin Redis obligatorio.
- Un proyecto Vercel Services confirmado por el usuario: frontend público,
  API interna mediante binding APP_URL; excepción pública protegida del cron.
- Proxy runtime conserva auth, multipart, query e idempotencia, limita tamaño,
  no sigue redirects ni divulga direcciones internas.
- Adapter Mailjet preparado con aceptación incierta explícita y pruebas sin red.
  Desactivado por defecto, sin despacho automático ni envíos reales.
- Documentación, contratos y pruebas de los incrementos anteriores consolidados.

## Verificación

- Backend completo con PostgreSQL efímero: **832 aprobadas**, sin fallos ni omisiones,
  557,45 s. Python 3.14/PostgreSQL 18.7; no sustituye CI 3.12/16.
- Frontend: **39 aprobadas**, TypeScript y build Next.js correctos.
- Schema oficial Vercel, Ruff de archivos cambiados, verificador SDD y diff-check.
- JUnit/log local: `/tmp/opencode/condo-services-pr-final.xml` y `.log`.
- Sin llamadas reales a Mailjet, Supabase o Vercel; sin despliegue ni Chromium.

## Antes del merge y deploy

- Resolver SSH, actualizar referencias y verificar que main no haya avanzado.
- Corregir variables Production según `docs/procesos/VERCEL-HOBBY.md`.
  El .env local conserva DEBUG true y JWT predeterminado: no sirve tal cual.
- Confirmar dominio definitivo y remitente Mailjet verificado; mantener
  `MAILJET_ENABLED=false` hasta la integración y autorización de prueba real.
- Mantener base y bucket de Preview separados de Production.
- Respaldo, migraciones controladas, migración de evidencia local y prueba de humo.
- Reconciliar reservas que solo existan en procesos antiguos antes de apagarlos.
- Aceptar limitación Hobby diaria: no acredita reintentos de correo 2/10/30 min.

El commit excluye .env y credenciales reales. No cambia Jira ni acredita aprobación.
