# language: es
Característica: Alta inactiva y habilitación administrativa de usuarios (CON-04)
  La contraseña inicial la define el administrador y solo SuperAdmin habilita el acceso.

  Escenario: Alta, habilitación y login persistente
    Dado un condominio y un SuperAdmin persistentes
    Cuando registra un usuario con contraseña inicial
    Entonces la cuenta queda inactiva y no puede iniciar sesión
    Cuando el SuperAdmin activa la cuenta
    Entonces el usuario inicia sesión con sus credenciales persistidas

  Escenario: Revocación al desactivar y reactivar
    Dado un condominio y un SuperAdmin persistentes
    Y un usuario activo con una sesión abierta
    Cuando el SuperAdmin desactiva y reactiva la cuenta
    Entonces el token anterior es rechazado y un nuevo login funciona

  Escenario: Solo SuperAdmin cambia el estado
    Dado un condominio y un SuperAdmin persistentes
    Y un usuario registrado por un administrador de junta
    Cuando el administrador de junta intenta activar la cuenta
    Entonces la API rechaza el cambio y conserva la cuenta inactiva

  Escenario: Duplicados normalizados y aislamiento
    Dado un condominio y un SuperAdmin persistentes
    Cuando registra un usuario con contraseña inicial
    Entonces repetir el correo o documento normalizado no crea otra identidad
    Y un administrador de otro condominio no consulta ni crea usuarios en este contexto

  Escenario: Estado repetido sin efectos duplicados
    Dado un condominio y un SuperAdmin persistentes
    Cuando registra un usuario con contraseña inicial
    Y el SuperAdmin solicita dos veces la activación
    Entonces solo un cambio de estado queda auditado
