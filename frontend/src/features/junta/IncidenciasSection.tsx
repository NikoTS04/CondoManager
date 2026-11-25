"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, Spinner } from "@/components/ui/Feedback";
import { listarIncidencias, NIVELES_INCIDENCIA, type BandejaIncidencias } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

const TAMANO_PAGINA = 25;

export function IncidenciasSection() {
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);
  const [resultado, setResultado] = useState<BandejaIncidencias>();
  const [error, setError] = useState("");

  useEffect(() => {
    const solicitud = new AbortController();
    setResultado(undefined);
    setError("");
    listarIncidencias(pagina * TAMANO_PAGINA, TAMANO_PAGINA, solicitud.signal)
      .then((datos) => {
        if (!solicitud.signal.aborted) setResultado(datos);
      })
      .catch(() => {
        if (!solicitud.signal.aborted) setError("No pudimos cargar las incidencias.");
      });
    return () => solicitud.abort();
  }, [pagina, revision]);

  return (
    <section className="space-y-4" aria-label="Bandeja de incidencias">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">Los reportes urgentes pendientes aparecen primero.</p>
        <Button variant="secondary" size="sm" onClick={() => setRevision((actual) => actual + 1)}>
          Actualizar bandeja
        </Button>
      </div>
      {error ? <Alert tone="danger">{error}</Alert> : !resultado ? (
        <Spinner label="Cargando incidencias…" />
      ) : resultado.items.length === 0 ? (
        <Card><EmptyState title="No hay incidencias en esta página" /></Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {resultado.items.map((incidencia) => {
              const prioridad = incidencia.prioridad ?? incidencia.urgencia;
              const rechazada = incidencia.estado === "RECHAZADO";
              const urgente = !rechazada && prioridad === "URGENTE";
              return (
                <li key={incidencia.id}>
                  <Link
                    href={`/incidencias/${incidencia.id}`}
                    className={cn(
                      "flex min-w-0 flex-wrap items-start justify-between gap-3 border-l-4 px-4 py-4 hover:bg-canvas",
                      urgente ? "border-danger-600" : "border-transparent",
                    )}
                  >
                    <div className="min-w-0 space-y-1">
                      <p className="break-words font-semibold">{incidencia.ubicacion}</p>
                      <p className="break-words text-sm text-muted">
                        {incidencia.categoria_confirmada ?? incidencia.categoria}
                      </p>
                      <time className="text-xs text-muted" dateTime={incidencia.creado_en}>
                        {formatDateTime(incidencia.creado_en)}
                      </time>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={urgente ? "danger" : "neutral"}>
                        {NIVELES_INCIDENCIA[prioridad]}{incidencia.prioridad === null ? " · reportada" : ""}
                      </Badge>
                      <Badge tone={rechazada ? "warning" : "info"}>
                        {rechazada ? "Rechazado" : "Registrado"}
                      </Badge>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
      {resultado && (pagina > 0 || resultado.hay_mas) && (
        <nav className="flex items-center justify-end gap-3" aria-label="Páginas de incidencias">
          <Button variant="secondary" size="sm" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>
            Anterior
          </Button>
          <span className="text-sm text-muted">Página {pagina + 1}</span>
          <Button variant="secondary" size="sm" disabled={!resultado.hay_mas} onClick={() => setPagina(pagina + 1)}>
            Siguiente
          </Button>
        </nav>
      )}
    </section>
  );
}
