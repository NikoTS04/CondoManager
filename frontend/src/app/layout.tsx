import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import TopBar from "@/components/layout/TopBar";
import { AuthProvider } from "@/context/AuthContext";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-sans" });

export const metadata: Metadata = {
  title: "CondoManager - Sistema Automatizado para Condominios",
  description:
    "Consulta de cuentas, conciliación de pagos y reservas de áreas comunes para tu condominio.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body
        className={`${inter.variable} min-h-dvh flex flex-col bg-canvas text-ink font-sans`}
      >
        <AuthProvider>
          <a
            href="#contenido"
            className="sr-only z-[100] rounded-md bg-surface p-3 text-ink focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:ring-2 focus:ring-brand-600"
          >
            Saltar al contenido
          </a>
          <TopBar />
          <main id="contenido" className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6 lg:p-8">
            {children}
          </main>
        </AuthProvider>
        <footer className="border-t border-line bg-surface py-4 text-center text-xs text-muted">
          <p>CondoManager · Gestión de condominios</p>
        </footer>
      </body>
    </html>
  );
}
