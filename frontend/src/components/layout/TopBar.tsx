"use client";

import Link from "next/link";
import { Building2, LogOut, Search, ShieldCheck, UserRound } from "lucide-react";
import { ROLE_LABELS, useAuth } from "@/context/AuthContext";
import DemoSwitcher from "@/components/layout/DemoSwitcher";

export default function TopBar() {
  const { user, logout, activeDepartment } = useAuth();
  const role = user?.rol;
  const resident = role && ["PROPIETARIO", "INQUILINO", "ADMIN_JUNTA", "SUPERADMIN"].includes(role);
  const junta = role && ["ADMIN_JUNTA", "SUPERADMIN", "AUDITOR"].includes(role);
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 font-semibold text-ink">
            <Building2 className="h-5 w-5 text-brand-600" aria-hidden />
            <span>CondoManager</span>
          </Link>
          <span className="hidden border-l border-line pl-3 text-sm text-muted sm:inline">
            Villa Bonita 3
          </span>
        </div>
        <nav aria-label="Portales" className="flex items-center gap-1">
          {resident && (
            <Link
              className="min-h-11 rounded-lg px-3 py-2 text-sm hover:bg-canvas"
              href={`/residente?dpto=${activeDepartment}`}
            >
              <UserRound className="mr-1 inline h-4 w-4" aria-hidden />
              Residente
            </Link>
          )}
          {junta && (
            <Link className="min-h-11 rounded-lg px-3 py-2 text-sm hover:bg-canvas" href="/junta">
              {role === "AUDITOR" ? (
                <Search className="mr-1 inline h-4 w-4" aria-hidden />
              ) : (
                <ShieldCheck className="mr-1 inline h-4 w-4" aria-hidden />
              )}
              {role === "AUDITOR" ? "Auditoría" : "Junta"}
            </Link>
          )}
        </nav>
        <div className="flex items-center gap-2">
          {user ? (
            <span className="hidden text-right text-xs sm:block">
              <span className="block font-medium text-ink">{user.nombre}</span>
              <span className="text-muted">{role ? ROLE_LABELS[role] : ""}</span>
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
      </div>
    </header>
  );
}
