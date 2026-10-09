"use client";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section className="mx-auto max-w-prose space-y-4 py-10">
      <h1 className="text-2xl font-bold">No pudimos cargar esta página</h1>
      <Alert tone="danger">Ocurrió un problema inesperado. Inténtalo de nuevo.</Alert>
      <Button onClick={reset}>Reintentar</Button>
    </section>
  );
}
