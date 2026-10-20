"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type AlertTone = "success" | "warning" | "danger" | "info";

const STYLES: Record<AlertTone, { box: string; icon: LucideIcon; iconColor: string }> = {
  success: { box: "bg-success-50 border-success-200 text-success-800", icon: CheckCircle2, iconColor: "text-success-600" },
  warning: { box: "bg-warning-50 border-warning-200 text-warning-800", icon: AlertTriangle, iconColor: "text-warning-600" },
  danger: { box: "bg-danger-50 border-danger-200 text-danger-800", icon: XCircle, iconColor: "text-danger-600" },
  info: { box: "bg-info-50 border-info-200 text-info-800", icon: Info, iconColor: "text-info-600" },
};

export interface AlertProps {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  /** Código técnico del backend; se muestra como detalle secundario. */
  code?: string | null;
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
}

/** Mensaje en línea. Los errores usan role="alert"; el resto role="status" (DESIGN.md §9). */
export function Alert({ tone = "info", title, children, code, action, onDismiss, className }: AlertProps) {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;
  const { box, icon: Icon, iconColor } = STYLES[tone];

  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-lg border p-3 text-sm sm:p-4", box, className)}
    >
      <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", iconColor)} aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="leading-relaxed">{children}</div>}
        {code && <p className="text-xs opacity-75">Código: {code}</p>}
        {action && <div className="pt-1">{action}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={() => {
            setVisible(false);
            onDismiss();
          }}
          className="-m-1 h-8 w-8 shrink-0 rounded-md p-1.5 opacity-70 hover:opacity-100"
          aria-label="Cerrar mensaje"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
      )}
    </div>
  );
}
