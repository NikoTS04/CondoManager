# language: es
# Contrato aceptado CON-51/52; escenarios describen el comportamiento objetivo,
# todavía no implementado.
Característica: Registro, aprobación y pago de egresos de proveedores
  Como integrante autorizado de la Junta o Tesorería
  Quiero registrar y aprobar egresos y confirmar sus pagos reales
  Para mantener trazabilidad financiera sin confundir presupuesto, ingresos y caja

  Antecedentes:
    Dado que el actor opera en el contexto autorizado de un condominio
    Y los importes se procesan como Decimal con dos posiciones

  Escenario: Registrar un borrador no afecta la caja
    Dado que existe un concepto presupuestal activo del condominio
    Cuando la Junta registra un egreso con descripción, justificación, moneda y fecha
    Entonces el egreso queda en estado "BORRADOR"
    Y queda asociado al concepto existente
    Y no se crea un pago ni un movimiento de caja

  Escenario: Proveedor opcional con pertenencia contextual
    Dado que el egreso puede no tener proveedor
    Cuando se registra sin "proveedor_id"
    Entonces el egreso se conserva con proveedor nulo
    Pero cuando se informa un proveedor de otro condominio
    Entonces la operación se rechaza sin revelar sus datos

  Escenario: Contrato opcional coherente con proveedor
    Dado que el contrato es opcional
    Cuando se informa un contrato perteneciente a otro proveedor o condominio
    Entonces la operación se rechaza
    Y no se guarda una relación cruzada

  Escenario: No se presenta a aprobación sin configuración
    Dado que no existe configuración de aprobación para el condominio
    Cuando se intenta presentar el borrador
    Entonces responde "APROBACION_CONFIGURACION_REQUERIDA"
    Pero permite consultar y editar el borrador según su estado

  Escenario: El registrador no aprueba su propio egreso
    Dado que un egreso está pendiente de aprobación
    Cuando su registrador intenta aprobarlo
    Entonces la decisión se rechaza
    Y el egreso conserva su estado y monto

  Escenario: Importe sobre umbral requiere aprobación adicional
    Dado que existe una política configurada y el importe supera su umbral
    Cuando un actor distinto del registrador registra una aprobación
    Entonces el egreso permanece "PENDIENTE_APROBACION"
    Cuando otra persona autorizada distinta registra la aprobación requerida
    Entonces el egreso pasa a "APROBADO"

  Escenario: Rechazo conserva motivo e historial
    Dado que un egreso está pendiente de aprobación
    Cuando un actor autorizado lo rechaza con motivo
    Entonces pasa a "RECHAZADO"
    Y se conserva actor, motivo, importe, versión y fecha de decisión

  Escenario: Modificar importe invalida aprobaciones anteriores
    Dado que existe una aprobación registrada para una versión del egreso
    Cuando se modifica el importe en un estado que permite corrección
    Entonces se incrementa la versión
    Y las aprobaciones anteriores no autorizan la nueva versión
    Y el historial anterior permanece conservado

  Escenario: Aprobar no confirma el pago
    Dado que un egreso cumple la política de aprobación
    Cuando se completa su aprobación
    Entonces queda "APROBADO"
    Y no se crea movimiento de salida de caja

  Escenario: No confirmar pago sin apertura conciliada
    Dado que un egreso está aprobado
    Y la cuenta no tiene apertura de caja conciliada
    Cuando Tesorería intenta confirmar el pago
    Entonces responde "CAJA_NO_CONFIGURADA"
    Y no se registra pago confirmado ni movimiento de caja

  Escenario: Confirmar pago con movimiento y auditoría atómicos
    Dado que el egreso está aprobado y la cuenta tiene caja conciliada suficiente
    Y Tesorería ejecutó el pago bancario y adjunta su evidencia
    Cuando confirma el pago con una clave de idempotencia
    Entonces se registra fecha, importe, referencia, cuenta y actor
    Y se inserta exactamente un movimiento de salida
    Y la auditoría y el pago se confirman en la misma transacción

  Escenario: Reintento idempotente no duplica la salida
    Dado que un pago fue confirmado con una clave y un payload
    Cuando se repite la misma solicitud con la misma clave y payload
    Entonces se devuelve el resultado original
    Y no se crea un segundo pago ni movimiento

  Escenario: Clave repetida con contenido distinto
    Dado que una clave de idempotencia ya identifica un pago
    Cuando se reutiliza con otro importe o referencia
    Entonces responde "IDEMPOTENCIA_CONFLICTO"
    Y la caja no cambia

  Escenario: Pagos parciales permanecen deshabilitados por defecto
    Dado que la política de pagos parciales está deshabilitada
    Y el egreso está aprobado por un saldo pendiente
    Cuando se intenta confirmar un importe menor al saldo aprobado
    Entonces se rechaza la operación
    Y no se registra movimiento de caja

  Escenario: Pagos parciales habilitados no exceden el aprobado
    Dado que Tesorería habilitó pagos parciales en la configuración
    Y el egreso está aprobado
    Cuando se confirma un pago parcial válido
    Entonces el egreso pasa a "PAGO_PARCIAL"
    Y los pagos acumulados no exceden el importe aprobado

  Escenario: Reverso usa movimiento compensatorio
    Dado que existe un pago confirmado
    Cuando un actor autorizado lo revierte con motivo
    Entonces el pago original permanece en el historial como "REVERSADO"
    Y se crea un movimiento compensatorio relacionado
    Y no se borra ni modifica el movimiento original

  Escenario: Concurrencia no duplica aprobación ni caja
    Dado que dos solicitudes concurrentes intentan decidir o confirmar el mismo egreso
    Cuando ambas se procesan
    Entonces solo una transición válida puede avanzar sobre la versión vigente
    Y la caja contiene como máximo un movimiento por pago idempotente

  Escenario: Auditor consulta sin mutar
    Dado que el actor tiene rol "AUDITOR" en el condominio
    Cuando consulta egresos, documentos e historial
    Entonces solo recibe información del condominio autorizado
    Pero no puede registrar, aprobar, confirmar ni revertir pagos

  Escenario: Aislamiento entre condominios
    Dado que el egreso, proveedor, contrato o cuenta pertenecen a otro condominio
    Cuando un actor intenta consultarlos o asociarlos
    Entonces la operación se deniega sin revelar información ajena
