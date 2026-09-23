import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "CondoManager - Sistema Automatizado para Condominios (SDD)",
  description:
    "Gestión contable, conciliación bancaria, control de solvencia financiera y reservas de áreas comunes para Villa Bonita 3 (139 departamentos).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="bg-slate-50 text-slate-900 min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <footer className="bg-slate-900 text-slate-400 text-xs py-6 border-t border-slate-800 text-center">
          <div className="max-w-7xl mx-auto px-4">
            <p className="font-medium text-slate-300">CondoManager • Spec-Driven Development (SDD)</p>
            <p className="mt-1 text-slate-500">
              Arquitectura de Cero Pérdida Decimal (ADR-002) • Invariantes de Solvencia Financiera • 139 Departamentos Piloto
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
