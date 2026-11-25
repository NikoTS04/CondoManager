# language: es
# Verificado por src/tests/integration/test_identidad_sprint3_db.py (PostgreSQL).
Característica: Aviso de cuenta activada (CON-78)

  Escenario: La activación avisa una sola vez sin exponer secretos
    Dado una invitación pendiente en un condominio activo
    Cuando el usuario activa con su token y contraseña
    Entonces se encola un único aviso de cuenta activada para su correo
    Y el aviso no contiene el token ni la contraseña
    Y reintentar la activación no encola otro aviso

  Escenario: El aviso de activación se revalida antes de enviarse
    Dado un aviso de cuenta activada en la cola
    Cuando la cuenta deja de estar activa antes del despacho
    Entonces el aviso no se envía y queda como fallido permanente con alerta
