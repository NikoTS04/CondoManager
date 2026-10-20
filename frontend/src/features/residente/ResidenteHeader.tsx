"use client";

import { Search } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import type { Departamento } from "@/lib/api";
import type { UserProfile } from "@/context/AuthContext";

export interface ResidenteHeaderProps {
  depto: Departamento | null;
  departamentos: Departamento[];
  onSelectDepartamento: (numero: string) => void;
  user: UserProfile | null;
}

export function ResidenteHeader({
  depto,
  departamentos,
  onSelectDepartamento,
  user,
}: ResidenteHeaderProps) {
  const isJunta = user?.rol === "ADMIN_JUNTA" || user?.rol === "SUPERADMIN";

  const eyebrow = (
    <div className="flex flex-wrap items-center gap-2">
      {isJunta ? (
        <Badge tone="info">Soporte Junta Directiva</Badge>
      ) : user?.rol === "INQUILINO" ? (
        <Badge tone="neutral">Arrendatario Registrado</Badge>
      ) : (
        <Badge tone="success">Propietario Titular</Badge>
      )}
    </div>
  );

  const actions = (
    <div className="flex flex-wrap items-center gap-2">
      {isJunta ? (
        <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-line bg-surface p-1.5 shadow-xs">
          <span className="flex items-center gap-1 px-2 text-xs font-semibold text-muted">
            <Search className="h-3.5 w-3.5 text-info-600" aria-hidden />
            Cambiar depto:
          </span>
          <button
            type="button"
            onClick={() => onSelectDepartamento("102")}
            aria-pressed={depto?.numero === "102"}
            className={`min-h-9 min-w-[44px] rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              depto?.numero === "102"
                ? "bg-brand-600 text-white shadow-xs font-semibold"
                : "text-ink hover:bg-slate-100"
            }`}
          >
            102 (Al Día)
          </button>
          <button
            type="button"
            onClick={() => onSelectDepartamento("302")}
            aria-pressed={depto?.numero === "302"}
            className={`min-h-9 min-w-[44px] rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              depto?.numero === "302"
                ? "bg-brand-600 text-white shadow-xs font-semibold"
                : "text-ink hover:bg-slate-100"
            }`}
          >
            302 (Saldo +)
          </button>
          <button
            type="button"
            onClick={() => onSelectDepartamento("402")}
            aria-pressed={depto?.numero === "402"}
            className={`min-h-9 min-w-[44px] rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              depto?.numero === "402"
                ? "bg-danger-600 text-white shadow-xs font-semibold"
                : "text-danger-700 hover:bg-danger-50"
            }`}
          >
            402 (En Mora)
          </button>
        </div>
      ) : departamentos.length > 1 ? (
        <div className="flex items-center gap-2">
          <label htmlFor="selector-departamento" className="text-xs font-medium text-muted">
            Departamento:
          </label>
          <select
            id="selector-departamento"
            value={depto?.numero || ""}
            onChange={(e) => onSelectDepartamento(e.target.value)}
            className="min-h-11 rounded-lg border border-slate-300 bg-surface px-3 py-1.5 text-sm font-medium text-ink focus:border-brand-600 focus:outline-hidden"
          >
            {departamentos.map((d) => (
              <option key={d.numero} value={d.numero}>
                Dpto. {d.numero} (Piso {d.piso})
              </option>
            ))}
          </select>
        </div>
      ) : null}
    </div>
  );

  const title = depto
    ? `Portal del Residente · Dpto. ${depto.numero}`
    : "Portal del Residente";

  const description = depto
    ? `Piso ${depto.piso} · Alícuota: ${depto.coeficiente ? `${depto.coeficiente}%` : "No disponible"} · Villa Bonita 3`
    : "Consulta tus cuotas, comprobantes y reservas.";

  return (
    <PageHeader
      title={title}
      description={description}
      eyebrow={eyebrow}
      actions={actions}
      className="pb-2 border-b border-line"
    />
  );
}
