# Arquitectura del Sistema - Visión General (System Overview)

## 1. Declaración de Propósito y Visión

**CondoManager** es una plataforma orientada a la automatización de procesos operativos, financieros y administrativos de comunidades residenciales (condominios, edificios multifamiliares y complejos habitacionales).

El sistema sustituye la gestión manual fragmentada (hojas de cálculo de Excel, transferencias bancarias/Yape validadas visualmente por WhatsApp, cálculo manual de moras y revisiones informales) por un **sistema guiado por eventos y reglas de negocio**, garantizando:
- Integridad y trazabilidad de los datos financieros.
- Imparcialidad y consistencia en la aplicación de penalidades y restricciones.
- Transparencia total para propietarios, inquilinos y juntas directivas.
- Continuidad operativa ante cambios de juntas directivas o personal administrativo.

---

## 2. Escalabilidad y Modelo Multi-Condominio / Multi-Edificio

El sistema se concibe bajo un diseño escalable:

```
[ Organización / Administradora ]
               │
               ▼
       [ Condominio ]  (Ej. "Villa Bonita 3", "Residencial Los Sauces", etc.)
               │
        ┌──────┴──────┐
        ▼             ▼
   [ Edificio A ] [ Edificio B ] (Cualquier número de torres o bloques)
        │
        ├─▶ [ Áreas Comunes ] (Parrillas, Salón Social, Gimnasio, etc.)
        │
        └─▶ [ Departamentos / Unidades ] (1 .. N departamentos)
                 │
                 ├─▶ [ Coeficiente de Participación / Alícuota ]
                 ├─▶ [ Propietario(s) ]
                 └─▶ [ Inquilino(s) ]
```

### Parámetros Dinámicos por Condominio
Cada condominio/edificio administra sus propias configuraciones sin cambios en el código:
- **Moneda de operación:** (PEN - Soles, USD - Dólares).
- **Mecanismo de distribución de cuotas:**
  - *Alícuota fija equitativa:* $\text{Cuota} = \frac{\text{Presupuesto Total}}{N \text{ unidades}}$
  - *Alícuota porcentual por metraje:* $\text{Cuota} = \text{Presupuesto Total} \times \% \text{ Participación}$
- **Parámetros de mora:** Días de corte, porcentaje o monto fijo de penalidad, periodo de gracia.
- **Reglas de reserva de áreas comunes:** Aforo máximo, costo de reserva, depósito de garantía, restricción por mora activa.

> **Caso Piloto:** Edificio 3 de Villa Bonita 3 (139 departamentos), utilizado como referencia empírica para pruebas de carga iniciales y validación de reglas de conciliación bancaria local (Yape, Plin y transferencias interbancarias CCI).

---

## 3. Principios de Diseño Arquitectónico

1. **Precisión Financiera Incondicional:**
   Todo cálculo contable (cuotas, recargos, prorrateos, saldos a favor) se realiza con tipos de datos de precisión decimal estricta (`Decimal(12, 2)` / `NUMERIC(12, 2)`), prohibiendo el uso de coma flotante (`float`) para evitar discrepancias por redondeo.
2. **Arquitectura Reactiva y Asíncrona (Event-Driven):**
   Las acciones del sistema se estructuran como reacciones a eventos del dominio (ej. `CuotaVencidaEvent`, `PagoRegistradoEvent`, `ReservaSolicitadaEvent`).
3. **Idempotencia Transaccional:**
   Ningún evento o reporte de pago puede generar duplicidad de transacciones. Toda operación de cobro o conciliación implementa claves de idempotencia basadas en el código de operación bancaria y fecha.
4. **Separación de Responsabilidades por Dominio (Clean / Modular Architecture):**
   El código se desacopla en módulos autónomos que reflejan los procesos del negocio, facilitando el trabajo colaborativo en paralelo entre los miembros del equipo.
5. **Gobernanza y Transparencia (Open Ledger):**
   Prohibición de eliminación física de registros contables (`DELETE`). Las correcciones se realizan exclusivamente mediante notas de crédito o ajustes compensatorios explícitos.

---

## 4. Stack Tecnológico Sugerido

Para satisfacer las demandas de rigurosidad contable, concurrencia y automatización de eventos:

| Capa | Tecnología | Justificación |
| :--- | :--- | :--- |
| **Backend Core** | **Python (FastAPI + Pydantic v2)** | Soporte nativo de `Decimal`, validación estricta de esquemas, alto rendimiento asíncrono para colas y webhooks. |
| **Base de Datos** | **PostgreSQL** | Integridad referencial ACID, tipos numéricos de alta precisión, soporte JSONB para payloads de auditoría y bloqueos pesimistas para reservas (`SELECT FOR UPDATE`). |
| **ORM & Migraciones** | **SQLAlchemy 2.0 (Async) + Alembic** | Mapeo objeto-relacional robusto, soporte para transacciones complejas y migraciones reproducibles en git. |
| **Motor de Tareas / Cron** | **Celery / ARQ / APScheduler + Redis** | Programación periódica para cálculo nocturno de vencimientos, reintentos de notificaciones y liberación de reservas expiradas. |
| **Frontend Web** | **TypeScript (React / Next.js / TailwindCSS)** | Tipado estricto para formularios de conciliación, paneles accesibles para residentes en dispositivos móviles y dashboards analíticos para la junta directiva. |

---

## 5. Módulos del Sistema y Flujo Global

```
                                  ┌────────────────────────┐
                                  │      RESIDENTE         │
                                  │ (Propietario/Inquilino)│
                                  └───────────┬────────────┘
                                              │
                     Registra Comprobante     │     Solicita Reserva
                     (Yape / Transferencia)   │     (Parrilla / Salón)
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ CONDIFY / CONDOMANAGER ENGINE                                                          │
│                                                                                        │
│   ┌────────────────────────┐                   ┌───────────────────────────────────┐   │
│   │   Módulo de Pagos      │                   │   Módulo de Reservas              │   │
│   │   (Tarqui)             │                   │   (Brandon)                       │   │
│   │                        │                   │                                   │   │
│   │ - Bandeja Conciliación │                   │ - Consulta disponibilidad         │   │
│   │ - Validación Comprob.  │                   │ - Validación cruzada con estado   │   │
│   │ - Actualiza Saldo Dpto │                   │   financiero del residente        │   │
│   └───────────┬────────────┘                   └─────────────────▲─────────────────┘   │
│               │                                                  │                     │
│               ▼ Emite Evento                                     │ Consulta Solvencia  │
│        [ PagoAprobadoEvent ]                                     │                     │
│               │                                                  │                     │
│               ├──────────────────────────────────────────────────┤                     │
│               ▼                                                  │                     │
│   ┌────────────────────────┐                   ┌─────────────────┴─────────────────┐   │
│   │ Módulo de Cuotas/Mora  │                   │   Módulo de Notificaciones        │   │
│   │ (Anderson)             │                   │   (Alejandro)                     │   │
│   │                        │                   │                                   │   │
│   │ - Emisión recurrente   │                   │ - Avisos de vencimiento           │   │
│   │ - Cálculo automático   │                   │ - Confirmación de conciliación    │   │
│   │   de mora al corte     │                   │ - Alerta de bloqueo/desbloqueo    │   │
│   └───────────┬────────────┘                   └───────────────────────────────────┘   │
│               │                                                                        │
│               ▼ Registra Transacción Inmutable                                         │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Bitácora de Auditoría y Libro Mayor (7 Campos Obligatorios)                     │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
