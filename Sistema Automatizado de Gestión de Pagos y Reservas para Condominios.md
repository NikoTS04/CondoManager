## **Sistema Automatizado de Gestión de Pagos y Reservas para Condominios**

### **Descripción general**

El proyecto consiste en desarrollar un sistema automatizado para apoyar la gestión administrativa de un condominio, principalmente en dos procesos relacionados entre sí: la gestión de pagos de mantenimiento y la gestión de reservas de áreas comunes.

Actualmente, gran parte de estas actividades puede realizarse de forma manual mediante hojas de cálculo, mensajes, revisiones periódicas y verificaciones realizadas por el administrador o tesorero. Esto genera una alta carga administrativa, posibilidad de errores, falta de trazabilidad y conflictos entre residentes.

La propuesta busca reducir estas tareas repetitivas mediante un sistema que pueda detectar eventos, aplicar reglas de negocio, ejecutar acciones automáticas y verificar los resultados, manteniendo siempre la posibilidad de intervención humana en casos excepcionales.

---

## **Problema identificado**

La administración manual de cuotas, pagos, moras y reservas presenta diversos problemas:

* El administrador debe revisar manualmente quién pagó y quién mantiene deudas pendientes.  
* El cálculo y aplicación de moras puede realizarse de forma tardía o inconsistente.  
* Los recordatorios de pago dependen de que una persona los envíe.  
* Un residente con deuda podría intentar reservar áreas comunes si no existe una validación automática.  
* Existe poca trazabilidad respecto a notificaciones, pagos, restricciones y cambios realizados.  
* Las decisiones manuales pueden generar reclamos o percepción de trato desigual.  
* El administrador dedica tiempo a tareas repetitivas que podrían ejecutarse automáticamente.

---

## **Objetivo del sistema**

Automatizar la gestión de pagos, morosidad, notificaciones y reservas de áreas comunes del condominio, de manera que el sistema pueda ejecutar automáticamente las actividades rutinarias y dejar al administrador principalmente funciones de supervisión y atención de excepciones.

---

## **Alcance principal**

El sistema estará enfocado inicialmente en cinco procesos:

### **1\. Gestión de cuotas de mantenimiento \-\> Anderson**

El sistema permitirá generar las cuotas periódicas correspondientes a cada departamento, indicando monto, fecha de emisión, fecha de vencimiento y estado de la obligación.

Podrá determinar automáticamente cuándo una cuota se encuentra pendiente, pagada o vencida.

### **2\. Gestión de pagos y morosidad \-\> Tarqui**

El sistema registrará y validará los pagos asociados a cada residente o departamento.

Cuando una cuota alcance su fecha de vencimiento sin haberse registrado el pago correspondiente, el sistema evaluará las reglas configuradas y podrá:

* cambiar el estado de la deuda;  
* calcular la mora correspondiente;  
* actualizar el estado financiero del residente;  
* registrar la acción realizada.

Los casos excepcionales podrán ser revisados por el administrador.

### **3\. Gestión de notificaciones \-\> Alejandro**

El sistema enviará automáticamente comunicaciones relacionadas con el estado de las obligaciones del residente.

Las notificaciones podrán incluir:

* recordatorios antes del vencimiento;  
* aviso de vencimiento;  
* aviso de mora;  
* aviso de restricción;  
* confirmación de pago;  
* levantamiento de restricciones.

Las notificaciones seguirán reglas y tiempos previamente definidos y cada envío deberá quedar registrado para fines de trazabilidad.

### **4\. Gestión de reservas de áreas comunes \-\> brandon**

Los residentes podrán consultar la disponibilidad y solicitar la reserva de espacios como parrillas, salones, gimnasio u otras áreas comunes.

El sistema verificará automáticamente:

* disponibilidad del espacio;  
* fecha y horario;  
* reglas de reserva;  
* estado del residente.

Una vez cumplidas las condiciones, podrá confirmar o rechazar la solicitud.

### **~~5\. Validación automática del estado de pago para reservas~~**

Antes de aprobar una reserva, el sistema verificará automáticamente si el residente se encuentra habilitado según las reglas del condominio.

Por ejemplo:

Si el residente mantiene una deuda vencida que supera el periodo de gracia establecido, el sistema podrá impedir temporalmente nuevas reservas.

Cuando la deuda sea regularizada, el sistema podrá restablecer automáticamente el permiso correspondiente.

**5 GEstion de usuario**

- **para el administrador crear usuarios (tipo de usuarios.)**

---

## **Funcionamiento general de la automatización**

El sistema trabajará siguiendo el ciclo:

**Evento → evaluación de reglas → decisión → acción → verificación**

Ejemplo:

Un residente alcanza la fecha límite de pago.

El sistema detecta el vencimiento, verifica si existe un pago registrado y evalúa las reglas de morosidad.

Si no existe un pago válido, podrá aplicar la mora correspondiente, actualizar el estado del residente, enviar una notificación y registrar todas las acciones realizadas.

Posteriormente, si el residente intenta reservar un área común, el sistema consultará automáticamente su estado y decidirá si la reserva puede continuar.

---

## **Intervención humana**

La automatización no pretende eliminar completamente la intervención del administrador.

El administrador tendrá principalmente funciones de supervisión, configuración y gestión de excepciones.

Podrá intervenir en situaciones como:

* errores en el registro de pagos;  
* pagos duplicados;  
* pagos parciales;  
* reclamos de residentes;  
* fallos de conciliación;  
* errores en una restricción;  
* situaciones especiales que requieran revisión;  
* reversión o anulación de determinadas acciones automáticas.

---

## **Mecanismos de control**

El sistema deberá incluir mecanismos que permitan verificar que las automatizaciones se ejecutaron correctamente.

Entre ellos:

* registro de logs;  
* historial de acciones;  
* auditoría de pagos, moras y restricciones;  
* control de notificaciones enviadas;  
* reintentos ante fallos;  
* alertas al administrador;  
* reversión manual;  
* control de acciones duplicadas.

Por ejemplo, si una notificación no puede enviarse, el sistema deberá registrar el fallo e intentar nuevamente según las reglas establecidas.

Si después de varios intentos el problema continúa, deberá generar una alerta para el administrador.

---

## **Calidad y resiliencia**

El sistema deberá prevenir situaciones que puedan afectar injustamente a los residentes.

Por ello se deberán considerar:

* validación de pagos antes de aplicar una mora;  
* prevención de pagos duplicados;  
* control de fechas y montos;  
* pruebas de pagos puntuales, tardíos y parciales;  
* manejo de fallas en servicios externos;  
* protección ante la pérdida de eventos;  
* recuperación ante errores;  
* registro de las acciones automáticas.

---

## **Trazabilidad**

Cada acción importante deberá quedar registrada indicando, como mínimo:

* residente o departamento involucrado;  
* fecha y hora;  
* acción ejecutada;  
* motivo;  
* resultado;  
* estado anterior;  
* estado posterior.

Esto permitirá atender reclamos y verificar posteriormente por qué el sistema realizó determinada acción.

---

## **Principios de la solución**

El sistema deberá aplicar las reglas de forma uniforme y transparente.

También deberá existir un mecanismo que permita al residente consultar su estado de cuenta y conocer el motivo de una mora, notificación o restricción.

La automatización deberá reducir las tareas repetitivas sin eliminar completamente la supervisión humana.

---

## **Resultado esperado**

Con la implementación del sistema se espera reducir el trabajo manual del administrador, mejorar el seguimiento de pagos, aplicar reglas de manera consistente, disminuir errores, mejorar la trazabilidad y relacionar automáticamente el estado financiero de los residentes con determinadas funciones del condominio, especialmente las reservas de áreas comunes.

El administrador pasará de realizar constantemente tareas operativas a supervisar el funcionamiento del sistema y gestionar únicamente los casos que requieran intervención humana.

