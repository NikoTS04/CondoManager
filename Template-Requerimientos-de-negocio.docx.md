# Requerimientos de negocio para \<\<Proyecto\>\>

## Versión: 0.1

# 

# Contenido

# Historial de revisiones

| Autor | Fecha | Comentarios | Versión |
| :---- | :---- | :---- | :---- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

# 

# 1\. Requerimientos del negocio

## 1.1 Situación actual

* **Centralización del conocimiento operativo:** Los procesos clave y la experiencia del negocio se concentran en una sola persona, una dinámica que se extiende al resto de los miembros de la junta directiva.  
* **Conciliación y recaudación vulnerable (139 departamentos):** El registro de ingresos mediante Yape o transferencias interbancarias depende de la verificación manual y de que el propietario indique correctamente su número de departamento. La consistencia de la información se ve comprometida por errores en la captura de datos y la falta de estandarización en el personal a cargo.  
* **Deficiente categorización de egresos:** Los gastos comunes carecen de una clasificación adecuada según su propósito, dificultando el control presupuestal.  
* **Baja trazabilidad en transacciones con proveedores:** El seguimiento de pagos y acuerdos es complejo debido a la dispersión de comprobantes e información en canales no centralizados (correos electrónicos y chats de WhatsApp).  
* **Gestión manual de mora:** El cálculo y cobro de penalidades por atraso se efectúa de forma manual, lo que sobrecarga la operación e incrementa la fricción y los conflictos entre propietarios.  
* **Generación ineficiente de reportería:** La elaboración de informes financieros y la visualización de indicadores clave de gestión siguen realizándose manualmente, limitando la toma de decisiones oportuna.

## 1.2 Oportunidad del negocio

*\<\<En esta sección se describe el problema que se va a resolver o la oportunidad de negocio que existe. Incluye cosas como:* 

* *Se compite en el mercado de administración de negocio.*  
* *El software operará dentro de los edificios de condominios.*  
* *Las soluciones actuales incluyen tablas de excel.*  
* *Los problemas que no se pueden resolver son principalmente la trazabilidad e integridad de los datos.*

## 1.3 Objetivos de negocio y Criterios de éxito

* *Automatización de procesos de negocio*  
* *Estandarización de metodología de procesos de la administración.*  
* *Capacitación de nuevas juntas directivas al sistema.*  
* *Disminuir la complejidad de los procesos de administración.*

## 1.4 Riesgos

* *Ausencia de personería jurídica.*  
* *Cambios de juntas directivas que no se adapten fácilmente al sistema.*

# 2\. Visión de la solución

## 2.1 Declaración de la visión de la solución

***Para** el edificio 3 de Villa Bonita 3*  
***quienes** experimentan complicaciones de tiempo, trazabilidad y falta de centralización de los datos*  
***la** solución de software*  
***es** un sistema web, en pro de la accesibilidad y quizá una aplicación móvil*  
***el cual** busca optimizar los procesos previamente mencionados*

## 2.2 Funciones principales

**Gestión de Ingresos y Validación de Pagos**

* **Portal de reporte de pagos para residentes:** Formulario donde el propietario o inquilino registra su pago seleccionando explícitamente su torre/departamento, adjuntando captura de transferencia o Yape, monto, fecha y código de operación.  
* **Bandeja de conciliación y validación:** Panel para la junta directiva que permite aprobar o rechazar comprobantes reportados, evitando duplicidad de operaciones y reduciendo la dependencia del criterio manual del encargado de turno.  
* **Estado de cuenta por departamento:** Historial en línea y descargable que muestra cuotas ordinarias y extraordinarias pagadas, saldos pendientes y recibos generados.

**Cálculo Automatizado de Moras y Cobranzas**

* **Motor de recargos automático:** Aplicación parametrizable de penalidades e intereses por retraso en el pago una vez vencida la fecha de corte, eliminando el cálculo manual y los reclamos por discrecionalidad.  
* **Notificaciones y recordatorios automáticos:** Envío de avisos preventivos de vencimiento, alertas de morosidad y estados de cuenta a través de correo electrónico o mensajes automáticos.

**Control de Egresos y Gastos Comunes**

* **Categorización estructurada de gastos:** Registro de salidas de dinero clasificadas según su propósito (mantenimiento de ascensores, limpieza, seguridad, servicios básicos, imprevistos).  
* **Gestión centralizada de proveedores:** Registro único de contratistas y proveedores externos que vincula facturas, órdenes de servicio, presupuestos, contratos y comprobantes de pago en una sola ficha, evitando la dispersión en WhatsApp o correos.

**Reportes, Transparencia e Indicadores (KPIs)**

* **Dashboard de indicadores clave:** Visualización en tiempo real de tasa de morosidad, flujo de caja mensual (ingresos vs. egresos), porcentaje de recaudación y saldo disponible.  
* **Generador de balances mensuales:** Creación automática de balances financieros y rendiciones de cuentas periódicas en formato PDF o descargable para asambleas de propietarios.

**Administración, Accesibilidad y Transición de Juntas**

* **Gestión de roles y accesos:** Perfiles diferenciados (Administrador/Junta Directiva, Propietario, Inquilino, Auditor) para garantizar integridad y evitar accesos no autorizados.  
* **Pistas de auditoría y trazabilidad:** Registro inmutable de cada cambio, aprobación de pago o modificación de datos, documentando qué usuario lo realizó y cuándo.  
* **Módulo de transición y documentación interna:** Espacio dentro del sistema con guías de operación, historial de acuerdos y actas para mitigar el impacto de los cambios de directiva y facilitar la inducción a nuevos miembros.

**Gestión de Repositorio de Contratos y Empresas Proveedoras**

* **Directorio de proveedores y hojas de servicio:** Registro integral de empresas contratistas (seguridad, limpieza, mantenimiento de ascensores, bombas) que consolide RUC, datos de contacto de emergencia, acuerdos de nivel de servicio (SLA) y calificaciones de desempeño.  
* **Custodia digital y control de vigencias:** Repositorio centralizado para el almacenamiento de contratos marco, pólizas de seguro de la edificación, garantías técnicas y addendas, equipado con un sistema de alertas tempranas que notifique con 30 o 60 días de anticipación el vencimiento o la necesidad de renovación de cada acuerdo.  
* **Vinculación contractual y documental de pagos:** Asociación directa de cotizaciones, órdenes de servicio y facturas electrónicas a la ficha del contrato correspondiente, impidiendo la dispersión de acuerdos en canales informales como WhatsApp o bandejas personales de correo.

**Pistas de Auditoría y Trazabilidad Global de Movimientos Financieros**

* **Libro mayor y bitácora unificada de flujo de caja:** Vista cronológica y detallada de cada ingreso validado (cuotas, moras, reservas) y cada egreso ejecutado (pagos a contratistas, servicios públicos), con filtros por fecha, categoría presupuestal y medio de pago (Yape, cuenta interbancaria, efectivo).  
* **Registro inmutable de transacciones:** Mecanismo de auditoría que documenta la huella digital de cada movimiento (usuario responsable del registro, usuario que aprobó la operación, fecha, hora y comprobante digital adjunto).  
* **Control estricto de anulaciones y correcciones:** Prohibición del borrado permanente de asientos contables; cualquier rectificación se procesa mediante notas de crédito o ajustes compensatorios explícitos, dejando constancia visible del motivo de la corrección para futuras auditorías de la junta directiva.

**Mesa de Ayuda y Gestión de Tickets de Incidencias**

* **Reporte y categorización por parte del residente:** Formulario accesible desde la web/móvil para que los vecinos informen fallas en infraestructura o áreas comunes (fugas de agua, luminarias quemadas, averías en puertas o ascensores), permitiendo adjuntar evidencia fotográfica y nivel de urgencia percibido.  
* **Tablero de control y ciclo de vida de atención:** Flujo de estados claramente definidos (Registrado, Asignado a proveedor, En proceso, Resuelto, Cerrado) gestionado por la administración, asignando responsables y plazos estimados de solución.  
* **Historial de intervenciones y retroalimentación:** Registro de acciones tomadas, costos o piezas asociadas para la resolución del problema y cierre formal con confirmación o calificación de conformidad por parte del residente que abrió el ticket.

## 2.3 Suposiciones y dependencias

*\<\<En esta sección registra las suposiciones que se hicieron mientras se concebía este documento de visión y alcance. Anota las dependencias principales que el proyecto debe utilizar, que incluyen:*

* *Tecnologías específicas*  
* *Proveedores externos*  
* *Outsourcing de desarrollo*  
* *Otras relaciones del negocio\>\>*

## 2.4 Limitaciones y exclusiones

\<\<Identifica alguna función o característica que los stakeholders puedan identificar, pero que no está planeada para incluirse en esta versión del producto\>\>