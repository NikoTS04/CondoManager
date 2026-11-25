Feature: Invitación y cambios de acceso persistentes
  Scenario: El invitado elige su contraseña una sola vez
    Given una invitación pendiente en un condominio activo
    When el usuario activa con su token y contraseña
    Then puede iniciar sesión con la contraseña elegida
    And reutilizar el token es rechazado

  Scenario: La revocación conserva el control de acceso aunque falle el correo
    Given un inquilino con sesión y un reemplazo autorizado
    When la administración confirma el relevo
    Then la sesión anterior pierde acceso y el historial permanece
    And ambos avisos quedan en la cola durable sin duplicarse

  Scenario: La activación avisa una sola vez sin exponer secretos
    Given una invitación pendiente en un condominio activo
    When el usuario activa con su token y contraseña
    Then se encola un único aviso de cuenta activada para su correo
    And el aviso no contiene el token ni la contraseña
    And reintentar la activación no encola otro aviso

  Scenario: El aviso de activación se revalida antes de enviarse
    Given un aviso de cuenta activada en la cola
    When la cuenta deja de estar activa antes del despacho
    Then el aviso no se envía y queda como fallido permanente con alerta
