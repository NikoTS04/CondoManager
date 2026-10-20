# Política de Concurrencia, Aislamiento y Bloqueo Pesimista (Concurrency & Locking)

Contrato objetivo de integración: [CON-72](../05-api/sprint-2-contratos.md). La estrategia se implementa y coordina en CON-41/43/46/70/73; no se afirma que los routers piloto actuales ya utilicen estos bloqueos.

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

Bloquear solo reservas existentes no protege el primer intento sobre un intervalo vacío. Para reservas, serializar primero recursos persistentes en orden común: condominio, departamento y área; después consultar solapamientos. Creación y cancelación usan ese mismo orden. Cuando una operación afecta varias unidades o áreas, ordenarlas por UUID antes de bloquearlas.

Ejemplo del contrato SQL dentro de la transacción, con contexto y autorización ya comprobados y revalidados bajo lock:
```sql
SELECT id FROM condominios WHERE id = :condominio_id FOR UPDATE;
SELECT id FROM departamentos WHERE id = :departamento_id FOR UPDATE;
SELECT id FROM areas_comunes WHERE id = :area_id FOR UPDATE;
SELECT id FROM reservas
WHERE area_id = :area_id 
  AND fecha_reserva = :fecha 
  AND NOT (hora_fin <= :hora_inicio OR hora_inicio >= :hora_fin)
  AND estado = 'CONFIRMADA'
FOR UPDATE;
```

La fila de área existe aunque no haya reservas y es el recurso que protege ese caso. Una restricción de exclusión equivalente puede complementar esta garantía, coordinada con las migraciones de CON-73. Un mutex del proceso o una consulta de calendario sin bloqueo no la sustituye.

---

## 3. Algoritmo de Reserva Atómica sin Condiciones de Carrera (Brandon - PROC-04)

```
[ Solicitud de Reserva Recibida ]
              │
              ▼
[ Iniciar Transacción ACID en PostgreSQL ]
  Adquirir locks comunes de la sección 2 en orden y revalidar recursos.
              │
              ▼
[ 1. Verificar Solvencia Financiera del Departamento ]
  Leer cuotas/obligaciones persistidas de la unidad y calcular deuda vencida.
  No usar COUNT(*) con FOR SHARE ni considerar unidades desconocidas solventes.
              │
      ┌───────┴───────┐
      ▼               ▼
(Tiene Deuda)     (Solvente)
      │               │
  ROLLBACK            ▼
  Retorna 403   [ 2. Bloquear Recurso Temporal con FOR UPDATE ]
  "DEUDA_MORA_ACTIVA"   SELECT id FROM reservas
                  WHERE area_id = :area_id AND fecha_reserva = :fecha ...
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
                        [ 4. Registrar Auditoría y COMMIT ]
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
