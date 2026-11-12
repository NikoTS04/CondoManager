"use client";

import { Calendar, CreditCard, Coins, Bell } from "lucide-react";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { cn } from "@/lib/cn";

export type ResidenteTab = "reservas" | "pagos" | "cuenta" | "avisos";

const TAB_ITEMS: TabItem<ResidenteTab>[] = [
  { id: "cuenta", label: "Resumen", icon: Coins },
  { id: "pagos", label: "Pagos", icon: CreditCard },
  { id: "reservas", label: "Reservas", icon: Calendar },
  { id: "avisos", label: "Avisos", icon: Bell },
];

export interface ResidenteNavProps {
  activeTab: ResidenteTab;
  onChangeTab: (tab: ResidenteTab) => void;
  className?: string;
}

export function ResidenteNav({ activeTab, onChangeTab, className }: ResidenteNavProps) {
  return (
    <>
      {/* Navegación superior para sm y pantallas mayores usando el componente Tabs */}
      <div className={cn("hidden sm:block", className)}>
        <Tabs<ResidenteTab>
          items={TAB_ITEMS}
          value={activeTab}
          onChange={onChangeTab}
          idPrefix="residente"
          label="Secciones del portal del residente"
        />
      </div>

      {/* Barra inferior fija para móvil (bottom tab bar, ítems ≥44px con aria-current) */}
      <nav
        aria-label="Navegación móvil del residente"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface shadow-lg sm:hidden pb-[env(safe-area-inset-bottom)]"
      >
        <div className="grid grid-cols-4">
          {TAB_ITEMS.map((item) => {
            const isSelected = activeTab === item.id;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                aria-current={isSelected ? "page" : undefined}
                onClick={() => onChangeTab(item.id)}
                className={cn(
                  "flex min-h-[48px] flex-col items-center justify-center gap-1 py-2 px-1 text-xs transition-colors",
                  isSelected
                    ? "font-semibold text-brand-700 bg-brand-50/50"
                    : "text-muted hover:text-ink active:bg-slate-100",
                )}
              >
                {Icon && <Icon className={cn("h-5 w-5 shrink-0", isSelected ? "text-brand-700" : "text-muted")} aria-hidden />}
                <span className="truncate max-w-full text-[11px] leading-tight text-center">
                    {item.label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
}
