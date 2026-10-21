# language: es
Característica: Roles persistentes y revocación de permisos CON-06
  Antecedentes:
    Dado un condominio con SuperAdmin y usuarios persistentes para roles

  Escenario: Cambiar el rol requiere renovar la sesión
    Cuando el SuperAdmin cambia un residente a Auditor
    Entonces la sesión anterior queda revocada
    Y un nuevo login obtiene el rol Auditor de solo lectura

  Escenario: Junta no puede conceder administración
    Cuando la Junta intenta asignar Admin Junta a un residente
    Entonces el cambio de rol se rechaza sin modificar la asignación

  Escenario: Junta puede gestionar los roles operativos
    Cuando la Junta asigna Auditor a un residente
    Entonces el nuevo rol queda persistido y auditado

  Escenario: Revocación y restauración conservan el historial
    Cuando el SuperAdmin revoca y restaura el rol de un residente
    Entonces se conserva la asignación y sus vínculos
    Y el token anterior sigue revocado después de restaurar

  Escenario: Solicitudes idénticas son idempotentes
    Cuando se solicita dos veces el mismo cambio de rol
    Entonces se registra una sola modificación de permisos

  Escenario: El condominio limita la autoridad de Junta
    Cuando la Junta solicita cambiar un rol en otro condominio
    Entonces el cambio de rol se rechaza sin modificar la asignación

  Escenario: Roles de tenencia no son roles de autorización
    Cuando se intenta asignar Propietario como rol
    Entonces la API rechaza el cuerpo de rol inválido
