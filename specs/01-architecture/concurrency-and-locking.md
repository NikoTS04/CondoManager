# Política de Concurrencia, Aislamiento y Bloqueo Pesimista (Concurrency & Locking)

## 1. Contexto del Problema

En un condominio de alta densidad como Villa Bonita 3 (139 departamentos), ocurren situaciones críticas de concurrencia:
1. **Reserva simultánea de áreas comunes:** Dos o más residentes intentan reservar la misma zona de parrilla o el salón de usos múltiples exactamente para el mismo sábado a las 20:00:00.
2. **Reporte y conciliación simultánea de pagos:** Un residente envía un comprobante de pago mientras el cron nocturno de moras está procesando el corte de cuentas.
3. **Cálculo masivo de cuotas con actualización concurrente de saldos a favor.**

Si no se implementa una estrategia estricta de aislamiento transaccional y bloqueo, el sistema incurriría en **reservas dobles (double booking)** o **actualizaciones perdidas (lost updates)**.

---

## 2. Nivel de Aislamiento en PostgreSQL

Todas las conexiones de base de datos en CondoManager operan bajo el nivel de aislamiento:
$$\mathbf{READ\ COMMITTED}\ \text{con Bloqueo Pesimista Explícito}$$

En reservas se bloquea primero el contexto financiero (condominio, departamento,
cuotas ordenadas por UUID) y luego la fila del área. El lock del área se conserva
hasta el commit de reserva, auditoría y outbox. Cancelaciones, cambios del catálogo
y bloqueos operativos respetan el mismo orden. No basta bloquear reservas
existentes: con un calendario vacío no habría ninguna fila que bloquear.

```sql
SELECT id FROM areas_comunes WHERE id = :area_id FOR UPDATE;

-- Después del lock estable se consultan las ocupaciones; intervalos [inicio, fin).
SELECT * FROM reservas 
WHERE area_id = :area_id 
  AND fecha_reserva = :fecha 
  AND NOT (hora_fin <= :hora_inicio OR hora_inicio >= :hora_fin)
  AND estado = 'CONFIRMADA'
FOR UPDATE;
```

---

## 3. Algoritmo de Reserva Atómica sin Condiciones de Carrera (Brandon - PROC-04)

```
[ Solicitud de Reserva Recibida ]
              │
              ▼
[ Iniciar Transacción ACID en PostgreSQL ]
              │
              ▼
[ 1. Verificar Solvencia Financiera del Departamento ]
  Bloquear condominio, departamento y cuotas ordenadas por UUID.
  Calcular deuda vencida real con la política de gracia de CON-42.
              │
      ┌───────┴───────┐
      ▼               ▼
(Tiene Deuda)     (Solvente)
      │               │
  ROLLBACK            ▼
  Retorna 403   [ 2. Bloquear Recurso Temporal con FOR UPDATE ]
  "DEUDA_MORA_ACTIVA"   SELECT id FROM areas_comunes
                   WHERE id = :area_id
                  FOR UPDATE;
                      │
              ┌───────┴───────┐
              ▼               ▼
        (Hay Conflicto)   (Horario Libre)
              │               │
          ROLLBACK            ▼
          Retorna 409   [ 3. Insertar Reserva 'CONFIRMADA' ]
          "HORARIO_NO_DISPONIBLE" │
                              ▼
                        [ 4. Registrar Auditoría, Outbox y COMMIT ]
                              │
                              ▼
                        [ Retornar 201 Created ]
```

---

## 4. Prevención de Interbloqueos (Deadlock Prevention)

Para evitar interbloqueos (*deadlocks*) cuando una transacción modifica múltiples registros contables (ej. conciliación que afecta 3 cuotas vencidas y 1 saldo a favor):
- **Regla de Ordenamiento Determinista:** Toda operación masiva debe ordenar los registros por su clave primaria (`id` ascendente) antes de emitir sentencias `UPDATE` o adquirir bloqueos `FOR UPDATE`.
- **Timeout Transaccional:** Todas las transacciones tienen un límite de espera de bloqueo configurado en PostgreSQL:
  ```sql
  SET statement_timeout = '5000ms';
  SET lock_timeout = '3000ms';
  ```
