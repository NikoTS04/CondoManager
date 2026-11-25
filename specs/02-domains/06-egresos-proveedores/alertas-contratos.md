# Alertas contractuales de 60 y 30 días (CON-50)

- **Estado:** Implementado el motor de evaluación y la persistencia propia. La fuente de contratos
  (CON-48/CON-49) y la orquestación del job (CON-85) quedan por conectar.
- **Proceso:** [PROC-06 §4.2.1](../../02-processes-and-automations/proc-06-egresos-y-proveedores.md)
- **Escenarios:** [alertas-contratos.feature.md](../../04-acceptance-criteria/alertas-contratos.feature.md)

## 1. Reglas

| Umbral | Prioridad | Destinatario | Propósito |
|---|---|---|---|
| 60 días | `INFORMATIVA` | Junta (`ADMIN_JUNTA`) del condominio | Evaluar renovación o cotizar con otros postores |
| 30 días | `PRIORITARIA` | Junta (`ADMIN_JUNTA`) del condominio | Gestionar addenda o nuevo acuerdo |

- Revisión diaria a las 01:00 UTC mediante el job diario existente. La evaluación es idempotente,
  de modo que una ejecución tardía o repetida no duplica avisos.
- `dias_restantes = fecha_fin - hoy` (fechas de calendario, UTC).
- Un umbral `U` está **vencido** cuando `0 <= dias_restantes <= U`. Un umbral vencido sin registro
  para su (contrato, vigencia) está **pendiente**.
- Entre los pendientes, el de menor umbral es el prioritario y se `GENERA`. Los demás
  pendientes de umbral mayor se registran `OMITIDO` con motivo `OMITIDO_POR_PRIORIDAD`.
- Con `dias_restantes < 0` (vigencia terminada) no se generan avisos nuevos.
- **Renovación:** abre una vigencia con otro identificador. Su calendario se calcula desde su
  propia `fecha_fin`; los avisos de la vigencia anterior permanecen sin cambios.
- **Aislamiento:** la evaluación y los destinatarios se resuelven por `condominio_id` del contrato.

## 2. Casos de recuperación

| Situación | Resultado |
|---|---|
| Faltan 60 días, sin registros | `GENERADO` 60 |
| Faltan 59 (se perdió la ejecución de 60) | `GENERADO` 60, una sola vez |
| Faltan 30, 60 ya generado | `GENERADO` 30 |
| Faltan 29 con ambos pendientes | `GENERADO` 30 y `OMITIDO` 60 por prioridad |
| Faltan 29 con 60 ya generado | `GENERADO` 30 |
| Segunda ejecución el mismo día | Sin cambios |
| Faltan 20 días, ya existen 60 y 30 | Sin cambios |
| Renovación con nueva `fecha_fin` | Calendario nuevo; historial anterior intacto |

## 3. Interfaz mínima con contratos

CON-49 debe exponer, por cada contrato con vigencia activa, un objeto con:

| Campo | Tipo | Uso |
|---|---|---|
| `id` | UUID | Contrato (sin llave foránea dura en CON-50) |
| `condominio_id` | UUID | Aislamiento y destinatarios |
| `fecha_fin` | date | Fin de la vigencia en curso |
| `vigencia` | str | Identificador opaco de la vigencia; cambia en cada renovación |

Se declara como `Protocol` en `src/modules/alertas_contratos/contratos.py`.

## 4. Persistencia: `avisos_contrato`

PK `id`; `condominio_id` FK RESTRICT a `condominios`; `contrato_id` UUID **sin llave foránea**
(la tabla de contratos aún no existe; CON-49 puede añadirla); `vigencia` TEXT; `umbral_dias`
(60 o 30); `estado` (`GENERADO`, `OMITIDO`); `prioridad` (`INFORMATIVA`, `PRIORITARIA`);
`destinatario_rol` (`ADMIN_JUNTA`); `fecha_fin` y `dias_restantes` observados; `motivo`;
`omitido_por_umbral` (umbral que lo reemplazó, solo si `OMITIDO`); `fecha_evaluacion`; `creado_en`.
Única por (`contrato_id`, `vigencia`, `umbral_dias`). Cada alta audita
`ALERTA_VENCIMIENTO_CONTRATO` con los siete campos mínimos más actor y contexto.

Entrega por correo: no incluida. Los avisos operativos de correo exigen un departamento y estas
alertas son del condominio; ver decisiones pendientes en la entrega.
