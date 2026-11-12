# ADR-003: Reparto común por pisos y reparto unitario equitativo

- Estado: aceptado para especificación; pendiente de implementación.
- Fecha: 2026-10-24.

## Contexto

El piloto comprende cuatro edificios (14, 14, 10 y 10 pisos). Los intentos de
reconstruir septiembre por departamentos no fueron tan cercanos como por pisos,
pero ninguna aproximación reproduce todas las filas. No hay padrón confirmado de
departamentos de los otros tres edificios; sí existe `total_pisos` en el catálogo.

## Decisión

Usar POR_PISOS para gastos comunes: peso exacto 14/48 o 10/48 según edificio.
Cerrar centavos por ítem sin truncar previamente los porcentajes. En edificio 03,
distribuir equitativamente entre sus 139 departamentos. Gastos exclusivos se
asignan directamente; excepciones explícitas requieren sustento y cierre exacto.

## Consecuencias

Regla simple, reproducible y trazable, sin inferir departamentos desconocidos.
Los pisos son una base operativa, no una prueba de consumo ni de coeficiente legal
de copropiedad. Su uso para futuras emisiones debe quedar ratificado en la
aprobación presupuestal. No ajustar porcentajes para disimular discrepancias ni
recalcular historia. Pesos y participantes se congelan por versión aprobada.

Detalle normativo: [prorrateo y mora diaria](../../02-domains/01-cuotas/prorrateo-y-mora-diaria.md).
