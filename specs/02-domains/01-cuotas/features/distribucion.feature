# language: es
Característica: Configurar la distribución de cuotas (CON-10)
  Como administrador del condominio
  Quiero elegir alícuota o distribución equitativa
  Para aplicar la regla aprobada antes de emitir cuotas

  Escenario: Configurar alícuota válida
    Dado departamentos del condominio con coeficientes 60.0000 y 40.0000
    Cuando ADMIN_JUNTA configura POR_ALICUOTA en su condominio
    Entonces se guarda una configuración con actor y fecha UTC
    Y el cambio queda auditado en la misma transacción
    Y un presupuesto de 100.01 produce montos 60.01 y 40.00

  Esquema del escenario: Rechazar sumas inexactas sin tolerancia
    Dado departamentos cuya suma de coeficientes es <suma>
    Cuando configuro POR_ALICUOTA
    Entonces recibo 422 con DISTRIBUCION_COEFICIENTES_INVALIDOS
    Y no se persiste ningún cambio ni auditoría
    Ejemplos:
      | suma     |
      | 99.9999  |
      | 100.0001 |

  Escenario: Distribuir equitativamente sin ajuste residual
    Dado tres departamentos del condominio
    Cuando configuro EQUITATIVA y calculo un presupuesto Decimal de 100.00
    Entonces cada monto es 33.33 usando ROUND_HALF_UP
    Y CON-11 es responsable del centavo residual

  Esquema del escenario: No se permite configurar sin departamentos
    Dado un condominio sin departamentos
    Cuando configuro <metodo>
    Entonces recibo 422 con DISTRIBUCION_SIN_DEPARTAMENTOS
    Ejemplos:
      | metodo       |
      | POR_ALICUOTA |
      | EQUITATIVA   |

  Escenario: PUT idempotente
    Dado una configuración válida persistida
    Cuando repito el PUT con el mismo método
    Entonces recibo la misma configuración sin cambiar actor ni fecha
    Y no se duplica la auditoría

  Escenario: Aislamiento y autorización
    Dado un usuario ADMIN_JUNTA del condominio A
    Cuando intenta consultar o configurar la distribución del condominio B
    Entonces recibe 403 con DISTRIBUCION_ACCESO_DENEGADO
    Y AUDITOR solo puede consultar en su condominio
    Y un usuario sin token recibe 401

  Escenario: Revalidar antes de emitir
    Dado una configuración POR_ALICUOTA válida persistida
    Y los coeficientes cambian y dejan de sumar 100.0000
    Cuando CON-11 recupera la configuración para emisión
    Entonces se rechaza su uso con DISTRIBUCION_COEFICIENTES_INVALIDOS
