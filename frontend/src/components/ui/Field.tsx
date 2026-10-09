"use client";

import {
  cloneElement,
  forwardRef,
  isValidElement,
  useId,
  type InputHTMLAttributes,
  type ReactElement,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

const CONTROL =
  "block w-full rounded-lg border bg-surface px-3 py-2.5 text-base text-ink placeholder:text-slate-400 sm:text-sm " +
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 aria-[invalid=true]:border-danger-600";

const controlBorder = "border-slate-300";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cn(CONTROL, controlBorder, className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select ref={ref} className={cn(CONTROL, controlBorder, "pr-8", className)} {...props}>
      {children}
    </select>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(CONTROL, controlBorder, "min-h-24", className)} {...props} />;
  },
);

export interface FieldProps {
  label: string;
  /** Un único control (Input, Select, Textarea, MoneyInput...). Recibe id y atributos ARIA. */
  children: ReactElement;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
}

/**
 * Asocia etiqueta, ayuda y error a un control (DESIGN.md §6.1, §9).
 * Inyecta `id`, `aria-describedby`, `aria-invalid` y `required` en el hijo.
 */
export function Field({ label, children, hint, error, required, className }: FieldProps) {
  const generatedId = useId();
  const child = isValidElement<Record<string, unknown>>(children) ? children : null;
  const id = (child?.props.id as string | undefined) ?? generatedId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
        {required && (
          <span className="ml-0.5 text-danger-600" aria-hidden>
            *
          </span>
        )}
      </label>
      {child &&
        cloneElement(child, {
          id,
          required: required || child.props.required,
          "aria-describedby": describedBy,
          "aria-invalid": error ? true : undefined,
        })}
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm font-medium text-danger-700">
          {error}
        </p>
      )}
    </div>
  );
}
