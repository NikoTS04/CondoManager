import { cn } from "@/lib/cn";
import { formatMoney, type Moneda } from "@/lib/money";

export interface MoneyAmountProps {
  value: string;
  moneda?: Moneda;
  tone?: "success" | "warning" | "danger" | "info" | "neutral";
  className?: string;
}

const TONE_CLASSES = {
  success: "text-success-700",
  warning: "text-warning-700",
  danger: "text-danger-700",
  info: "text-info-700",
  neutral: "text-ink",
} as const;

export function MoneyAmount({ value, moneda = "PEN", tone = "neutral", className }: MoneyAmountProps) {
  return <span className={cn("tabular-nums", TONE_CLASSES[tone], className)}>{formatMoney(value, moneda)}</span>;
}
