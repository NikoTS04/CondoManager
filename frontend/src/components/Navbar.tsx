"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, DEMO_PERSONAS } from "@/context/AuthContext";
import {
  Building2,
  ShieldCheck,
  UserCheck,
  Search,
  LogOut,
  ChevronDown,
  User,
  Lock,
} from "lucide-react";
import { useState } from "react";

export default function Navbar() {
  const pathname = usePathname();
  const { user, switchDemoPersona, logout, activeDepartment } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const canAccessJunta = user && ["ADMIN_JUNTA", "SUPERADMIN", "AUDITOR"].includes(user.rol);
  const canAccessResidente = user && ["PROPIETARIO", "INQUILINO", "ADMIN_JUNTA", "SUPERADMIN"].includes(user.rol);

  return (
    <header className="sticky top-0 z-50 bg-slate-900 text-white shadow-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo y Condominio */}
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="p-2 bg-emerald-600 rounded-lg group-hover:bg-emerald-500 transition-colors">
                <Building2 className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="text-xl font-black tracking-tight bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">
                  CondoManager
                </span>
                <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800 rounded-full">
                  Villa Bonita 3
                </span>
              </div>
            </Link>
          </div>

          {/* Enlaces de Navegación adaptados por Rol */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              href="/"
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                pathname === "/"
                  ? "bg-slate-800 text-white"
                  : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
              }`}
            >
              Inicio
            </Link>

            {canAccessResidente && (
              <Link
                href={`/residente?dpto=${activeDepartment}`}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  pathname.startsWith("/residente")
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <UserCheck className="w-4 h-4" />
                <span>Portal Residente</span>
              </Link>
            )}

            {canAccessJunta && (
              <Link
                href="/junta"
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  pathname.startsWith("/junta")
                    ? user?.rol === "AUDITOR"
                      ? "bg-purple-600 text-white shadow-sm"
                      : "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {user?.rol === "AUDITOR" ? (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Auditoría Fiscal</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    <span>Junta Directiva</span>
                  </>
                )}
              </Link>
            )}
          </nav>

          {/* Selector Rápido de Perfiles y Estado de Sesión */}
          <div className="flex items-center gap-3">
            {/* Dropdown de Simulación de Perfil */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700/80 border border-slate-700 text-xs font-semibold text-slate-200 transition"
                title="Cambiar perfil para evaluar permisos RBAC"
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    user?.rol === "ADMIN_JUNTA"
                      ? "bg-blue-400"
                      : user?.rol === "AUDITOR"
                      ? "bg-purple-400"
                      : user?.rol === "PROPIETARIO" && activeDepartment === "402"
                      ? "bg-rose-400"
                      : "bg-emerald-400"
                  }`}
                />
                <span className="hidden md:inline">
                  {user ? `${user.nombre} (${user.rol})` : "Seleccionar Rol"}
                </span>
                <span className="md:hidden">
                  {user?.rol === "SUPERADMIN"
                    ? "SuperAdmin"
                    : user?.rol === "ADMIN_JUNTA"
                    ? "Junta"
                    : user?.rol === "AUDITOR"
                    ? "Auditor"
                    : `Dpto. ${activeDepartment}`}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {dropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50 text-slate-800 animate-in fade-in-50"
                  onMouseLeave={() => setDropdownOpen(false)}
                >
                  <div className="px-3 py-2 border-b border-slate-100">
                    <p className="text-xs font-bold text-slate-900">Perfiles de demostración</p>
                    <p className="text-[11px] text-slate-500">
                      Cambie de usuario para comprobar la adaptación de cada pantalla.
                    </p>
                  </div>

                  <div className="py-1">
                    {DEMO_PERSONAS.map((persona) => {
                      const isCurrent = user?.email === persona.email;
                      return (
                        <button
                          key={persona.key}
                          onClick={() => {
                            switchDemoPersona(persona.key);
                            setDropdownOpen(false);
                          }}
                          className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition ${
                            isCurrent ? "bg-slate-100 font-bold" : ""
                          }`}
                        >
                          <div>
                            <p className="font-semibold text-slate-900 flex items-center gap-1.5">
                              <span>{persona.label}</span>
                              {persona.key === "moroso402" && (
                                <Lock className="w-3 h-3 text-rose-500 inline" />
                              )}
                            </p>
                            <p className="text-[10px] text-slate-500">{persona.email}</p>
                          </div>
                          {isCurrent && (
                            <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                              Activo
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  <div className="border-t border-slate-100 pt-1 mt-1 px-2">
                    <Link
                      href="/login"
                      onClick={() => setDropdownOpen(false)}
                      className="block text-center py-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                    >
                      Ir a Pantalla de Login Formal →
                    </Link>
                  </div>
                </div>
              )}
            </div>

            {/* Botón Logout / Login */}
            {user ? (
              <button
                onClick={logout}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                title="Cerrar sesión"
              >
                <LogOut className="w-4 h-4" />
              </button>
            ) : (
              <Link
                href="/login"
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition"
              >
                Ingresar
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
