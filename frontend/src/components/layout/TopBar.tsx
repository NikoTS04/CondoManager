"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, LogOut, Search, ShieldCheck, UserRound } from "lucide-react";
import { ROLE_LABELS, useAuth } from "@/context/AuthContext";
import DemoSwitcher from "@/components/layout/DemoSwitcher";
import { etiquetaResidente } from "@/lib/session";

export default function TopBar() {
  const { user, logout, activeDepartment } = useAuth();
  const pathname = usePathname();
  const role = user?.rol;
  const resident = role && ["RESIDENTE", "ADMIN_JUNTA", "SUPERADMIN"].includes(role);
  const junta = role && ["ADMIN_JUNTA", "SUPERADMIN", "AUDITOR"].includes(role);
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 font-semibold text-ink">
            <Building2 className="h-5 w-5 text-brand-600" aria-hidden />
            <span>CondoManager</span>
          </Link>
        </div>
        {resident && junta && <nav aria-label="Portales" className="order-3 flex w-full items-center gap-1 sm:order-none sm:w-auto">
          {resident && (
            <Link
              className={`flex min-h-11 items-center rounded-lg px-3 py-2 text-sm ${pathname === "/residente" ? "bg-brand-50 font-semibold text-brand-800" : "hover:bg-canvas"}`}
              aria-current={pathname === "/residente" ? "page" : undefined}
              href={activeDepartment ? `/residente?dpto=${activeDepartment}` : "/residente"}
            >
              <UserRound className="mr-1 inline h-4 w-4" aria-hidden />
              Residente
            </Link>
          )}
          {junta && (
            <Link className={`flex min-h-11 items-center rounded-lg px-3 py-2 text-sm ${pathname === "/junta" ? "bg-brand-50 font-semibold text-brand-800" : "hover:bg-canvas"}`} aria-current={pathname === "/junta" ? "page" : undefined} href="/junta">
              {role === "AUDITOR" ? (
                <Search className="mr-1 inline h-4 w-4" aria-hidden />
              ) : (
                <ShieldCheck className="mr-1 inline h-4 w-4" aria-hidden />
              )}
              {role === "AUDITOR" ? "Auditoría" : "Junta"}
            </Link>
          )}
        </nav>}
        <div className="flex items-center gap-2">
          {user ? (
            <span className="text-right text-xs">
              <span className="block font-medium text-ink">{user.nombre}</span>
              <span className="text-muted">{role === "RESIDENTE" ? etiquetaResidente(user, activeDepartment) : role ? ROLE_LABELS[role] : ""}</span>
            </span>
          ) : (
            <Link href="/login" className="rounded-lg px-3 py-2 text-sm text-brand-700">
              Ingresar
            </Link>
          )}
          <DemoSwitcher />
          {user && (
            <button
              type="button"
              onClick={logout}
              aria-label="Cerrar sesión"
              className="flex h-11 w-11 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
            >
              <LogOut className="h-4 w-4" aria-hidden />
            </button>
          )}
        </div>
        {user && <p className="w-full break-all border-t border-line pt-2 text-xs text-muted">{user.condominio_id ? `Condominio · ${user.condominio_id}` : "Administración global · selecciona un condominio en Junta"}</p>}
      </div>
    </header>
  );
}
