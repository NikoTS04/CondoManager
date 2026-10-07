# Criterios de Aceptación: Usuarios, Roles RBAC y Condominios (BDD / Gherkin)

## Característica: Alta de Usuarios, Asignación de Roles y Registro de Condominios (PROC-05 / PROC-CORE)

### Escenario 1: Alta de usuario con correo único
```gherkin
Dado que el correo "residente101@gmail.com" no existe aún en el directorio
Cuando el administrador envía el alta del usuario con nombre "María", apellido "Flores" y documento "74125896"
Entonces el sistema crea el usuario en estado "esta_activo = true"
Y retorna el correo normalizado en minúsculas "residente101@gmail.com"
Y la contraseña se almacena únicamente como hash irreversible (nunca texto plano)
Y el evento queda registrado en la bitácora de auditoría con la acción "ALTA_USUARIO" y sus 7 campos obligatorios.
```

### Escenario 2: Rechazo de alta por correo duplicado
```gherkin
Dado que el correo "residente101@gmail.com" ya está registrado en el directorio
Cuando el administrador intenta crear un nuevo usuario con ese mismo correo
Entonces el sistema rechaza la operación con el código "EMAIL_YA_REGISTRADO"
Y la respuesta HTTP es "409 Conflict"
Y no se crea ningún usuario duplicado en la base de datos.
```

### Escenario 3: Asignación de rol RBAC dentro de un condominio
```gherkin
Dado un usuario existente "María" y un condominio "Villa Bonita 3" registrado
Cuando el administrador asigna el rol "RESIDENTE" al usuario dentro de ese condominio
Entonces el sistema crea la relación usuario-rol-condominio
Y retorna la respuesta HTTP "201 Created" con el rol asignado
Y el evento queda registrado en la bitácora de auditoría con la acción "ASIGNACION_ROL_USUARIO".
```

### Escenario 4: Prohibición de roles duplicados por unicidad usuario-condominio
```gherkin
Dado que el usuario ya posee un rol dentro del condominio "Villa Bonita 3"
Cuando el administrador intenta asignarle un segundo rol en ese mismo condominio
Entonces el sistema rechaza la operación con el código "ROL_YA_ASIGNADO"
Y la respuesta HTTP es "409 Conflict".
```

### Escenario 5: Registro de condominio con configuración de mora coherente
```gherkin
Dado que el administrador registra el condominio "Villa Bonita 3" con dirección "Av. Los Rosales 245"
Y selecciona la regla de mora "MONTO_FIJO" con un monto de "20.00"
Cuando el sistema procesa el alta
Entonces el condominio queda registrado con moneda "PEN", día de corte "20" y "2" días de gracia
Y retorna la respuesta HTTP "201 Created"
Y el evento queda registrado en la bitácora de auditoría con la acción "ALTA_CONDOMINIO".
```

### Escenario 6: Rechazo de condominio con regla de mora incoherente
```gherkin
Dado que el administrador selecciona la regla de mora "MONTO_FIJO"
Y no configura ningún monto de mora mayor a 0.00
Cuando el sistema procesa la solicitud de alta del condominio
Entonces el sistema rechaza la operación con el código "CONFIGURACION_MORA_INVALIDA"
Y la respuesta HTTP es "422 Unprocessable Entity".
```