"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import type { Moneda } from "@/lib/money";

export interface MoneyInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
  /** Importe como string decimal; nunca como número (DESIGN.md §5). */
  value: string;
  onValueChange: (value: string) => void;
  moneda?: Moneda;
}

const SIMBOLO: Record<Moneda, string> = { PEN: "S/", USD: "US$" };

/** Entrada de importes: teclado decimal, acepta solo dígitos y hasta dos decimales. */
export const MoneyInput = forwardRef<HTMLInputElement, MoneyInputProps>(function MoneyInput(
  { value, onValueChange, moneda = "PEN", className, ...props },
  ref,
) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted" aria-hidden>
        {SIMBOLO[moneda]}
      </span>
      <input
        ref={ref}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={value}
        onChange={(event) => {
          const next = event.target.value.replace(",", ".");
          if (next === "" || /^\d*(\.\d{0,2})?$/.test(next)) onValueChange(next);
        }}
        className={cn(
          "block w-full rounded-lg border border-slate-300 bg-surface py-2.5 pl-11 pr-3 text-right text-base tabular-nums text-ink sm:text-sm",
          "disabled:cursor-not-allowed disabled:bg-slate-50 aria-[invalid=true]:border-danger-600",
          className,
        )}
        {...props}
      />
    </div>
  );
});
