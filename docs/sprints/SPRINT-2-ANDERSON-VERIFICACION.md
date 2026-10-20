# Evidencia de verificación — Anderson, Sprint 2

Fecha: 2026-10-20. Alcance: CON-22, CON-70 y CON-42.
Entorno: Windows, Python 3.12.10, PostgreSQL 16 aislado, Redis 7 y Chromium.
No se migró ni modificó una base compartida del equipo.

## Resultados comprobados

| Verificación | Resultado |
|---|---|
| Suite completa con PostgreSQL (`pytest -q --cov`) | **321 pruebas aprobadas, 0 omitidas; cobertura 86,04 %**, mínimo 80 %. |
| Regresión adicional del worker como proceso independiente | Aprobada, junto con las 14 pruebas de almacenamiento/contabilidad. |
| Migración en base vacía: upgrade head → downgrade base → upgrade head | Aprobada en una base exclusivamente creada para esta verificación. |
| Adopción de tablas financieras preexistentes | Aprobada; el comprobante conserva su identificador y estado. |
| Concurrencia de reporte y aprobación | Un comprobante lógico y una aplicación de fondos. |
| Rollback de revisión | Conserva EN_REVISION, sin imputaciones/crédito/revisión/evento de aprobación parciales. |
| Validación PNG/JPEG/PDF, archivo corrupto, tamaño y rutas | Aprobada; nombre generado y rechazo controlado. |
| Permisos y vínculos persistidos | Aprobados; evidencia privada y rechazo de escritura de AUDITOR. |
| SDD | Aprobado. |
| OpenAPI / Spectral | **0 errores**; conserva 60 advertencias de documentación fuera de este alcance. |
| Ruff de archivos Python modificados | Lint y formato aprobados. |
| Ruff global | 54 avisos fuera de los archivos modificados; no se alteraron módulos ajenos para corregirlos. |
| Docker backend | Imagen construida correctamente con las nuevas dependencias. |
| Frontend final | Build de producción aprobado, incluido lint y comprobación de tipos. |

La suite completa precedió a la regresión adicional del import del relay. Este
documento distingue ambas ejecuciones; no presenta un agregado como si fuera una
única ejecución de pytest.

La medición de cobertura se configuró para `greenlet` y `thread`: SQLAlchemy async
transfiere ejecución a greenlets y el seguimiento anterior omitía líneas realmente
ejecutadas. No se reduce el mínimo del proyecto ni se excluyen archivos productivos.

## Recorrido real desde navegador

Comando: `python -m scripts.verificar_pagos_navegador --confirmar-entorno-demo`.
Frontend con `NEXT_PUBLIC_DEMO_MODE=false`, utilizando su configuración existente
para evitar el autologin demo durante el login manual. No se modificó AuthContext.

1. Residente 402 con cuota SQL de S/ 170.00: reserva bloqueada.
2. Subida real de PNG, nombre UUID persistido en `url_voucher` y recepción 202.
3. Descarga privada desde la interfaz; el reporte aún no elimina la deuda.
4. Junta aprueba desde la interfaz: imputación S/ 170.00, resultado persistido.
5. Actualizar solvencia habilita el intento y actualiza la información del portal.
6. Recarga conserva el comprobante aprobado.
7. Se detuvo y arrancó nuevamente el proceso API; el comando de solo lectura
   `--comprobante-reinicio` recuperó el mismo comprobante y descargó el PNG.

Las capturas se mantuvieron fuera de Git, en una carpeta temporal de evidencia;
no se versionan archivos de pago ni credenciales. El guion es reproducible siguiendo
[`SPRINT-2-ANDERSON-USO.md`](SPRINT-2-ANDERSON-USO.md).

## Relay real y recuperación

Se publicó el outbox de la demostración a Redis real. La comprobación independiente
detectó un import ORM faltante que las pruebas dentro de la aplicación ocultaban;
se corrigió y se añadió una regresión en un intérprete separado.

El primer XADD había sido aceptado antes del fallo del commit. Al recuperar se
observaron **3 entregas, 2 event_id lógicos estables** (recepción y aprobación),
que es la semántica al menos una vez documentada. Otra pasada no produjo más
entregas. El consumidor debe deduplicar por event_id; esta entrega no afirma que
Alejandro haya implementado o entregado una notificación.

## Límites y revisión pendiente

- El calendario de reservas conserva su implementación anterior en memoria; su
  persistencia y exclusión entre procesos pertenecen a CON-41/43/73.
- Anderson aporta el guard SQL y su sesión transaccional para esa integración.
- No se implementaron historias de otros integrantes ni el motor de nuevos recargos.
- La aprobación del PR, el cierre de Jira y la validación funcional del equipo
  continúan siendo necesarios. Este registro no sustituye la revisión de un par.
