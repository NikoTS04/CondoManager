Feature: Convergencia verificable con CON-72
  Scenario: Reporte multipart idempotente
    Given una unidad autorizada y un voucher válido
    When dos solicitudes equivalentes reportan la misma operación
    Then se conserva un solo comprobante, archivo, auditoría y evento
    And las respuestas son 202 COMPROBANTE_RECIBIDO y 200 VOUCHER_EN_EVALUACION

  Scenario: Subsanar sin destruir evidencia
    Given un comprobante OBSERVADO con una revisión persistida
    When el residente adjunta otro voucher válido
    Then conserva UUID, hash y datos bancarios y pasa a EN_REVISION
    And conserva el archivo anterior y publica otra recepción
    And una nueva revisión queda asociada al nuevo archivo

  Scenario: Repetir una revisión confirmada
    Given una revisión vigente confirmada
    When administración repite la misma decisión y motivo
    Then recibe la respuesta financiera original sin aplicar saldos otra vez
    And una decisión distinta responde 409 ESTADO_COMPROBANTE_INVALIDO

  Scenario: Mantener mensajes históricos
    Given eventos históricos y canónicos en el outbox
    When el consumidor recupera los mensajes más de una vez
    Then genera un aviso lógico por evento y destinatario sin modificar los mensajes
