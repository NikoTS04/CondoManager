import type { ReactNode } from "react";
import { CheckCircle2, Clock, Info, Minus, XCircle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type Tone = "success" | "warning" | "danger" | "info" | "audit" | "neutral";

const TONES: Record<Tone, string> = {
  success: "bg-success-50 text-success-800 border-success-200",
  warning: "bg-warning-50 text-warning-800 border-warning-200",
  danger: "bg-danger-50 text-danger-800 border-danger-200",
  info: "bg-info-50 text-info-800 border-info-200",
  audit: "bg-audit-50 text-audit-800 border-audit-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
};

const ICONS: Record<Tone, LucideIcon> = {
  success: CheckCircle2,
  warning: Clock,
  danger: XCircle,
  info: Info,
  audit: Info,
  neutral: Minus,
};

export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  /** Por defecto se muestra el icono del tono: el estado nunca se comunica solo con color. */
  icon?: LucideIcon | null;
  className?: string;
}

export function Badge({ tone = "neutral", children, icon, className }: BadgeProps) {
  const Icon = icon === null ? null : icon ?? ICONS[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
      {children}
    </span>
  );
}
