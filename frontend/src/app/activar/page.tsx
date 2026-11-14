"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { activarCuenta, ApiError } from "@/lib/api";

export default function ActivarPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [busy, setBusy] = useState(false);
  const [completado, setCompletado] = useState(false);
  const [error, setError] = useState<{ mensaje: string; codigo?: string } | null>(null);
  const leido = useRef(false);

  useEffect(() => {
    if (leido.current) return;
    leido.current = true;
    const valor = new URLSearchParams(window.location.hash.slice(1)).get("token");
    setToken(valor || "");
    // El fragmento no viaja a servidores ni Referer y se retira del historial visible.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function activar(event: FormEvent) {
    event.preventDefault();
    if (busy || !token) return;
    if (password !== confirmacion) {
      setError({ mensaje: "Las contraseñas no coinciden." });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await activarCuenta(token, password);
      setCompletado(true);
      setToken("");
      setPassword("");
      setConfirmacion("");
    } catch (cause) {
      setError({ mensaje: cause instanceof Error ? cause.message : "No se pudo conectar con la API. Reintenta con el mismo enlace.", codigo: cause instanceof ApiError ? cause.errorCode : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto max-w-lg space-y-6 py-8" aria-labelledby="activacion-titulo">
      <header><h1 id="activacion-titulo" className="text-2xl font-bold">Activa tu cuenta</h1>
        <p className="mt-2 text-sm text-muted">Elige la contraseña con la que accederás a CondoManager.</p></header>
      {token === null ? <p role="status">Preparando activación…</p> : completado ? (
        <Alert tone="success" title="Tu cuenta está lista">La contraseña se guardó correctamente. <Link className="underline" href="/login">Inicia sesión</Link> para acceder.</Alert>
      ) : !token ? (
        <Alert tone="danger" title="Falta el enlace de invitación">Abre el enlace completo que recibiste por correo. Si ya no lo tienes, solicita una invitación nueva a la administración.</Alert>
      ) : (
        <form onSubmit={activar} className="space-y-5 rounded-xl border border-line bg-surface p-6 shadow-sm">
          {error && <Alert tone="danger" code={error.codigo} title="No se pudo activar la cuenta">{error.mensaje}</Alert>}
          <Field label="Nueva contraseña" required hint="Entre 8 y 128 caracteres.">
            <Input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={password} disabled={busy} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Confirmar contraseña" required>
            <Input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirmacion} disabled={busy} onChange={(e) => setConfirmacion(e.target.value)} />
          </Field>
          <Button type="submit" loading={busy} disabled={busy} loadingText="Activando…">Activar cuenta</Button>
          <p className="text-sm text-muted">Si el enlace venció o fue revocado, pide el reenvío a la administración.</p>
        </form>
      )}
      {!completado && <Link className="inline-block text-sm underline" href="/login">Volver al inicio de sesión</Link>}
    </section>
  );
}
