import Link from "next/link";

export default function NotFound() {
  return (
    <section className="mx-auto max-w-prose space-y-3 py-10">
      <h1 className="text-2xl font-bold">Página no encontrada</h1>
      <p className="text-muted">
        No encontramos la página que buscas. Revisa la dirección o vuelve al inicio.
      </p>
      <Link href="/" className="inline-flex min-h-11 items-center text-brand-700 underline">
        Volver al inicio
      </Link>
    </section>
  );
}
