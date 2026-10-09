"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { DEMO_PERSONAS, useAuth } from "@/context/AuthContext";
import { parseApiError } from "@/lib/errors";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; code: string | null } | null>(null);
  const goToPortal = (role: string) => {
    router.push(["ADMIN_JUNTA", "AUDITOR", "SUPERADMIN"].includes(role) ? "/junta" : "/residente");
  };

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await login(email, password);
      if (result.ok && result.user) {
        goToPortal(result.user.rol);
      } else {
        setError(parseApiError(result.error, "No pudimos iniciar sesión. Revisa tus credenciales e inténtalo de nuevo."));
      }
    } catch (cause) {
      setError(parseApiError(cause, "No pudimos iniciar sesión. Inténtalo de nuevo."));
    } finally {
      setLoading(false);
    }
  }

  async function quickLogin(key: string) {
    setLoading(true);
    setError(null);
    try {
      const persona = DEMO_PERSONAS.find((item) => item.key === key);
      if (!persona) {
        setError(parseApiError(null, "No encontramos ese perfil de demostración."));
        return;
      }
      const result = await login(persona.email, persona.password);
      if (result.ok && result.user) goToPortal(result.user.rol);
      else setError(parseApiError(result.error, "No se pudo iniciar la sesión de demostración."));
    } catch (cause) {
      setError(parseApiError(cause, "No se pudo iniciar la sesión de demostración."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6 py-8">
      <header>
        <h1 className="text-2xl font-bold">Iniciar sesión</h1>
        <p className="mt-1 text-sm text-muted">Accede al portal de tu condominio.</p>
      </header>
      {error && <Alert tone="danger" code={error.code}>{error.message}</Alert>}
      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-6"
      >
        <Field label="Correo electrónico" required>
          <Input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        <Field label="Contraseña" required>
          <Input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Button type="submit" loading={loading} loadingText="Ingresando…">
          Iniciar sesión
        </Button>
      </form>
      {process.env.NEXT_PUBLIC_DEMO_MODE !== "false" && (
        <section className="space-y-3" aria-labelledby="demos-title">
          <div>
            <h2 id="demos-title" className="text-lg font-semibold">Perfiles de demostración</h2>
            <p className="text-sm text-muted">Elige un perfil para explorar sus funciones.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {DEMO_PERSONAS.map((persona) => (
              <Button
                key={persona.key}
                variant="secondary"
                className="justify-start text-left"
                disabled={loading}
                onClick={() => void quickLogin(persona.key)}
              >
                {persona.label}
              </Button>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
