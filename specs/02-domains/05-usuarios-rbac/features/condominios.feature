# language: es
Característica: Configuración y aislamiento de condominios
  Como superadministrador
  Quiero registrar la configuración raíz de un condominio
  Para que sus operaciones se administren de forma independiente

  Escenario: Creación exitosa por SuperAdmin
    Dado que existe un usuario autenticado con rol "SUPERADMIN"
    Cuando registra un condominio válido llamado "Villa Bonita 3"
    Entonces la API responde con código 201
    Y el condominio queda activo con un UUID
    Y se registra la auditoría "CONDOMINIO_CREADO"

  Escenario: Rechazo de una solicitud sin autenticación
    Dado que la solicitud no tiene un Bearer Token
    Cuando intenta registrar un condominio válido llamado "Villa Bonita 3"
    Entonces la API responde con código 401
    Y no se persiste ningún condominio

  Escenario: Rechazo de un rol no autorizado
    Dado que existe un usuario autenticado con rol "ADMIN_JUNTA"
    Cuando intenta registrar un condominio válido llamado "Villa Bonita 3"
    Entonces la API responde con código 403
    Y no se persiste ningún condominio

  Escenario: Rechazo de una modalidad de mora inconsistente
    Dado que existe un usuario autenticado con rol "SUPERADMIN"
    Cuando registra un condominio con regla porcentual sin tasa
    Entonces la API responde con código 422
    Y no se persiste ningún condominio

  Escenario: Consulta de un condominio inexistente
    Dado que existe un usuario autenticado con rol "SUPERADMIN"
    Cuando consulta un UUID de condominio inexistente
    Entonces la API responde con código 404
    Y el error es "CONDOMINIO_NO_ENCONTRADO"

  Escenario: Aislamiento entre dos condominios
    Dado que existe un usuario autenticado con rol "SUPERADMIN"
    Y están registrados "Condominio Norte" y "Condominio Sur"
    Cuando consulta ambos condominios por sus UUID
    Entonces cada respuesta conserva su propia configuración

  Escenario: Selección entre condominios activos
    Dado que existe un usuario autenticado con rol "SUPERADMIN"
    Y están registrados "Condominio Norte" y "Condominio Sur"
    Cuando lista los condominios activos
    Entonces obtiene ambos condominios como contextos seleccionables
