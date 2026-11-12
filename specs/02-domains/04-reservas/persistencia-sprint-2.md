# CON-73/74 — Persistencia e integración del prototipo

Antecedente implementado. La [ampliación financiera](../01-cuotas/prorrateo-y-mora-diaria.md)
requiere adaptar el guard a fecha Lima y gracia efectiva histórica por cuota,
default 0. Esta adaptación está especificada, no acreditada por CON-73/74.

Nicolás, 20/10/2026. Se conserva el catálogo SQL de CON-39 y la solvencia de
CON-42/70. El rediseño visual no forma parte de esta entrega.

## Transacciones y calendario

- Crear usa la sesión de `SolvenciaService.para_reserva`: condominio,
  departamento y cuotas bloqueados antes del área. Cancelar toma el mismo orden.
  El lock de la fila del área existe incluso con calendario vacío; se mantiene
  hasta confirmar reserva, auditoría encadenada y outbox. No basta bloquear
  reservas existentes. Bloqueos operativos siguen el mismo protocolo.
- Disponibilidad lee reservas confirmadas y bloqueos activos, convierte sus
  instantes a America/Lima y fusiona intervalos semiabiertos. No devuelve datos
  personales. Fechas pasadas se rechazan; las nuevas reservas no pueden iniciar
  en el pasado ni cruzar medianoche.
- Las reservas anteriores sin zona son UTC. La migración conserva fecha/hora y
  tarifa, completa moneda desde el condominio y no inventa un actor histórico.
  Nuevas reservas conservan moneda, zona y actor. Adoptar un esquema incompatible
  falla sin borrar tablas ni registros. Downgrade con datos se rechaza.
- Cancelación repetida devuelve fecha/resultado originales sin otro evento.
  La frontera voluntaria es `inicio - ahora >= 24 horas`; es_admin del cliente
  no concede permisos. Sin un cobro efectivo asociado el ajuste es NO_APLICA,
  monto 0.00: una tarifa no demuestra un pago. El prototipo no registra cobros
  de reservas; incorporar ese productor exige integrar la compensación antes
  de habilitarlo.

## Notificaciones y recuperación

- PostgreSQL guarda aviso, identidad destinataria, evento y operación de origen,
  canal, transporte, ciclo, intentos, próxima ejecución y referencia externa.
  La unicidad lógica es evento/operación/usuario/canal. Los contactos proceden
  de usuarios activos con vínculo y rol contextual activos, nunca del padrón demo.
- Consumir registra evento y avisos en una transacción, con exclusión SQL del
  event_id. Solo después se confirma el mensaje de Redis. Se recuperan mensajes
  pendientes de consumidores caídos. Versiones desconocidas o eventos inválidos
  quedan como incidencias SQL sin almacenar contactos ni contenido del voucher.
  El worker recupera además outboxes aún no consumidos sin depender de Redis;
  un marcador separado de descarte evita reintentar copias SQL inválidas sin fin.
- Se conservan los productores existentes de cuotas y pagos, incluido el
  envelope histórico `version: 1` de Anderson. No se cambian eventos persistidos.
- Un worker adquiere cada aviso con FOR UPDATE SKIP LOCKED. El transporte del
  prototipo es SIMULADO: aceptación da ENVIADO, nunca ENTREGADO. El proveedor real
  y su confirmación autenticada siguen a cargo del módulo de Alejandro.
- Cada intento efectivo queda en el historial. Inicial más tres reintentos:
  2 minutos (jitter ±15 s), 10 y 30 minutos desde el fallo. Programar no incrementa
  intentos. Caída durante envío mantiene evidencia del intento incierto; no se
  reenvía automáticamente a un proveedor sin reconciliar. ENVIADO/ENTREGADO no
  se reenvían. Nuevo ciclo manual solo con contacto autorizado corregido.
- Residente consulta exclusivamente avisos destinados a su identidad y unidad
  activamente vinculada; administración/auditor consultan su condominio.

## Integración y evidencia

La UI conserva componentes y estilos actuales. Consume los uploads y resultados
reales de CON-70, incorpora avisos y conserva errores estructurados. Las pruebas
incluyen rollback, sesiones independientes, reinicio, diez reservas concurrentes,
consumo duplicado, workers concurrentes y límites temporales. No se acredita
entrega física usando el transporte simulado.
