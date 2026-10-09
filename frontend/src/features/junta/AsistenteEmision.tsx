interface AsistenteEmisionProps {
  paso: 1 | 2 | 3;
  presupuestoAprobado: boolean;
  distribucionAprobada: boolean;
}

const PASOS = ["Aprobar presupuesto", "Distribuir alícuotas", "Emitir cuotas"];

export function AsistenteEmision({
  paso,
  presupuestoAprobado,
  distribucionAprobada,
}: AsistenteEmisionProps) {
  return (
    <ol
      aria-label="Asistente de presupuesto y emisión"
      className="grid gap-2 sm:grid-cols-3"
    >
      {PASOS.map((label, index) => {
        const numero = (index + 1) as 1 | 2 | 3;
        const completado = numero === 1
          ? presupuestoAprobado
          : numero === 2 && distribucionAprobada;

        return (
          <li
            key={label}
            aria-current={numero === paso ? "step" : undefined}
            className={`rounded-xl border p-3 text-sm ${
              completado
                ? "border-success-200 bg-success-50 text-success-800"
                : numero === paso
                  ? "border-info-200 bg-info-50 text-info-800"
                  : "border-line bg-surface text-muted"
            }`}
          >
            <span className="font-semibold">Paso {numero}</span>
            <span className="ml-2">{label}</span>
            <span className="sr-only">
              {completado ? " — completado" : numero === paso ? " — actual" : " — pendiente"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
