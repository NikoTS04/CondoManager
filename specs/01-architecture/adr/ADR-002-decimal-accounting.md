# ADR-002: Obligatoriedad de Precisión Decimal Estricta en Operaciones Financieras

## Estado
**Aceptado** (Fecha: 2026-09-22)

## Contexto
El cálculo de cuotas de mantenimiento en condominios involucra prorrateos porcentuales basados en coeficientes de copropiedad (alícuotas). Por ejemplo, un departamento con coeficiente de `0.7194%` sobre un presupuesto de S/ 20,000.00 genera un valor teórico de `S/ 143.8800`.

En sistemas que emplean tipos de datos de coma flotante estándar (`float` o `double` basados en IEEE 754), ocurren errores sistemáticos de redondeo binario:
- `0.1 + 0.2 = 0.30000000000000004`
- Al sumar las cuotas de 139 departamentos calculadas con floats, la suma total difiere del presupuesto aprobado por varios centavos o soles, rompiendo el balance contable y provocando reclamos en asambleas de propietarios.

## Decisión
1. **Prohibición Total de `float`:** Queda terminantemente prohibido el uso del tipo nativo `float` de Python o `FLOAT/REAL/DOUBLE PRECISION` de SQL en cualquier campo o función vinculada a dinero, cuotas, saldos, porcentajes o penalidades.
2. **Uso Exclusivo de `decimal.Decimal` en Python:** Todo cálculo financiero debe utilizar la clase estándar `Decimal` con modo de redondeo `ROUND_HALF_UP` (redondeo bancario estándar al centavo más cercano).
3. **Uso de `NUMERIC(12, 2)` en PostgreSQL:** Todas las columnas monetarias en la base de datos se declaran como `NUMERIC(12, 2)`, y los coeficientes de alícuota como `NUMERIC(7, 4)`.
4. **Validación Automática en CI:** Se implementa una regla estática en `scripts/verify_sdd_compliance.py` que analiza el código fuente y rechaza cualquier Pull Request que contenga conversiones o literales `float` en los módulos de finanzas.

## Consecuencias
- **Positivas:** 
  - La suma de todas las cuotas emitidas coincide de forma exacta y determinista con el presupuesto.
  - Cero discrepancias en balances mensuales y liquidaciones ante auditorías.
- **Negativas / Mitigaciones:**
  - `Decimal` requiere instanciarse mediante cadenas de texto (ej. `Decimal("150.00")` en lugar de `Decimal(150.00)`). Se proveen funciones constructoras en `src/shared/decimal_types.py`.
