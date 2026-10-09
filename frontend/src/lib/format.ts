/** Formato de fechas y periodos en la zona horaria del condominio (DESIGN.md §5). */

export { formatMoney, formatPercent } from "@/lib/money";

const TIME_ZONE = "America/Lima";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

/** "2026-10-08" o ISO completo → "08 oct 2026". Las fechas sin hora no se desplazan por zona horaria. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const soloFecha = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = new Date(soloFecha ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-PE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: soloFecha ? "UTC" : TIME_ZONE,
  })
    .format(date)
    .replace(".", "");
}

/** ISO → "08 oct 2026, 14:30". */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-PE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  })
    .format(date)
    .replace(".", "");
}

/** "2026-10" → "Octubre 2026". */
export function formatPeriodo(periodo: string | null | undefined): string {
  if (!periodo) return "—";
  const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(periodo);
  if (!match) return periodo;
  return `${MESES[Number(match[2]) - 1]} ${match[1]}`;
}

/** "19:00:00" → "19:00". */
export function formatHora(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 5);
}
