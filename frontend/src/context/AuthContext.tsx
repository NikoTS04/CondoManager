"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export type UserRole = "SUPERADMIN" | "ADMIN_JUNTA" | "AUDITOR" | "PROPIETARIO" | "INQUILINO";

export interface UserProfile {
  id: string;
  email: string;
  nombre: string;
  apellido: string;
  rol: UserRole;
  condominio_id: string;
  departamentos: string[];
  tipo_relacion?: string;
}

export interface DemoPersona {
  key: string;
  label: string;
  email: string;
  rol: UserRole;
  depto?: string;
  badgeColor: string;
  description: string;
}

export const DEMO_PERSONAS: DemoPersona[] = [
  {
    key: "superadmin",
    label: "SuperAdmin de Plataforma",
    email: "superadmin@condomanager.pe",
    rol: "SUPERADMIN",
    badgeColor: "bg-slate-900 text-white",
    description: "Configura condominios, reglas generales y accesos globales",
  },
  {
    key: "admin",
    label: "Junta Directiva",
    email: "admin@villabonita3.pe",
    rol: "ADMIN_JUNTA",
    badgeColor: "bg-blue-600 text-white",
    description: "Gestión total: emisión masiva, conciliación de pagos y moras",
  },
  {
    key: "auditor",
    label: "Auditor Fiscal",
    email: "auditor@villabonita3.pe",
    rol: "AUDITOR",
    badgeColor: "bg-purple-600 text-white",
    description: "Solo lectura irrestricta: inspección de bitácora y balances",
  },
  {
    key: "residente102",
    label: "Propietario Solvente (Dpto. 102)",
    email: "residente102@villabonita3.pe",
    rol: "PROPIETARIO",
    depto: "102",
    badgeColor: "bg-emerald-600 text-white",
    description: "Al día: reporta pagos y reserva áreas comunes sin restricción",
  },
  {
    key: "moroso402",
    label: "Propietario Moroso (Dpto. 402)",
    email: "moroso402@villabonita3.pe",
    rol: "PROPIETARIO",
    depto: "402",
    badgeColor: "bg-rose-600 text-white",
    description: "En mora: bloqueado automáticamente para realizar reservas",
  },
  {
    key: "inquilino504",
    label: "Inquilino (Dpto. 504)",
    email: "inquilino504@villabonita3.pe",
    rol: "INQUILINO",
    depto: "504",
    badgeColor: "bg-teal-600 text-white",
    description: "Arrendatario: reporta pagos y reserva para su unidad asignada",
  },
];

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  activeDepartment: string;
  isAuthenticated: boolean;
  login: (email: string, password?: string) => Promise<boolean>;
  logout: () => void;
  switchDemoPersona: (personaKey: string) => void;
  setActiveDepartment: (depto: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [activeDepartment, setActiveDepartment] = useState<string>("102");
  const router = useRouter();

  // Inicializar con la persona demo predeterminada o sesión guardada
  useEffect(() => {
    const savedToken = typeof window !== "undefined" ? localStorage.getItem("condo_token") : null;
    const savedUser = typeof window !== "undefined" ? localStorage.getItem("condo_user") : null;
    const savedDepto = typeof window !== "undefined" ? localStorage.getItem("condo_depto") : null;

    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        setUser(parsed);
        setToken(savedToken);
        if (savedDepto) setActiveDepartment(savedDepto);
        else if (parsed.departamentos?.length > 0) setActiveDepartment(parsed.departamentos[0]);
        return;
      } catch {}
    }

    // Por defecto, inicializar como Junta Directiva para demostración directa
    switchDemoPersona("admin");
  }, []);

  function switchDemoPersona(personaKey: string) {
    const persona = DEMO_PERSONAS.find((p) => p.key === personaKey) || DEMO_PERSONAS[0];
    const newUser: UserProfile = {
      id: `usr-${persona.key}`,
      email: persona.email,
      nombre: persona.label.split(" ")[0],
      apellido: persona.label.split(" ").slice(1).join(" ") || "Demo",
      rol: persona.rol,
      condominio_id: "vb3-condo",
      departamentos: persona.depto ? [persona.depto] : [],
      tipo_relacion: persona.rol === "INQUILINO" ? "INQUILINO" : persona.rol === "PROPIETARIO" ? "PROPIETARIO_TITULAR" : "ADMINISTRADOR",
    };

    const mockToken = `jwt-mock-token-${persona.key}-${Date.now()}`;
    setUser(newUser);
    setToken(mockToken);
    const depto = persona.depto || (persona.rol === "ADMIN_JUNTA" ? "102" : "102");
    setActiveDepartment(depto);

    if (typeof window !== "undefined") {
      localStorage.setItem("condo_token", mockToken);
      localStorage.setItem("condo_user", JSON.stringify(newUser));
      localStorage.setItem("condo_depto", depto);
    }
  }

  async function login(email: string, password = "Password123!"): Promise<boolean> {
    const cleanEmail = email.trim().toLowerCase();
    const persona = DEMO_PERSONAS.find((p) => p.email.toLowerCase() === cleanEmail);

    if (persona) {
      switchDemoPersona(persona.key);
      return true;
    }

    // Fallback genérico para correo nuevo
    const newUser: UserProfile = {
      id: `usr-${Date.now()}`,
      email: cleanEmail,
      nombre: "Usuario",
      apellido: "Residente",
      rol: "PROPIETARIO",
      condominio_id: "vb3-condo",
      departamentos: ["102"],
      tipo_relacion: "PROPIETARIO_TITULAR",
    };
    const mockToken = `jwt-token-${Date.now()}`;
    setUser(newUser);
    setToken(mockToken);
    setActiveDepartment("102");

    if (typeof window !== "undefined") {
      localStorage.setItem("condo_token", mockToken);
      localStorage.setItem("condo_user", JSON.stringify(newUser));
      localStorage.setItem("condo_depto", "102");
    }
    return true;
  }

  function logout() {
    setUser(null);
    setToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("condo_token");
      localStorage.removeItem("condo_user");
      localStorage.removeItem("condo_depto");
    }
    router.push("/login");
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        activeDepartment,
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
