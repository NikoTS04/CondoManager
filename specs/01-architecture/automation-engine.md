# Arquitectura del Motor de Automatizaciones (Automation Engine)

## 1. El Ciclo de Automatización

Todo proceso rutinario en **CondoManager** se rige por un pipeline determinista de 5 fases:

$$\mathbf{Evento} \longrightarrow \mathbf{Evaluaci\acute{o}n\ de\ Reglas} \longrightarrow \mathbf{Decisi\acute{o}n} \longrightarrow \mathbf{Acci\acute{o}n} \longrightarrow \mathbf{Verificaci\acute{o}n}$$

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│  EVENTO  │ ──▶ │  EVALUACIÓN  │ ──▶ │ DECISIÓN │ ──▶ │  ACCIÓN  │ ──▶ │ VERIFICACIÓN │
└──────────┘     │  DE REGLAS   │     └──────────┘     └──────────┘     └──────────────┘
                 └──────────────┘                                              │
                        ▲                                                      │
                        └─────────────── Reintento si Falla ───────────────────┘
```

---

## 2. Definición Detallada de las Fases

### Fase 1: Evento (Detection / Trigger)
El suceso que despierta el proceso. Puede originarse por:
1. **Temporizadores / Crons (Time-based):** 
   - Llegada de fecha de emisión de cuota (ej. día 1 de cada mes a las 00:00).
    - Vencimiento de cuota el día 10 a las 23:59:59 de Lima; gracia efectiva default 0.
   - Alerta preventiva de vencimiento (ej. 3 días antes de la fecha límite).
   - Vencimiento de contrato de proveedor (30 o 60 días antes).
2. **Acciones de Usuario (User-initiated):**
   - Residente reporta un comprobante de pago por Yape o transferencia bancaria.
   - Administrador aprueba o rechaza un comprobante en la bandeja de conciliación.
   - Residente solicita reservar un área común para una fecha y bloque horario.
3. **Webhooks / Eventos del Sistema (Internal Events):**
   - Publicación de `PagoConciliadoEvent` o `CuotaMoraAplicadaEvent`.

### Fase 2: Evaluación de Reglas (Rule Evaluation)
El motor carga el contexto del condominio y evalúa las políticas vigentes:
- ¿El departamento tiene saldo pendiente anterior?
- ¿Se superó el periodo de gracia configurado para este edificio?
- ¿El comprobante de pago tiene un código de operación ya registrado (control de duplicados)?
- ¿El área común solicitada está disponible y el residente está al día con sus obligaciones?

### Fase 3: Decisión (Decision Making)
El motor determina el camino lógico según las reglas evaluadas:
- **Aprobar:** Ejecutar la acción estándar (ej. marcar cuota como pagada y habilitar reservas).
- **Rechazar:** Denegar la operación con motivo explícito (ej. denegar reserva por mora activa).
- **Escalar a Humano:** Enviar a la bandeja del Administrador si se detecta discrepancia (ej. pago parcial o voucher dudoso).

### Fase 4: Acción (Action Execution)
Ejecución de cambios en el estado del sistema y llamadas a servicios:
- Actualización transaccional en la base de datos (estados, saldos, moras).
- Emisión de notificaciones (correo electrónico, mensajes automáticos).
- Registro inmutable en la bitácora de auditoría.

### Fase 5: Verificación (Verification & Assertion)
El motor comprueba que la acción produjo el resultado esperado:
- ¿El balance del departamento concuerda con la suma algebraica de cargos y abonos?
- ¿El proveedor de mensajería confirmó la recepción del mensaje o retornó error?
- Si la verificación falla:
  - Se ejecuta la política de reintentos exponenciales.
  - Si los reintentos se agotan, se emite una **Alerta Crítica al Administrador** y se detiene la propagación de estados inconsistentes.

---

## 3. Topología de Componentes del Motor

```
[ FastAPI Backend ] ────────▶ [ Redis Queue / Broker ]
        │                               │
        │ Eventos                       ▼
        │                      [ Celery / ARQ Workers ]
        ▼                               │
[ Base de Datos PostgreSQL ] ◀──────────┘
  (Transacciones ACID +                   - Evalúa Reglas de Negocio
   Bloqueo Pesimista)                     - Ejecuta Notificaciones
                                          - Monitorea Vencimientos Diarios
```

### Componentes Clave:
1. **Event Dispatcher (Dispatcher de Eventos):** Desacopla las llamadas HTTP de los procesos pesados. Cuando un residente envía un pago, la API responde inmediatamente con código `202 Accepted` y delega la validación asíncrona al worker.
2. **Scheduler (Planificador de Tareas Recurrentes):** Ejecuta revisiones cronometradas periódicas (cada hora o una vez al día) para evaluar fechas de corte, moras y expiración de reservas pendientes.
3. **Idempotency Manager:** Valida tokens de idempotencia únicos generados por combinación de hash (`sha256(edificio_id + banco + nro_operacion + monto)`).

---

## 4. Ejemplo Aplicado: Ciclo de Corte y Mora

| Paso | Ejecución |
| :--- | :--- |
| **1. Evento** | Cron diario a las 00:05 de America/Lima dispara `EvaluarVencimientosDiariosJob`; recupera fechas omitidas. |
| **2. Evaluación** | Busca principal impago después de vencimiento + gracia histórica efectiva, incluso cuotas EN_MORA. Usa fecha bancaria validada para pagos. |
| **3. Decisión** | Por cuota y día exigible genera importe diario editable (default 1.00 PEN), sin duplicar `(cuota_id, fecha_local)` ni capitalizar. Pausa de revisión no condona días. |
| **4. Acción** | 1. Genera cargo de mora en estado de cuenta. <br>2. Cambia estado del dpto a `MOROSO`. <br>3. Dispara orden de notificación de mora a Alejandro. <br>4. Inhabilita al departamento para reservar áreas comunes. |
| **5. Verificación** | Valida que el saldo total actualizado coincida con `saldo_anterior + mora`. Confirma registro en la bitácora inmutable. |
