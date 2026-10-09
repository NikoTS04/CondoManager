"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { iniciarSesion } from "@/lib/api";

export type UserRole = "SUPERADMIN" | "ADMIN_JUNTA" | "AUDITOR" | "PROPIETARIO" | "INQUILINO";

export const ROLE_LABELS: Record<UserRole, string> = {
  SUPERADMIN: "Superadministración",
  ADMIN_JUNTA: "Junta Directiva",
  AUDITOR: "Auditoría",
  PROPIETARIO: "Propietario",
  INQUILINO: "Inquilino",
};

export interface UserProfile {
  id: string;
  email: string;
  nombre: string;
  apellido: string;
  rol: UserRole;
  condominio_id: string | null;
  departamentos: string[];
  tipo_relacion?: string;
}

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
    description: "Solo lectura irrestricta: inspección de bitácora y balances",
  },
  {
    key: "residente102",
    label: "Propietario Solvente (Dpto. 102)",
    email: "residente102@villabonita3.pe",
    password: "Residente123!",
    rol: "PROPIETARIO",
    depto: "102",
    description: "Al día: reporta pagos y reserva áreas comunes sin restricción",
  },
  {
    key: "moroso402",
    label: "Propietario Moroso (Dpto. 402)",
    email: "moroso402@villabonita3.pe",
    password: "Moroso123!",
    rol: "PROPIETARIO",
    depto: "402",
    description: "En mora: bloqueado automáticamente para realizar reservas",
  },
  {
    key: "inquilino504",
    label: "Inquilino (Dpto. 504)",
    email: "inquilino504@villabonita3.pe",
    password: "Inquilino123!",
    rol: "INQUILINO",
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

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [activeDepartment, setActiveDepartment] = useState<string>("102");
  const [authReady, setAuthReady] = useState(false);
  const router = useRouter();

  // Inicializar con la persona demo predeterminada o sesión guardada
  useEffect(() => {
    async function restoreSession() {
      try {
        const savedToken = localStorage.getItem("condo_token");
        const savedUser = localStorage.getItem("condo_user");
        const savedDepto = localStorage.getItem("condo_depto");

        if (savedToken && savedUser) {
          try {
            const parsed = JSON.parse(savedUser) as UserProfile;
            const contextoValido =
              parsed.rol === "SUPERADMIN" || UUID_PATTERN.test(parsed.condominio_id || "");
            if (contextoValido) {
              setUser(parsed);
              setToken(savedToken);
              if (savedDepto) setActiveDepartment(savedDepto);
              else if (parsed.departamentos?.length > 0) {
                setActiveDepartment(parsed.departamentos[0]);
              }
              return;
            }
            localStorage.removeItem("condo_token");
            localStorage.removeItem("condo_user");
            localStorage.removeItem("condo_active_id");
          } catch {
            // Si la sesión guardada no se puede leer, continúa con el modo configurado.
          }
        }

        if (process.env.NEXT_PUBLIC_DEMO_MODE !== "false") {
          await switchDemoPersona("admin");
        }
      } finally {
        setAuthReady(true);
      }
    }

    void restoreSession();
  }, []);

  async function switchDemoPersona(personaKey: string): Promise<boolean> {
    const persona = DEMO_PERSONAS.find((p) => p.key === personaKey) || DEMO_PERSONAS[0];
    return (await login(persona.email, persona.password)).ok;
  }

  async function login(email: string, password = ""): Promise<LoginResult> {
    const cleanEmail = email.trim().toLowerCase();
    try {
      const session = await iniciarSesion(cleanEmail, password);
      const newUser = session.usuario as UserProfile;
      const depto = newUser.departamentos[0] || "102";
      setUser(newUser);
      setToken(session.access_token);
      setActiveDepartment(depto);

      if (typeof window !== "undefined") {
        localStorage.setItem("condo_token", session.access_token);
        localStorage.setItem("condo_user", JSON.stringify(newUser));
        localStorage.setItem("condo_depto", depto);
      }
      return { ok: true, user: newUser };
    } catch (error) {
      return { ok: false, error };
    }
  }

  function logout() {
    setUser(null);
    setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("condo_token");
      localStorage.removeItem("condo_user");
      localStorage.removeItem("condo_depto");
      localStorage.removeItem("condo_active_id");
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
