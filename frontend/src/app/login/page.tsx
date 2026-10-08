"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, DEMO_PERSONAS, UserRole } from "@/context/AuthContext";
import {
  Building2,
  ShieldCheck,
  UserCheck,
  KeyRound,
  ArrowRight,
  ShieldAlert,
  Search,
  CheckCircle2,
  Lock,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, switchDemoPersona } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      setError("Por favor, ingrese un correo electrónico.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const ok = await login(email, password);
      if (ok) {
        if (email.includes("admin") || email.includes("auditor")) {
          router.push("/junta");
        } else {
          router.push("/residente");
        }
      }
    } catch {
      setError("Error al iniciar sesión.");
    } finally {
      setLoading(false);
    }
  }

  function handleQuickLogin(personaKey: string, role: UserRole) {
    switchDemoPersona(personaKey);
    if (role === "ADMIN_JUNTA" || role === "AUDITOR" || role === "SUPERADMIN") {
      router.push("/junta");
    } else {
      router.push("/residente");
    }
  }

  return (
    <div className="min-h-[80vh] flex flex-col justify-center py-8 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto space-y-8">
      {/* Encabezado */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-semibold">
          <Building2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Villa Bonita 3 • Edificio 3 (139 Departamentos)</span>
        </div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">
          Autenticación y Control de Acceso (RBAC)
        </h1>
        <p className="text-sm text-slate-600 max-w-xl mx-auto">
          Inicie sesión con sus credenciales o seleccione un perfil de prueba para verificar las restricciones de pantalla y la invariante de solvencia en tiempo real.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 items-start">
        {/* Formulario Estándar */}
        <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-sm border border-slate-200 space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-indigo-600" />
              <span>Acceso con Credenciales</span>
            </h2>
            <p className="text-xs text-slate-500">
              Token JWT emitido con claims validados criptográficamente.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Correo Electrónico
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ejemplo@villabonita3.pe"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-sm transition shadow-sm flex items-center justify-center gap-2"
            >
              <span>{loading ? "Verificando..." : "Ingresar al Sistema"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Perfiles de Demostración */}
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <span>Perfiles de Demostración (1 Clic)</span>
            </h2>
            <p className="text-xs text-slate-500">
              Pruebe de inmediato cómo se adapta cada pantalla según el rol asignado.
            </p>
          </div>

          <div className="space-y-2.5">
            {DEMO_PERSONAS.map((persona) => {
              const isMoroso = persona.key === "moroso402";
              const isAudit = persona.rol === "AUDITOR";
              return (
                <button
                  key={persona.key}
                  onClick={() => handleQuickLogin(persona.key, persona.rol)}
                  className="w-full text-left p-3.5 rounded-xl bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-sm transition-all group flex items-start justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${persona.badgeColor}`}>
                        {persona.label}
                      </span>
                      {isMoroso && (
                        <span className="flex items-center gap-1 text-[11px] font-semibold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded">
                          <Lock className="w-3 h-3" /> Bloqueado
                        </span>
                      )}
                      {isAudit && (
                        <span className="flex items-center gap-1 text-[11px] font-semibold text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">
                          <Search className="w-3 h-3" /> Solo Lectura
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-600 font-medium">
                      {persona.description}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {persona.email}
                    </p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-1" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
