import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  /** Contenido sobre el título (p. ej. un Badge de contexto). */
  eyebrow?: ReactNode;
  className?: string;
}

/** Único h1 de cada página (DESIGN.md §4.2, §9). */
export function PageHeader({ title, description, actions, eyebrow, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0 space-y-1">
        {eyebrow}
        <h1 className="text-2xl font-bold tracking-tight text-ink lg:text-3xl">{title}</h1>
        {description && <p className="max-w-prose text-sm text-muted sm:text-base">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
