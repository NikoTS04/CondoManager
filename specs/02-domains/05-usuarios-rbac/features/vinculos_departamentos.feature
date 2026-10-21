# language: es
Característica: Vínculos persistentes con departamentos CON-05
  Antecedentes:
    Dado una administración y usuarios con unidades reales para vincular

  Escenario: Vincular varias unidades con relaciones distintas
    Cuando la administración registra un titular y un inquilino con varias unidades
    Entonces el nuevo login representa las relaciones mixtas persistidas
    Y el portal devuelve únicamente sus unidades activas reales

  Escenario: No se retira al último titular
    Cuando la administración intenta desactivar al último titular
    Entonces la API exige un titular sin modificar el vínculo

  Escenario: Onboarding exige titular antes de un inquilino
    Cuando se intenta registrar un inquilino en una unidad sin titular
    Entonces la API exige un titular sin crear el vínculo

  Escenario: Revocar un inquilino retira el acceso
    Cuando la administración revoca el vínculo de un inquilino
    Entonces la sesión anterior queda revocada por el cambio de vínculo
    Y un nuevo login no permite operar sobre la unidad desvinculada

  Escenario: El auditor no administra tenencia
    Cuando un Auditor intenta vincular un usuario
    Entonces la API rechaza la vinculación por falta de permisos

  Escenario: No se vinculan departamentos de otro condominio
    Cuando se intenta vincular una unidad de otro condominio
    Entonces la API no encuentra la unidad en el contexto solicitado

  Escenario: El vínculo repetido es idempotente
    Cuando se solicita dos veces el mismo vínculo
    Entonces existe una sola relación y un solo cambio auditado
