# Criterios de Aceptación: Autenticación y Control de Acceso (RBAC) (BDD / Gherkin)

## Característica: Autenticación JWT y Control Granular de Pantallas por Rol

### Escenario 1: Inicio de sesión exitoso y generación de claims
```gherkin
Dado que existe un usuario con correo "admin@villabonita3.pe" y rol "ADMIN_JUNTA"
Cuando el usuario envía su correo y contraseña correcta a "/api/v1/auth/login"
Entonces la API responde con código HTTP 200 OK
Y la respuesta contiene un "access_token" JWT válido
Y el payload del token incluye el rol "ADMIN_JUNTA" y el identificador de condominio "vb3-condo".
```

### Escenario 2: Rechazo de credenciales incorrectas
```gherkin
Dado que existe un usuario registrado en el sistema
Cuando el usuario intenta iniciar sesión con una contraseña incorrecta
Entonces la API responde con código HTTP 401 Unauthorized
Y el mensaje de error indica "Credenciales inválidas".
```

### Escenario 3: Bloqueo de mutación administrativa para rol Residente
```gherkin
Dado que un usuario con rol "PROPIETARIO" ha iniciado sesión
Cuando el usuario intenta invocar "POST /api/v1/cuotas/emitir-lote" con su token Bearer
Entonces la API rechaza la solicitud con código HTTP 403 Forbidden
Y el mensaje de error indica "Acceso denegado: Se requiere rol de administración".
```

### Escenario 4: Modo solo lectura estricto para Auditor
```gherkin
Dado que un usuario con rol "AUDITOR" ha iniciado sesión
Cuando el usuario accede al panel de conciliación bancaria
Entonces la interfaz muestra los comprobantes y números de operación
Pero los botones "Aprobar Pago" y "Rechazar Pago" se encuentran ocultos
Y cualquier intento de enviar "POST /api/v1/pagos/{id}/conciliar" es rechazado por la API con HTTP 403.
```

### Escenario 5: Aislamiento contextual de departamentos en el Portal de Residentes
```gherkin
Dado que un residente tiene asignado únicamente el departamento "102"
Cuando el residente carga el portal "/residente"
Entonces el sistema bloquea la visualización de los datos de otros departamentos
Y las reservas de áreas comunes se registran bajo el identificador de su departamento "102".
```
