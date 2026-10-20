# Criterios de Aceptación: Autenticación y Control de Acceso (RBAC) (BDD / Gherkin)

## CON-04 — Alta inactiva y habilitación manual

Contrato: [alta administrativa](../02-domains/05-usuarios-rbac/alta-administrativa.md).
Escenarios ejecutables: [alta_usuarios.feature](../02-domains/05-usuarios-rbac/features/alta_usuarios.feature).

- El administrador crea una cuenta con contraseña inicial y estado inactivo.
- Solo SuperAdmin habilita o deshabilita la cuenta desde la aplicación.
- Login, autorización y restauración consultan la identidad persistida.
- Desactivar/reactivar invalida las sesiones anteriores; repetir un estado es un no-op.
- Correo y documento normalizados no se duplican, tampoco concurrentemente.
- Alta, asignación inicial y auditoría se confirman o revierten conjuntamente.
- La activación administrativa es independiente de una futura verificación por correo.

## Característica: Autenticación JWT y Control Granular de Pantallas por Rol

### Escenario 1: Inicio de sesión exitoso y generación de claims
```gherkin
Dado que existe un usuario con correo "admin@villabonita3.pe" y rol "ADMIN_JUNTA"
Cuando el usuario envía su correo y contraseña correcta a "/api/v1/auth/login"
Entonces la API responde con código HTTP 200 OK
Y la respuesta contiene un "access_token" JWT válido
Y el payload del token incluye el rol "ADMIN_JUNTA", el UUID del condominio piloto y "session_version" igual a 2.
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
Dado que un usuario con rol "RESIDENTE" ha iniciado sesión
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

## Característica: Configuración y Aislamiento de Condominios (CON-2 / USR-01)

### Escenario 6: Creación exitosa de un condominio por SuperAdmin

```gherkin
Dado que un usuario autenticado tiene rol global "SUPERADMIN"
Cuando envía una solicitud POST a "/api/v1/condominios" con nombre "Villa Bonita 3", dirección "Av. Principal 123, Lima", moneda "PEN", regla de mora "MONTO_FIJO", monto de mora "20.00", día de vencimiento 20 y 2 días de gracia
Entonces la API responde con código HTTP 201 Created
Y la respuesta contiene un "id" con formato UUID generado por el servidor
Y el condominio queda persistido con "activo" igual a true
Y "creado_en" contiene una fecha y hora UTC
Y existe una auditoría "CONDOMINIO_CREADO" asociada al usuario autenticado.
```

### Escenario 7: Rechazo de creación sin autenticación

```gherkin
Dado que la solicitud no contiene un Bearer Token válido
Cuando intenta enviar POST a "/api/v1/condominios"
Entonces la API responde con código HTTP 401 Unauthorized
Y el error contiene el código "NO_AUTENTICADO"
Y no se persiste ningún condominio.
```

### Escenario 8: Rechazo de creación para un rol no autorizado

```gherkin
Dado que un usuario autenticado tiene rol "ADMIN_JUNTA"
Cuando intenta enviar POST a "/api/v1/condominios" con datos válidos
Entonces la API responde con código HTTP 403 Forbidden
Y el error contiene el código "ACCESO_DENEGADO"
Y no se persiste ningún condominio.
```

### Escenario 9: Validación condicional de la modalidad de mora

```gherkin
Dado que un usuario autenticado tiene rol global "SUPERADMIN"
Cuando intenta crear un condominio con regla "PORCENTAJE_SALDO", tasa nula y monto fijo "20.00"
Entonces la API responde con código HTTP 422 Unprocessable Entity
Y el error identifica la combinación inválida de la regla de mora
Y no se persiste ningún condominio ni auditoría.
```

### Escenario 10: Consulta del condominio persistido

```gherkin
Dado que un "SUPERADMIN" creó un condominio y recibió su UUID
Cuando consulta GET "/api/v1/condominios/{condominio_id}" con ese UUID
Entonces la API responde con código HTTP 200 OK
Y devuelve el mismo nombre, dirección, moneda, regla de mora, día de vencimiento y días de gracia
Y devuelve "activo" igual a true.
```

### Escenario 11: Consulta de un condominio inexistente

```gherkin
Dado que un usuario autenticado tiene rol global "SUPERADMIN"
Y no existe un condominio con el UUID solicitado
Cuando consulta GET "/api/v1/condominios/{condominio_id}"
Entonces la API responde con código HTTP 404 Not Found
Y el error contiene el código "CONDOMINIO_NO_ENCONTRADO".
```

### Escenario 12: Aislamiento entre dos condominios

```gherkin
Dado que existen los condominios "Condominio Norte" y "Condominio Sur" con UUID distintos
Y cada uno tiene configuración financiera diferente
Cuando se consulta cada condominio por su UUID
Entonces cada respuesta contiene únicamente la configuración asociada al UUID solicitado
Y ningún dato de "Condominio Norte" aparece en la respuesta de "Condominio Sur"
Y ningún dato de "Condominio Sur" aparece en la respuesta de "Condominio Norte".
```

### Escenario 13: Selección del condominio activo por SuperAdmin

```gherkin
Dado que un usuario autenticado tiene rol global "SUPERADMIN"
Y existen uno o más condominios activos
Cuando consulta GET "/api/v1/condominios"
Entonces la API responde con código HTTP 200 OK
Y devuelve los condominios activos como contextos seleccionables
Y si existe más de uno la interfaz exige una selección explícita
Y los usuarios sin rol "SUPERADMIN" no pueden utilizar el listado global.
```

### Escenario 14: Relaciones distintas sin cambiar de rol

```gherkin
Dado un usuario RESIDENTE propietario de la unidad 102 e inquilino de la 504
Cuando inicia sesión y consulta /auth/me
Entonces recibe ambos vínculos con UUID, número, tipo_relacion y es_activo
Y el JWT conserva rol RESIDENTE para ambos vínculos
Y al seleccionar cada unidad la etiqueta cambia entre Propietario e Inquilino
Y no aparecen unidades ajenas o vínculos inactivos en el selector.
```

### Escenario 15: Autorización de recursos y cancelación sin elevación

```gherkin
Dado un RESIDENTE vinculado únicamente a la unidad 102
Cuando reporta un pago o crea/cancela una reserva de una unidad ajena
Entonces recibe 403 y no se modifica ningún recurso
Y enviar es_admin=true no evita la regla de 24 horas para su propia reserva
Y el departamento moroso sigue bloqueado aunque el otro vínculo esté al día.
```

### Escenario 16: Renovación obligatoria y restauración segura

```gherkin
Dado un token anterior a la versión de sesión 2 o con rol PROPIETARIO o INQUILINO
Cuando intenta acceder a una ruta protegida
Entonces recibe 401 SESION_DESACTUALIZADA y debe iniciar sesión de nuevo
Y el frontend descarta esa sesión en lugar de restaurarla o entrar automáticamente
Y un UUID de unidad ajena en URL o almacenamiento no cambia la unidad autorizada.
```

### Escenario 17: Aislamiento administrativo y consulta del calendario

```gherkin
Dado un ADMIN_JUNTA o AUDITOR con contexto de condominio A
Cuando consulta o modifica recursos del condominio B
Entonces recibe 403 y no se modifica ningún recurso
Y AUDITOR puede consultar los recursos de A pero nunca enviar pagos, reservas o comunicados
Y un residente consulta horarios ocupados sin recibir datos privados de otras unidades.
```
