# Especificación del Dataset Semilla Piloto: Villa Bonita 3 (139 Departamentos)

## 1. Contexto del Condominio Piloto
- **Nombre:** Edificio 3 - Villa Bonita 3
- **Moneda:** Soles (PEN)
- **Total Unidades Inmobiliarias:** 139 departamentos
- **Distribución Física:**
  - 14 pisos habitacionales.
  - Pisos 1 al 13: 10 departamentos por piso (101 a 110, 201 a 210, ..., 1301 a 1310) = 130 departamentos.
  - Piso 14: 9 departamentos tipo penthouse/flat superior (1401 a 1409) = 9 departamentos.
  - Total = 139 departamentos.
- **Presupuesto Mensual Base:** S/ 20,850.00
- **Día de Corte:** 20 de cada mes
- **Días de Gracia:** 2 días calendario
- **Modalidad de Mora:** Monto fijo de S/ 20.00 por cuota vencida impaga tras vencer el periodo de gracia.

---

## 2. Distribución de Coeficientes de Participación (Alícuotas)

Para garantizar la exactitud contable ($\sum \text{Alícuotas} = 100.0000\%$):

| Tipología de Unidad | Cantidad | Metraje Promedio | Coeficiente Individual (%) | Subtotal Porcentual (%) | Cuota Mensual Aprox. |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Tipo A (Flat 2 Dorm)** | 65 dptos | 62.5 m² | `0.6800%` | `44.2000%` | S/ 141.78 |
| **Tipo B (Flat 3 Dorm)** | 65 dptos | 75.0 m² | `0.7400%` | `48.1000%` | S/ 154.29 |
| **Tipo C (Penthouse)** | 9 dptos | 110.0 m² | `0.8555%` | `7.6995%` | S/ 178.37 |
| **Ajuste Técnico Dpto 1409** | 1 dpto (1409) | 110.5 m² | `0.8560%` | `+0.0005%` (Ajuste) | S/ 178.48 |
| **TOTAL CONSOLIDADO** | **139 dptos** | - | **-** | **100.0000%** | **S/ 20,850.00** |

---

## 3. Catálogo de Áreas Comunes Piloto

| ID Simbólico | Nombre | Aforo Máximo | Costo de Reserva | Horarios Disponibles |
| :--- | :--- | :---: | :---: | :--- |
| `area-parrilla-1` | Zona de Parrillas 1 (Piso 15 Terraza) | 12 personas | S/ 25.00 | Turno Tarde: 12:00 - 16:00<br>Turno Noche: 18:00 - 22:00 |
| `area-parrilla-2` | Zona de Parrillas 2 (Piso 15 Terraza) | 12 personas | S/ 25.00 | Turno Tarde: 12:00 - 16:00<br>Turno Noche: 18:00 - 22:00 |
| `area-salon-eventos` | Salón Social de Eventos (Piso 1) | 40 personas | S/ 100.00 | Bloque único: 16:00 - 23:00 |
| `area-gimnasio` | Sala Fitness (Piso 1) | 8 personas | Gratuito | 06:00 a 22:00 (turnos de 1 hora) |

---

## 4. Perfiles y Departamentos de Prueba para Tests Automatizados

| Departamento | Propietario / Residente | Escenario de Prueba Asignado | Estado Inicial |
| :---: | :--- | :--- | :---: |
| **Dpto 101** | Juan Carlos Mendoza | Residente ejemplar: Siempre al día. Usado para pruebas de reservas exitosas. | `AL_DIA` |
| **Dpto 302** | María Fernández | Residente con saldo a favor preexistente de S/ 200.00. | `AL_DIA` (Saldo a Favor) |
| **Dpto 402** | Roberto Gómez | Residente moroso con cuota vencida anterior a la gracia. Bloqueado para reservas. | `EN_MORA` |
| **Dpto 504** | Lucía Paredes | Residente con comprobante reportado pendiente de conciliar (`EN_REVISION`). | `OBSERVADO` |
| **Administración** | Lic. Carlos Bustamante | Usuario con rol `ADMIN_JUNTA` para bandeja de conciliación y emisión de cuotas. | Rol Admin |
