import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function AccessDenied() {
  const { user } = useAuth();

  return (
    <section
      className="mx-auto max-w-prose space-y-3 py-10"
      aria-labelledby="access-denied-title"
    >
      <h1 id="access-denied-title" className="text-2xl font-bold">
        {user ? "Sin acceso" : "Inicia sesión para continuar"}
      </h1>
      <p className="text-muted">
        {user
          ? "Tu cuenta no tiene permisos para ver esta sección. Si crees que es un error, contacta a la administración."
          : "Inicia sesión con tu cuenta para acceder a esta sección."}
      </p>
      <Link
        href={user ? "/" : "/login"}
        className="inline-flex min-h-11 items-center rounded-lg border border-line bg-surface px-4 text-sm font-semibold text-ink hover:bg-canvas"
      >
        {user ? "Volver al inicio" : "Iniciar sesión"}
      </Link>
    </section>
  );
}
