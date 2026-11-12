# language: es
Característica: Catálogo persistente de áreas comunes CON-39
  Antecedentes:
    Dado un condominio y una administración persistentes para áreas

  Escenario: Crear y consultar un área real
    Cuando la administración crea un área con costo y horarios
    Entonces el residente consulta sus condiciones desde el catálogo SQL

  Escenario: Auditor solo consulta
    Cuando un Auditor intenta crear un área
    Entonces la API rechaza la escritura del catálogo

  Escenario: Aislamiento por condominio
    Cuando una Junta intenta consultar el catálogo de otro condominio
    Entonces la API rechaza la operación ajena

  Escenario: Desactivar conserva el área y bloquea nuevas reservas
    Cuando se desactiva un área registrada
    Entonces desaparece del catálogo activo pero conserva su registro administrativo
    Y una nueva reserva en esa área es rechazada

  Escenario: Límites de horario y duración
    Cuando se solicita un turno fuera del horario permitido
    Entonces la API rechaza el turno sin ocupar el calendario

  Escenario: La configuración repetida es idempotente
    Cuando la administración repite la configuración del área
    Entonces solo el alta queda registrada en auditoría
