"use client";

import { useId, useRef, useState, type DragEvent } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { cn } from "@/lib/cn";

export interface FileDropzoneProps {
  label: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  /** Tipos MIME aceptados. */
  accept?: string[];
  /** Tamaño máximo en MB (visible para el usuario). */
  maxSizeMb?: number;
  error?: string | null;
  required?: boolean;
}

const DEFAULT_ACCEPT = ["image/png", "image/jpeg", "application/pdf"];

/** Selección de voucher por botón o arrastre (no solo arrastre), con validación visible (DESIGN.md §6.1). */
export function FileDropzone({
  label,
  file,
  onFileChange,
  accept = DEFAULT_ACCEPT,
  maxSizeMb = 5,
  error,
  required,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const shownError = error || localError;

  function choose(selected: File | null) {
    setLocalError(null);
    if (!selected) return onFileChange(null);
    if (!accept.includes(selected.type)) {
      setLocalError("Formato no permitido. Usa PNG, JPG o PDF.");
      return;
    }
    if (selected.size > maxSizeMb * 1024 * 1024) {
      setLocalError(`El archivo supera el máximo de ${maxSizeMb} MB.`);
      return;
    }
    onFileChange(selected);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0] ?? null);
  }

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
        {required && (
          <span className="ml-0.5 text-danger-600" aria-hidden>
            *
          </span>
        )}
      </label>
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border border-line bg-slate-50 p-3">
          <FileText className="h-5 w-5 shrink-0 text-muted" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{file.name}</p>
            <p className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB</p>
          </div>
          <button
            type="button"
            onClick={() => {
              onFileChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="rounded-md p-1.5 text-muted hover:bg-slate-200 hover:text-ink"
            aria-label={`Quitar ${file.name}`}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : (
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors",
            dragging ? "border-brand-600 bg-brand-50" : shownError ? "border-danger-600" : "border-slate-300",
          )}
        >
          <UploadCloud className="h-7 w-7 text-slate-400" aria-hidden />
          <p className="text-sm text-muted">
            Arrastra el archivo aquí o{" "}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="font-semibold text-brand-700 underline-offset-2 hover:underline"
            >
              selecciónalo
            </button>
          </p>
          <p id={`${id}-hint`} className="text-xs text-muted">
            PNG, JPG o PDF · máximo {maxSizeMb} MB
          </p>
        </div>
      )}
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept.join(",")}
        required={required && !file}
        aria-describedby={`${id}-hint${shownError ? ` ${id}-error` : ""}`}
        aria-invalid={shownError ? true : undefined}
        onChange={(event) => choose(event.target.files?.[0] ?? null)}
        className="sr-only"
      />
      {shownError && (
        <p id={`${id}-error`} className="text-sm font-medium text-danger-700">
          {shownError}
        </p>
      )}
    </div>
  );
}
