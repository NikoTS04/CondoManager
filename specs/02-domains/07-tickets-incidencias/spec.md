# Dominio 07: Mesa de Ayuda y Tickets de Incidencias

## 1. Ficha del Dominio
- **Identificador:** DOM-07 / PROC-07
- **Responsable:** **Mantenimiento / Administración**
- **Estado:** Aprobado para Implementación
- **Versión:** 2.1 (SDD Detallado)
- **Módulos de Código:** `src/modules/tickets/`

---

## 2. Propósito y Ciclo de Vida
Permite a los residentes reportar desperfectos en infraestructura común (bombas de agua, iluminación de pasillos, ascensores, portones eléctricos) adjuntando fotos de evidencia y monitoreando el ciclo de resolución:
$$\text{REGISTRADO} \longrightarrow \text{ASIGNADO} \longrightarrow \text{EN\_PROCESO} \longrightarrow \text{RESUELTO} \longrightarrow \text{CERRADO}$$

El flujo vigente mantiene la clasificación, priorización y asignación bajo responsabilidad del administrador. La extensión `TIC-06` propone asistir estas tareas mediante IA y automatizar su ejecución operativa mediante RPA; permanece como mejora futura y no debe presentarse como funcionalidad implementada.

---

## 3. Responsabilidades del Dominio

- Recibir una incidencia con ubicación, descripción, urgencia declarada y evidencia opcional.
- Conservar el ciclo de vida y las transiciones válidas del ticket.
- Asociar un responsable interno o proveedor compatible y un plazo de atención.
- Conservar comentarios, diagnósticos, costos, evidencias y cambios de estado.
- Permitir que el residente confirme la solución o reabra el ticket.
- Registrar en auditoría cada decisión y corrección relevante.

---

## 4. Extensión Futura TIC-06: IA + RPA

### 4.1 Aporte de IA

La IA actúa como apoyo probabilístico a la decisión y devuelve:

- categoría sugerida;
- prioridad sugerida;
- nivel de confianza;
- posibles tickets duplicados;
- responsable o especialidad recomendada;
- señales de criticidad detectadas.

La salida de IA no constituye por sí sola una aprobación, rechazo, cierre ni autorización de gasto.

### 4.2 Aporte de RPA

RPA aplica reglas determinísticas sobre la recomendación y el contexto del dominio para:

- crear o completar el ticket;
- asignar un proveedor compatible en casos normales;
- iniciar el plazo de atención;
- actualizar el estado permitido;
- registrar la ejecución y sus resultados;
- verificar las poscondiciones;
- reintentar fallos temporales o remitir excepciones a revisión humana.

### 4.3 Automatización Atendida y Desatendida

- **Desatendida:** procesa en segundo plano casos normales que superan las validaciones, controla plazos, verifica resultados y escala vencimientos.
- **Atendida:** presenta la recomendación al administrador y espera confirmación o corrección cuando existe baja confianza, criticidad, ambigüedad, costo elevado o falta de proveedor compatible.

---

## 5. Guardas e Invariantes

- Una incidencia crítica nunca se asigna exclusivamente por recomendación probabilística.
- Las reglas críticas determinísticas prevalecen sobre la categoría o prioridad sugerida por IA.
- Un ticket solo pasa de `REGISTRADO` a `ASIGNADO` si tiene responsable compatible y plazo definido.
- Una clave de idempotencia impide crear o asignar dos veces el mismo ticket durante reintentos.
- Un proveedor puede marcar el trabajo como `RESUELTO`, pero solo la confirmación del residente o una decisión administrativa autorizada permite pasar a `CERRADO`.
- Toda corrección humana conserva la recomendación original, el valor corregido, el actor y el motivo.
- Ningún fallo de automatización elimina el reporte original del residente.

---

## 6. Detección y Manejo de Errores

| Error o señal | Detección | Respuesta requerida |
| :--- | :--- | :--- |
| Datos incompletos | Validación de campos obligatorios | Mantener borrador y solicitar información |
| Evidencia inválida | Validación de formato, tamaño y seguridad | Rechazar el archivo, no el reporte completo |
| Baja confianza | Puntaje inferior al umbral configurable | Enviar a revisión humana |
| Contradicción | Categoría declarada incompatible con la recomendación o reglas críticas | Bloquear asignación desatendida |
| Posible duplicado | Similitud de ubicación, tiempo, descripción o evidencia | Proponer vinculación; no fusionar automáticamente |
| Proveedor incompatible | Especialidad o disponibilidad no cumple la categoría | Buscar alternativa o escalar |
| Fallo temporal de RPA | Timeout o error recuperable del sistema externo | Reintentar con límite y espera controlada |
| Ejecución parcial | Falta alguna poscondición esperada | Marcar excepción y continuar desde el último paso seguro |
| Incumplimiento de plazo | Temporizador supera el SLA configurado | Escalar o reasignar |
| Solución no conforme | Residente rechaza el resultado | Volver a `EN_PROCESO` con motivo registrado |

---

## 7. Verificación Posterior de RPA

Una ejecución solo se considera exitosa cuando se comprueba desde almacenamiento persistente que:

- existe exactamente un ticket para la clave de operación;
- el estado corresponde al flujo permitido;
- el responsable es compatible con la categoría confirmada;
- el plazo de atención está definido;
- la auditoría registra entrada, recomendación, regla aplicada, acción y resultado.

Si alguna comprobación falla, el resultado es `FALLIDO_CONTROL`; el proceso no informa éxito general y remite la ejecución a reintento o revisión manual.

---

## 8. Indicadores Propuestos

- **Tiempo promedio de asignación:** suma de tiempos entre registro y asignación / tickets asignados.
- **Exactitud de clasificación confirmada:** recomendaciones aceptadas sin corrección / recomendaciones revisadas x 100.
- **Resolución dentro del plazo:** tickets resueltos dentro del SLA / tickets resueltos x 100.

Estos indicadores evalúan la mejora; no constituyen resultados obtenidos mientras `TIC-06` permanezca sin implementar.

---

## 9. Criterios de Aceptación del Dominio

- Un reporte válido crea un ticket `REGISTRADO` con identificador único.
- Solo se permiten transiciones definidas por el ciclo de vida del ticket.
- La asignación identifica responsable y plazo estimado.
- Cada cambio de estado registra fecha, actor y observación.
- La confirmación del residente cierra el ticket; su disconformidad lo devuelve a `EN_PROCESO` con motivo.
- Cuando `TIC-06` sea implementado, los casos críticos o bajo el umbral deben quedar bajo control humano y cada ejecución RPA debe superar su verificación posterior.
