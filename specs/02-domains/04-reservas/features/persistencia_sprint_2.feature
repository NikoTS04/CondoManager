Feature: Persistencia integrada de reservas y comunicaciones
  Scenario: Recuperar una reserva confirmada
    Given un residente activo con unidad solvente y área persistente
    When confirma una reserva y abre una sesión independiente
    Then conserva el mismo identificador, tarifa y horario
    And existe una auditoría y un evento pendiente de confirmación

  Scenario: Revertir una reserva incompleta
    Given un residente activo con unidad solvente y área persistente
    When falla la escritura del evento de reserva
    Then no quedan reserva, auditoría ni evento de éxito parciales

  Scenario: Excluir reservas concurrentes con calendario vacío
    Given un residente activo con unidad solvente y área persistente
    When diez sesiones solicitan el mismo intervalo
    Then una obtiene 201 y nueve obtienen 409

  Scenario: Consumir dos veces una confirmación
    Given una reserva confirmada con evento persistido
    When dos workers consumen el mismo evento
    Then cada destinatario tiene un solo aviso lógico persistido

  Scenario: Recuperar un envío temporalmente fallido
    Given un aviso persistido cuyo primer envío falla temporalmente
    When reinicia el worker y vence el próximo reintento
    Then conserva ambos intentos y la aceptación simulada queda ENVIADO
