"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { type CuentaUsuarioConRol, type RolContextual } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/session";

interface Props {
  usuario: CuentaUsuarioConRol;
  esSuperAdmin: boolean;
  esPropio: boolean;
  disabled: boolean;
  onGuardar: (rol: RolContextual) => void;
  onRevocar: () => void;
}

export function RolUsuarioEditor({ usuario, esSuperAdmin, esPropio, disabled, onGuardar, onRevocar }: Props) {
  const contextual = usuario.rol === "SUPERADMIN" ? "RESIDENTE" : usuario.rol;
  const [rol, setRol] = useState<RolContextual>(contextual);
  useEffect(() => setRol(contextual), [contextual]);
  const protegido = esPropio || usuario.es_superadmin || (!esSuperAdmin && !["AUDITOR", "RESIDENTE"].includes(usuario.rol));
  const nombre = `${usuario.nombre} ${usuario.apellido}`;

  return (
    <div className="min-w-56 space-y-2">
      <p className="font-medium">{usuario.es_superadmin ? "SuperAdmin global" : ROLE_LABELS[usuario.rol]}</p>
      <Badge tone={usuario.rol_activo ? "info" : "warning"}>{usuario.rol_activo ? "Rol vigente" : "Rol revocado"}</Badge>
      {protegido ? (
        <p className="text-xs text-muted">{esPropio ? "Tu asignación está protegida." : usuario.es_superadmin ? "Concesión global gestionada por CLI." : "Esta asignación la gestiona SuperAdmin."}</p>
      ) : (
        <>
          <Select aria-label={`Rol de ${nombre}`} value={rol} disabled={disabled} onChange={(event) => setRol(event.target.value as RolContextual)}>
            {esSuperAdmin && <option value="ADMIN_JUNTA">Admin / Junta</option>}
            <option value="AUDITOR">Auditor</option>
            <option value="RESIDENTE">Residente</option>
          </Select>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" disabled={disabled || (usuario.rol_activo && rol === usuario.rol)} onClick={() => onGuardar(rol)} aria-label={`${usuario.rol_activo ? "Guardar" : "Restaurar"} rol de ${nombre}`}>
              {usuario.rol_activo ? "Guardar rol" : "Restaurar rol"}
            </Button>
            {usuario.rol_activo && <Button size="sm" variant="ghost" disabled={disabled} onClick={onRevocar} aria-label={`Revocar rol de ${nombre}`}>Revocar rol</Button>}
          </div>
        </>
      )}
    </div>
  );
}
