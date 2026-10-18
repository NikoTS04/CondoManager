# language: es
Característica: Registro persistente de edificios y departamentos
  Como administrador de un condominio
  Quiero registrar e importar su estructura inmobiliaria
  Para operar con unidades identificadas por UUID

  Escenario: El número del departamento es único por edificio
    Dado un administrador con dos edificios en su condominio
    Cuando registra el departamento 101 en ambos edificios
    Entonces ambas unidades tienen UUID diferentes
    Y repetir el número en el primer edificio produce conflicto

  Escenario: Importación parcial reintentable
    Dado un administrador con dos edificios en su condominio
    Cuando importa un CSV con una unidad válida y otra con piso inválido
    Entonces se crea una unidad y se informa una fila inválida
    Y reintentar el archivo no duplica la unidad válida

  Escenario: Desactivación con conservación de la unidad
    Dado un administrador con dos edificios en su condominio
    Cuando registra y desactiva un departamento
    Entonces conserva su UUID y registra un único cambio de estado
