/**
 * Aritmética monetaria sobre strings decimales (DESIGN.md §5, ADR-002).
 * Nunca se usa `Number`/`float` para dinero: los importes se convierten a céntimos con BigInt.
 */

export type Moneda = "PEN" | "USD";

const ZERO = BigInt(0);
const CIEN = BigInt(100);

const MONEY_PATTERN = /^-?\d+(\.\d{1,2})?$/;

/** Indica si el texto es un importe válido con hasta dos decimales. */
export function isValidMoney(value: string): boolean {
  return MONEY_PATTERN.test(value.trim());
}

/** Convierte "1250.5" → 125050 céntimos. Lanza error si el formato no es válido. */
export function toCents(value: string): bigint {
  const clean = value.trim();
  if (!isValidMoney(clean)) {
    throw new Error(`Importe inválido: "${value}"`);
  }
  const negative = clean.startsWith("-");
  const [entero, decimales = ""] = clean.replace("-", "").split(".");
  const cents = BigInt(entero) * CIEN + BigInt(decimales.padEnd(2, "0"));
  return negative ? -cents : cents;
}

/** Convierte céntimos a string con dos decimales: 125050 → "1250.50". */
export function fromCents(cents: bigint): string {
  const negative = cents < ZERO;
  const abs = negative ? -cents : cents;
  const entero = abs / CIEN;
  const decimales = (abs % CIEN).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${entero.toString()}.${decimales}`;
}

/** Normaliza un importe a dos decimales: "20850" → "20850.00". */
export function normalizeMoney(value: string): string {
  return fromCents(toCents(value));
}

export function addMoney(...values: string[]): string {
  return fromCents(values.reduce((acc, v) => acc + toCents(v), ZERO));
}

export function subtractMoney(a: string, b: string): string {
  return fromCents(toCents(a) - toCents(b));
}

export function compareMoney(a: string, b: string): -1 | 0 | 1 {
  const diff = toCents(a) - toCents(b);
  return diff === ZERO ? 0 : diff > ZERO ? 1 : -1;
}

export function isPositiveMoney(value: string): boolean {
  return isValidMoney(value) && toCents(value) > ZERO;
}

const SYMBOL: Record<Moneda, string> = { PEN: "S/", USD: "US$" };

/** Formato de presentación: formatMoney("1250.5", "PEN") → "S/ 1,250.50". */
export function formatMoney(value: string | null | undefined, moneda: Moneda = "PEN"): string {
  if (value === null || value === undefined || !isValidMoney(String(value))) {
    return "—";
  }
  const normalized = normalizeMoney(String(value));
  const negative = normalized.startsWith("-");
  const [entero, decimales] = normalized.replace("-", "").split(".");
  const conMiles = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${SYMBOL[moneda]} ${conMiles}.${decimales}`;
}

/** Formato de coeficientes con 4 decimales: "0.72" → "0.7200 %". */
export function formatPercent(value: string | null | undefined): string {
  if (value === null || value === undefined || !/^-?\d+(\.\d+)?$/.test(String(value).trim())) {
    return "—";
  }
  const [entero, decimales = ""] = String(value).trim().split(".");
  return `${entero}.${decimales.padEnd(4, "0").slice(0, 4)} %`;
}
