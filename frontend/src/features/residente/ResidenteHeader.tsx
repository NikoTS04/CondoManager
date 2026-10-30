"use client";

import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import type { Departamento } from "@/lib/api";
import type { UserProfile } from "@/context/AuthContext";
import { etiquetaResidente } from "@/lib/session";

export interface ResidenteHeaderProps {
  depto: Departamento | null;
  departamentos: Departamento[];
  onSelectDepartamento: (id: string) => void;
  user: UserProfile | null;
}

export function ResidenteHeader({ depto, departamentos, onSelectDepartamento, user }: ResidenteHeaderProps) {
  const isJunta = user?.rol === "ADMIN_JUNTA" || user?.rol === "SUPERADMIN";
  return (
    <PageHeader
      title={depto ? `Departamento ${depto.numero}` : "Tu departamento"}
      description={depto ? `${depto.edificio_nombre ? `${depto.edificio_nombre} · ` : ""}Piso ${depto.piso}` : "Consulta tu cuenta, reporta pagos y reserva espacios."}
      eyebrow={(
        <Badge tone={isJunta ? "info" : "neutral"}>
          {isJunta ? "Soporte Junta Directiva" : user ? etiquetaResidente(user, depto?.id || "") : "Residente"}
        </Badge>
      )}
      actions={departamentos.length > 1 ? (
        <div className="flex items-center gap-2">
          <label htmlFor="selector-departamento" className="text-xs font-medium text-muted">Departamento:</label>
          <select
            id="selector-departamento"
            value={depto?.id || ""}
            onChange={(e) => onSelectDepartamento(e.target.value)}
            className="min-h-11 rounded-lg border border-line bg-surface px-3 text-sm"
          >
            {departamentos.map((d) => <option key={d.id} value={d.id}>{d.edificio_nombre ? `${d.edificio_nombre} · ` : ""}Dpto. {d.numero} (Piso {d.piso})</option>)}
          </select>
        </div>
      ) : undefined}
      className="pb-2 border-b border-line"
    />
  );
}
