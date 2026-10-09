import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("rounded-xl border border-line bg-surface shadow-sm", className)} {...props} />;
}

export interface CardHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
  /** Nivel de encabezado; por defecto h2. */
  as?: "h2" | "h3";
  className?: string;
}

export function CardHeader({ title, description, actions, icon, as: Heading = "h2", className }: CardHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3 border-b border-line px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-6",
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <span className="mt-0.5 shrink-0 text-muted" aria-hidden>
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <Heading className="text-base font-semibold text-ink">{title}</Heading>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-4 sm:px-6 sm:py-5", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-wrap items-center justify-end gap-2 border-t border-line px-4 py-3 sm:px-6", className)}
      {...props}
    />
  );
}
