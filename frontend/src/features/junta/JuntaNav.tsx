"use client";

import {
  Bell,
  Building2,
  ClipboardCheck,
  Coins,
  FileCheck2,
  LayoutDashboard,
  Settings2,
  Clock3,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

export type JuntaSection =
  | "resumen"
  | "configuracion"
  | "estructura"
  | "presupuesto"
  | "cuotas"
  | "conciliacion"
  | "moras"
  | "comunicados";

const NAV_ITEMS = [
  { id: "resumen", label: "Resumen", Icon: LayoutDashboard },
  { id: "configuracion", label: "Configuración", Icon: Settings2, superAdmin: true },
  { id: "estructura", label: "Estructura", Icon: Building2 },
  { id: "presupuesto", label: "Presupuesto", Icon: ClipboardCheck },
  { id: "cuotas", label: "Distribución y emisión", Icon: Coins },
  { id: "conciliacion", label: "Conciliación", Icon: FileCheck2 },
  { id: "moras", label: "Moras", Icon: Clock3 },
  { id: "comunicados", label: "Comunicados", Icon: Bell },
] as const;

interface JuntaNavProps {
  section: JuntaSection;
  isSuperAdmin: boolean;
  pendientes: number;
  onNavigate: (section: JuntaSection) => void;
}

export function JuntaNav({ section, isSuperAdmin, pendientes, onNavigate }: JuntaNavProps) {
  const items = NAV_ITEMS.filter((item) => !("superAdmin" in item) || isSuperAdmin);

  return (
    <nav
      aria-label="Secciones de Junta"
      className="flex gap-2 overflow-x-auto pb-2 lg:block lg:space-y-1 lg:overflow-visible lg:pb-0"
    >
      {items.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          aria-current={section === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
          className={cn(
            "flex min-h-11 shrink-0 items-center gap-3 rounded-lg px-3",
            "text-sm font-medium transition-colors lg:w-full",
            section === id
              ? "bg-info-50 text-info-700"
              : "text-muted hover:bg-canvas hover:text-ink",
          )}
        >
          <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span>{label}</span>
          {id === "conciliacion" && pendientes > 0 && (
            <Badge tone="warning">{pendientes}</Badge>
          )}
        </button>
      ))}
    </nav>
  );
}

export const JUNTA_NAV_ITEMS = NAV_ITEMS;
