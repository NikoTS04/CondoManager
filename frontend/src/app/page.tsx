"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Feedback";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const router = useRouter();
  const { user } = useAuth();
  useEffect(() => {
    if (!user) return;
    router.replace(["PROPIETARIO", "INQUILINO"].includes(user.rol) ? "/residente" : "/junta");
  }, [user, router]);
  if (user) return <div className="flex min-h-64 items-center justify-center"><Spinner label="Abriendo tu portal…" /></div>;

  return (
    <section className="mx-auto max-w-3xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">Bienvenido a CondoManager</h1>
        <p className="mt-2 text-muted">Elige un portal o inicia sesión para continuar.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardBody className="space-y-3">
            <h2 className="text-lg font-semibold">Portal residente</h2>
            <p className="text-sm text-muted">
              Consulta tus cuotas, reporta pagos y reserva áreas comunes.
            </p>
            <Link
              className="inline-flex min-h-11 items-center rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
              href="/residente"
            >
              Ir al portal residente
            </Link>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="space-y-3">
            <h2 className="text-lg font-semibold">Portal junta</h2>
            <p className="text-sm text-muted">
              Gestiona cuotas, comprobantes y la operación del condominio.
            </p>
            <Link
              className="inline-flex min-h-11 items-center rounded-lg border border-line px-4 text-sm font-semibold hover:bg-canvas"
              href="/junta"
            >
              Ir al portal junta
            </Link>
          </CardBody>
        </Card>
      </div>
      <Link className="text-sm text-brand-700 underline" href="/login">
        Iniciar sesión
      </Link>
    </section>
  );
}
