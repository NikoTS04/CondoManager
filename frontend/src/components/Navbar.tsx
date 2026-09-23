"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, ShieldCheck, UserCheck, Bell, Activity } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 bg-slate-900 text-white shadow-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo y Condominio */}
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="p-2 bg-emerald-600 rounded-lg group-hover:bg-emerald-500 transition-colors">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <span className="text-xl font-black tracking-tight bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">
                  CondoManager
                </span>
                <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800 rounded-full">
                  Villa Bonita 3 • 139 Dptos
                </span>
              </div>
            </Link>
          </div>

          {/* Enlaces de Navegación */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              href="/"
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                pathname === "/"
                  ? "bg-slate-800 text-white"
                  : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
              }`}
            >
              General
            </Link>

            <Link
              href="/residente"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                pathname.startsWith("/residente")
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <UserCheck className="w-4 h-4" />
              <span>Portal Residente</span>
            </Link>

            <Link
              href="/junta"
              className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                pathname.startsWith("/junta")
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Junta Directiva</span>
            </Link>
          </nav>

          {/* Badge de Estado del Sistema */}
          <div className="hidden md:flex items-center gap-2 text-xs text-slate-400 bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>SDD Invariant Active</span>
          </div>
        </div>
      </div>
    </header>
  );
}
