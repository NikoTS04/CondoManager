/** Contrato de sesión v2: roles SQL y tenencia por unidad. */
export type UserRole = "SUPERADMIN" | "ADMIN_JUNTA" | "AUDITOR" | "RESIDENTE";
export type TipoRelacion = "PROPIETARIO_TITULAR" | "COPROPIETARIO" | "INQUILINO";

export interface DepartmentLink {
  departamento_id: string;
  numero: string;
  tipo_relacion: TipoRelacion;
  es_activo: boolean;
}

export interface SessionUser {
  id: string;
  email: string;
  nombre: string;
  apellido: string;
  rol: UserRole;
  condominio_id: string | null;
  departamentos: DepartmentLink[];
}

export const ROLE_LABELS: Record<UserRole, string> = {
  SUPERADMIN: "Superadministración",
  ADMIN_JUNTA: "Junta Directiva",
  AUDITOR: "Auditoría",
  RESIDENTE: "Residente",
};

export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isSessionUser(value: unknown): value is SessionUser {
  if (!value || typeof value !== "object") return false;
  const user = value as SessionUser;
  return [user.id, user.email, user.nombre, user.apellido].every((v) => typeof v === "string") &&
    Object.hasOwn(ROLE_LABELS, user.rol) &&
    ((user.rol === "SUPERADMIN" && user.condominio_id === null) || UUID_PATTERN.test(user.condominio_id || "")) &&
    Array.isArray(user.departamentos) && user.departamentos.every((link) =>
      link && UUID_PATTERN.test(link.departamento_id) && typeof link.numero === "string" &&
      ["PROPIETARIO_TITULAR", "COPROPIETARIO", "INQUILINO"].includes(link.tipo_relacion) &&
      typeof link.es_activo === "boolean"
    );
}

export function portalInicial(rol: UserRole): string {
  return rol === "RESIDENTE" ? "/residente" : "/junta";
}

export function seleccionarUnidad(
  user: SessionUser, solicitada?: string | null, anterior?: string | null, catalogo?: string[],
): string {
  const ids = user.rol === "RESIDENTE"
    ? user.departamentos.filter((v) => v.es_activo).map((v) => v.departamento_id)
      .filter((id) => !catalogo || catalogo.includes(id))
    : catalogo || [];
  return [solicitada, anterior].find((id): id is string => !!id && ids.includes(id)) || ids[0] || "";
}

export function etiquetaResidente(user: SessionUser, departamentoId: string): string {
  const relacion = user.departamentos.find((v) => v.es_activo && v.departamento_id === departamentoId)?.tipo_relacion;
  if (relacion === "INQUILINO") return "Inquilino";
  if (relacion === "COPROPIETARIO") return "Copropietario";
  return relacion === "PROPIETARIO_TITULAR" ? "Propietario" : "Residente";
}
