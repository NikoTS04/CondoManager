# Rediseño: información verificable por rol

No se modifican PROC-01/02/03/04 ni los contratos API. Cambia la presentación de sus datos.

## Cuenta del residente
Dado un residente con una unidad activa, cuando abre su portal, entonces ve primero Resumen y puede acceder a Pagos, Reservas y Avisos con teclado o móvil.

Dado que la API devuelve saldo a favor y deuda vencida, cuando consulta su resumen, entonces ve esos importes decimales sin cuotas, periodos ni penalidades referenciales; si un importe falta, ve «No disponible», nunca cero inferido.

## Mesa de trabajo de la junta
Dado un catálogo y comprobantes cargados, cuando la junta consulta Resumen o Moras, entonces ve conteos y estados de los registros recibidos; no puede ejecutar una evaluación simulada.

Dado un fallo al cargar los datos, cuando se muestra el error, entonces no se presentan conteos de cero ni listas vacías como si la consulta hubiera tenido éxito, y se ofrece Reintentar.

Dado un presupuesto aún no consultado, cuando abre Resumen, entonces se ofrece consultar Presupuesto sin afirmar que no hay uno aprobado.

## Contexto e interacción
Dado un usuario autenticado, cuando navega por su portal, entonces ve su usuario y rol, el contexto del condominio disponible y su unidad activa; nunca un nombre de condominio fijo.

Dado un auditor, cuando consulta la junta, entonces conserva el modo de solo lectura. Dado movimiento reducido, cuando opera la interfaz, entonces no recibe desplazamientos ni escalados animados.
