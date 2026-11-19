# Aceptación Hobby

Escenario: almacenamiento privado remoto
  Dada una evidencia autorizada
  Cuando se descarga desde Supabase Storage
  Entonces se devuelven bytes privados sin URL ni credencial
  Y los fallos remotos no producen éxito ni exponen detalles internos

Escenario: ejecución diaria protegida
  Cuando falta el secreto, es incorrecto o se trata de preview
  Entonces no se ejecuta ninguna operación
  Cuando otra ejecución mantiene el lock
  Entonces responde conflicto sin duplicar operaciones

Escenario: configuración de producción insegura
  Cuando hay debug, demo, JWT predeterminado o CORS abierto
  Entonces la aplicación rechaza la configuración al arrancar
