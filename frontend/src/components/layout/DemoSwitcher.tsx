"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { DEMO_PERSONAS, useAuth } from "@/context/AuthContext";

export default function DemoSwitcher() {
  const { user, switchDemoPersona } = useAuth();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstOption = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    trigger.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    firstOption.current?.focus();

    const handleOutsideClick = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, close]);

  if (process.env.NEXT_PUBLIC_DEMO_MODE === "false") return null;

  return (
    <div className="relative" ref={root}>
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-controls="demo-switcher-options"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-line bg-surface px-3 text-sm text-ink hover:bg-canvas"
      >
        Demos
        <ChevronDown className="h-4 w-4" aria-hidden />
      </button>
      {open && (
        <div
          id="demo-switcher-options"
          className="absolute right-0 z-50 mt-2 max-h-[70vh] w-72 overflow-auto rounded-xl border border-line bg-surface p-1 shadow-lg"
        >
          {DEMO_PERSONAS.map((persona, index) => (
            <button
              ref={index === 0 ? firstOption : undefined}
              type="button"
              key={persona.key}
              onClick={() => {
                void switchDemoPersona(persona.key);
                close();
              }}
              className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-canvas focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
            >
              <span className="block font-medium">
                {persona.label}{user?.email === persona.email ? " · Activo" : ""}
              </span>
              <span className="text-xs text-muted">{persona.email}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
