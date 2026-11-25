# CON-53 — Reportar una incidencia

- **Reporte válido.** Dado un residente con vínculo activo, cuando envía un
  reporte completo sin foto, entonces el sistema devuelve el ID, persiste el
  estado `REGISTRADO` y encola un aviso por integrante activo de Junta del
  condominio.
- **Campos obligatorios.** Dado un formulario sin ubicación, cuando el residente
  intenta enviarlo, entonces ve el campo pendiente y conserva lo ingresado. La
  API rechaza la solicitud sin crear el ticket ni encolar el aviso.
- **Reintento.** Dado un reporte registrado, cuando se reenvía con la misma clave
  y datos, entonces recibe el mismo ID y se conservan un ticket y un aviso por
  destinatario.
- **Aislamiento.** Dado un reporte con foto, cuando un residente de otro
  condominio intenta consultar el ticket o la foto, entonces recibe 404.
- **Evidencia inválida.** Dado un reporte completo con una foto inválida,
  cuando se envía, entonces el archivo se rechaza, el reporte se conserva
  sin foto y se muestra el motivo en la confirmación.
