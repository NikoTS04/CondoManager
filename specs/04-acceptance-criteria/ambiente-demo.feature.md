# CON-81 — ambiente compartido Supabase y recuperación

```gherkin
Característica: Ambiente reproducible sin alterar datos operativos
  Escenario: Liveness no sustituye readiness
    Dado que la API responde pero PostgreSQL no está disponible
    Cuando se consulta /api/v1/health
    Entonces responde 200 sin consultar la base
    Cuando se consulta /api/v1/ready
    Entonces responde 503 sin exponer secretos ni detalles SQL

  Escenario: Revisión y esquema verificables
    Dado PostgreSQL con las migraciones del artefacto desplegado
    Cuando se consulta /api/v1/ready
    Entonces responde 200 con la revisión instalada
    Pero si falta una tabla o columna requerida o difiere la revisión
    Entonces responde 503 y no declara listo el ambiente

  Escenario: Instalación limpia y actualización soportada
    Dado PostgreSQL exclusivo de pruebas
    Cuando se migra desde cero o desde la revisión soportada hasta head
    Entonces existe una sola cabeza y las lecturas autenticadas funcionan
    Y ejecutar dos veces los seeds conserva identidades y datos existentes

  Escenario: Restauración separada
    Dado un respaldo consistente de PostgreSQL y archivos privados con workers detenidos
    Cuando se restaura en una base y directorio vacíos de ensayo
    Entonces las referencias SQL recuperan sus archivos originales
    Y los accesos autenticados conservan su aislamiento
    Y los pendientes se recuperan sin duplicar efectos
    Y los intentos de aceptación incierta no se reenvían ciegamente
    Y no se alteran los datos de Supabase para ejecutar el ensayo
```
