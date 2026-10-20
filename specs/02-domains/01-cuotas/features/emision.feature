# language: es
Característica: Emisión persistente del lote mensual CON-11
  Escenario: Emitir desde presupuesto aprobado y aplicar saldos conservando el bruto
    Dado un presupuesto aprobado de "100.00" y tres departamentos activos equitativos
    Y un departamento inactivo y un crédito de "40.00" en la primera unidad
    Cuando el administrador emite el periodo "2026-10"
    Entonces se persisten tres cuotas cuyo bruto suma "100.00"
    Y la primera cuota queda pagada conservando el crédito restante
    Y existe un único evento de lote y una cadena de auditoría válida

  Escenario: Reintentar una emisión desde otra sesión
    Dado un lote persistido para el periodo "2026-10"
    Cuando se emite nuevamente el mismo condominio y periodo
    Entonces se rechaza con "LOTE_YA_EMITIDO" sin consumir crédito ni duplicar eventos

  Escenario: Revertir todo el lote ante un fallo intermedio
    Dado un presupuesto aprobado y departamentos con créditos
    Cuando falla la emisión después de aplicar el primer crédito
    Entonces no persiste ninguna cuota, aplicación, auditoría, lote ni evento
    Y se conserva íntegro el saldo original

  Escenario: Impedir emisiones sin presupuesto aprobado
    Dado un presupuesto en borrador para el periodo solicitado
    Cuando se intenta emitir el lote
    Entonces se rechaza con "PRESUPUESTO_NO_APROBADO" sin escrituras
