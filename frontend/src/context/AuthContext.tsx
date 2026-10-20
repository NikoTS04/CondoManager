"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { iniciarSesion, obtenerSesion } from "@/lib/api";
import { isSessionUser, seleccionarUnidad, UUID_PATTERN, type SessionUser, type UserRole } from "@/lib/session";

export { ROLE_LABELS, type UserRole } from "@/lib/session";
export type UserProfile = SessionUser;

export interface DemoPersona {
  key: string;
  label: string;
  email: string;
  password: string;
  rol: UserRole;
  depto?: string;
  description: string;
}

export const DEMO_PERSONAS: DemoPersona[] = [
  {
    key: "superadmin",
    label: "SuperAdmin de Plataforma",
    email: "superadmin@condomanager.pe",
    password: "SuperAdmin123!",
    rol: "SUPERADMIN",
    description: "Configura condominios, reglas generales y accesos globales",
  },
  {
    key: "admin",
    label: "Junta Directiva",
    email: "admin@villabonita3.pe",
    password: "Admin123!",
    rol: "ADMIN_JUNTA",
    description: "Gestión total: emisión masiva, conciliación de pagos y moras",
  },
  {
    key: "auditor",
    label: "Auditor Fiscal",
    email: "auditor@villabonita3.pe",
    password: "Auditor123!",
    rol: "AUDITOR",
    description: "Solo lectura de su condominio: inspección de bitácora y balances",
  },
  {
    key: "residente102",
    label: "Propietario Solvente (Dpto. 102)",
    email: "residente102@villabonita3.pe",
    password: "Residente123!",
    rol: "RESIDENTE",
    depto: "102",
    description: "Al día: reporta pagos y reserva áreas comunes sin restricción",
  },
  {
    key: "moroso402",
    label: "Propietario Moroso (Dpto. 402)",
    email: "moroso402@villabonita3.pe",
    password: "Moroso123!",
    rol: "RESIDENTE",
    depto: "402",
    description: "En mora: bloqueado automáticamente para realizar reservas",
  },
  {
    key: "inquilino504",
    label: "Inquilino (Dpto. 504)",
    email: "inquilino504@villabonita3.pe",
    password: "Inquilino123!",
    rol: "RESIDENTE",
    depto: "504",
    description: "Arrendatario: reporta pagos y reserva para su unidad asignada",
  },
];

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  activeDepartment: string;
  authReady: boolean;
  isAuthenticated: boolean;
  login: (email: string, password?: string) => Promise<LoginResult>;
  logout: () => void;
  switchDemoPersona: (personaKey: string) => Promise<boolean>;
  setActiveDepartment: (depto: string) => void;
}

export interface LoginResult {
  ok: boolean;
  user?: UserProfile;
  error?: unknown;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function limpiarSesion() {
  ["condo_token", "condo_user", "condo_depto", "condo_active_id"].forEach((key) => localStorage.removeItem(key));
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [activeDepartment, actualizarDepartamento] = useState<string>("");
  const [authReady, setAuthReady] = useState(false);
  const router = useRouter();

  const login = useCallback(async (email: string, password = ""): Promise<LoginResult> => {
    try {
      const session = await iniciarSesion(email.trim().toLowerCase(), password);
      if (!isSessionUser(session.usuario)) throw new Error("Contrato de sesión incompatible. Inicia sesión de nuevo.");
      const newUser = session.usuario;
      const depto = seleccionarUnidad(newUser);
      limpiarSesion();
      localStorage.setItem("condo_token", session.access_token);
      localStorage.setItem("condo_user", JSON.stringify(newUser));
      localStorage.setItem("condo_depto", depto);
      setUser(newUser);
      setToken(session.access_token);
      actualizarDepartamento(depto);
      return { ok: true, user: newUser };
    } catch (error) {
      return { ok: false, error };
    }
  }, []);

  // La caché no concede permisos: restaurar siempre contra /auth/me.
  useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      try {
        const savedToken = localStorage.getItem("condo_token");
        const savedUser = localStorage.getItem("condo_user");
        const savedDepto = localStorage.getItem("condo_depto");

        if (savedToken || savedUser) {
          try {
            if (!savedToken || !isSessionUser(JSON.parse(savedUser || "null"))) throw new Error("Sesión antigua");
            const perfil = await obtenerSesion();
            if (!isSessionUser(perfil)) throw new Error("Sesión incompatible");
            if (cancelled) return;
            const depto = seleccionarUnidad(perfil, savedDepto);
            setUser(perfil);
            setToken(savedToken);
            actualizarDepartamento(depto);
            localStorage.setItem("condo_user", JSON.stringify(perfil));
            localStorage.setItem("condo_depto", depto);
          } catch {
            if (!cancelled) {
              limpiarSesion();
              router.replace("/login");
            }
          }
          return; // Nunca sustituir una sesión antigua por un login demo automático.
        }

        if (process.env.NEXT_PUBLIC_DEMO_MODE !== "false") {
          const persona = DEMO_PERSONAS.find((p) => p.key === "admin")!;
          if (!cancelled) await login(persona.email, persona.password);
        }
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }

    void restoreSession();
    return () => { cancelled = true; };
  }, [login, router]);

  const setActiveDepartment = useCallback((depto: string) => {
    if (!user) return;
    if (user.rol === "RESIDENTE" && !user.departamentos.some((v) => v.es_activo && v.departamento_id === depto)) return;
    if (depto && !UUID_PATTERN.test(depto)) return;
    actualizarDepartamento(depto);
    localStorage.setItem("condo_depto", depto);
  }, [user]);

  async function switchDemoPersona(personaKey: string): Promise<boolean> {
    const persona = DEMO_PERSONAS.find((p) => p.key === personaKey) || DEMO_PERSONAS[0];
    return (await login(persona.email, persona.password)).ok;
  }

  function logout() {
    setUser(null);
    setToken(null);
    actualizarDepartamento("");
    if (typeof window !== "undefined") {
      limpiarSesion();
    }
    router.push("/login");
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        activeDepartment,
        authReady,
        isAuthenticated: !!user,
        login,
        logout,
        switchDemoPersona,
        setActiveDepartment,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe ser utilizado dentro de un AuthProvider");
  }
  return context;
}
