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
  Users,
  CalendarDays,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

export type JuntaSection =
  | "resumen"
  | "configuracion"
  | "estructura"
  | "usuarios"
  | "areas"
  | "presupuesto"
  | "cuotas"
  | "conciliacion"
  | "moras"
  | "comunicados";

const NAV_ITEMS = [
  { id: "resumen", label: "Resumen", Icon: LayoutDashboard },
  { id: "configuracion", label: "Configuración", Icon: Settings2, superAdmin: true },
  { id: "estructura", label: "Estructura", Icon: Building2 },
  { id: "usuarios", label: "Usuarios", Icon: Users, administracion: true },
  { id: "areas", label: "Áreas comunes", Icon: CalendarDays },
  { id: "presupuesto", label: "Presupuesto", Icon: ClipboardCheck },
  { id: "cuotas", label: "Distribución y emisión", Icon: Coins },
  { id: "conciliacion", label: "Conciliación", Icon: FileCheck2 },
  { id: "moras", label: "Moras", Icon: Clock3 },
  { id: "comunicados", label: "Comunicados", Icon: Bell },
] as const;

interface JuntaNavProps {
  section: JuntaSection;
  isSuperAdmin: boolean;
  isAuditor: boolean;
  pendientes: number;
  onNavigate: (section: JuntaSection) => void;
}

export function JuntaNav({ section, isSuperAdmin, isAuditor, pendientes, onNavigate }: JuntaNavProps) {
  const items = NAV_ITEMS.filter((item) => (!("superAdmin" in item) || isSuperAdmin) && (!("administracion" in item) || !isAuditor));

  return (
    <nav
      aria-label="Secciones de Junta"
      className="flex gap-2 overflow-x-auto pb-2 md:block md:space-y-1 md:overflow-visible md:pb-0"
    >
      {items.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          aria-current={section === id ? "page" : undefined}
          aria-label={label}
          title={label}
          onClick={() => onNavigate(id)}
          className={cn(
            "flex min-h-11 shrink-0 items-center gap-3 rounded-lg px-3",
            "text-left text-sm font-medium transition-colors duration-150 md:w-full md:justify-center md:px-2 lg:justify-start lg:px-3",
            (id === "presupuesto" || id === "comunicados") && "md:!mt-5",
            section === id
              ? "bg-brand-50 text-brand-800"
              : "text-muted hover:bg-canvas hover:text-ink",
          )}
        >
          <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span className="md:hidden lg:inline">{label}</span>
          {id === "conciliacion" && pendientes > 0 && (
            <span className="md:hidden lg:inline"><Badge tone="warning">{pendientes}</Badge></span>
          )}
        </button>
      ))}
    </nav>
  );
}

export const JUNTA_NAV_ITEMS = NAV_ITEMS;
