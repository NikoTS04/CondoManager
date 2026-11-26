# language: es
Característica: Directorio de Proveedores y Custodia de Contratos (CON-48, CON-49)
  Como integrante de la Junta Directiva
  Quiero gestionar el directorio de proveedores homologados y custodiar sus contratos con alertas preventivas
  Para transparentar las contrataciones, imputar egresos correctamente y anticipar renovaciones o licitaciones.

  Escenario: Registro exitoso de proveedor con RUC único por condominio
    Dado un condominio y un integrante de Junta autenticado
    Cuando registra un proveedor con RUC de 11 dígitos, razón social y datos de contacto
    Entonces el proveedor queda guardado como activo y con versión inicial 1
    Y aparece disponible en el directorio oficial del condominio

  Escenario: Rechazo de RUC duplicado dentro del mismo condominio
    Dado un proveedor existente con RUC "20551122334" en el condominio
    Cuando otro integrante intenta registrar un proveedor con el mismo RUC "20551122334"
    Entonces la solicitud es rechazada con código 409 PROVEEDOR_RUC_DUPLICADO
    Y no se duplica la entidad en el directorio

  Escenario: Registro de contrato y cálculo de alertas de vencimiento
    Dado un proveedor registrado en el directorio
    Cuando la Junta registra un contrato de servicio con fecha de inicio y fecha de fin a 45 días
    Entonces el contrato queda en estado POR_VENCER con alerta preventiva de 60 días
    Y muestra 45 días restantes para el vencimiento

  Escenario: Custodia digital y versionamiento inmutable de contratos PDF
    Dado un contrato vigente registrado en el sistema
    Cuando la Junta sube el documento PDF original firmado
    Entonces queda almacenado en el repositorio privado con versión 1
    Cuando posteriormente se sube una addenda en PDF indicando el motivo de reemplazo
    Entonces se genera la versión 2 del documento
    Y la versión 1 anterior se conserva intacta en el historial para auditoría

  Escenario: Restricción de permisos y aislamiento por rol
    Dado un usuario con rol AUDITOR en el condominio
    Cuando consulta el directorio de proveedores y contratos
    Entonces puede visualizar la información y descargar los documentos
    Cuando el auditor intenta registrar o modificar un proveedor
    Entonces la solicitud es rechazada con código 403 ACCESO_DENEGADO
