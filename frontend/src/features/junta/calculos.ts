import { fromCents, isValidMoney, toCents } from "@/lib/money";

const ESCALA_COEFICIENTE = BigInt(10000);
const TOTAL_ALICUOTAS = BigInt(1000000);

/** Comprueba que los coeficientes con cuatro decimales sumen 100.0000 %. */
export function distribucionValida(coeficientes: string[]): boolean {
  if (coeficientes.length === 0) return false;
  if (coeficientes.some((coeficiente) => !/^\d+\.\d{4}$/.test(coeficiente))) return false;

  const suma = coeficientes.reduce((total, coeficiente) => {
    const [entero, decimales] = coeficiente.split(".");
    return total + BigInt(entero) * ESCALA_COEFICIENTE + BigInt(decimales);
  }, BigInt(0));

  return suma === TOTAL_ALICUOTAS;
}

/** Calcula la cuota en céntimos, redondeando la mitad hacia arriba. */
export function calcularCuota(total: string, coeficiente: string): string | null {
  if (!isValidMoney(total) || !/^\d+\.\d{4}$/.test(coeficiente)) return null;
  const montoCentimos = toCents(total);
  if (montoCentimos < BigInt(0)) return null;

  const [entero, decimales] = coeficiente.split(".");
  const unidadesCoeficiente = BigInt(entero) * ESCALA_COEFICIENTE + BigInt(decimales);
  const numerador = montoCentimos * unidadesCoeficiente;
  const centimosRedondeados = (numerador + TOTAL_ALICUOTAS / BigInt(2)) / TOTAL_ALICUOTAS;
  return fromCents(centimosRedondeados);
}
