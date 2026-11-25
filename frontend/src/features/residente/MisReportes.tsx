"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, Spinner } from "@/components/ui/Feedback";
import { ReportarIncidenciaForm } from "@/features/residente/ReportarIncidenciaForm";
import { listarMisReportes, type BandejaIncidencias } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const TAMANO_PAGINA = 25;

function MisReportes({ onReportar, puedeReportar }: { onReportar: () => void; puedeReportar: boolean }) {
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);
  const [resultado, setResultado] = useState<BandejaIncidencias>();
  const [error, setError] = useState(false);

  useEffect(() => {
    const solicitud = new AbortController();
    setResultado(undefined);
    setError(false);
    listarMisReportes(pagina * TAMANO_PAGINA, TAMANO_PAGINA, solicitud.signal)
      .then((datos) => {
        if (!solicitud.signal.aborted) setResultado(datos);
      })
      .catch(() => {
        if (!solicitud.signal.aborted) setError(true);
      });
    return () => solicitud.abort();
  }, [pagina, revision]);

  return (
    <Card className="max-w-4xl">
      <CardHeader
        title="Mis reportes"
        actions={(
          <>
            <Button variant="secondary" size="sm" onClick={() => setRevision((actual) => actual + 1)}>
              Actualizar
            </Button>
            <Button size="sm" disabled={!puedeReportar} onClick={onReportar}>Reportar incidencia</Button>
          </>
        )}
      />
      {error ? (
        <Alert className="m-4" tone="danger">No pudimos cargar tus reportes. Pulsa Actualizar para reintentar.</Alert>
      ) : !resultado ? (
        <Spinner className="m-4" label="Cargando tus reportes…" />
      ) : resultado.items.length === 0 ? (
        <EmptyState title={pagina === 0 ? "Todavía no tienes reportes" : "No hay más reportes en esta página"} />
      ) : (
        <ul className="divide-y divide-line">
          {resultado.items.map((reporte) => {
            const rechazado = reporte.estado === "RECHAZADO";
            return (
              <li key={reporte.id} className="space-y-2 px-4 py-4 sm:px-6">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="break-words font-semibold">{reporte.ubicacion}</h3>
                  <Badge tone={rechazado ? "warning" : "info"}>
                    {rechazado ? "Rechazado" : "Registrado"}
                  </Badge>
                </div>
                <p className="text-sm text-muted">
                  {reporte.categoria_confirmada ?? reporte.categoria}
                  {" · "}
                  <time dateTime={reporte.creado_en}>{formatDateTime(reporte.creado_en)}</time>
                </p>
                {reporte.motivo_rechazo && (
                  <p className="whitespace-pre-wrap break-words text-sm text-warning-800">
                    <strong>Motivo del rechazo</strong>{" "}{reporte.motivo_rechazo}
                  </p>
                )}
                <Link className="inline-flex min-h-11 items-center text-sm font-semibold text-brand-700 underline" href={`/incidencias/${reporte.id}`}>
                  Ver reporte
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {resultado && (pagina > 0 || resultado.hay_mas) && (
        <nav className="flex flex-wrap items-center justify-end gap-3 border-t border-line p-4" aria-label="Páginas de mis reportes">
          <Button variant="secondary" size="sm" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>
            Anterior
          </Button>
          <span className="text-sm text-muted">Página {pagina + 1}</span>
          <Button variant="secondary" size="sm" disabled={!resultado.hay_mas} onClick={() => setPagina(pagina + 1)}>
            Siguiente
          </Button>
        </nav>
      )}
    </Card>
  );
}

export function IncidenciasResidente({
  departamentoId,
  cargandoDepartamento,
}: {
  departamentoId: string;
  cargandoDepartamento: boolean;
}) {
  const [reportando, setReportando] = useState(false);

  if (!reportando || !departamentoId) {
    return (
      <MisReportes
        onReportar={() => setReportando(true)}
        puedeReportar={!!departamentoId && !cargandoDepartamento}
      />
    );
  }

  return (
    <div className="space-y-3">
      <Button variant="ghost" onClick={() => setReportando(false)}>Volver a mis reportes</Button>
      <ReportarIncidenciaForm key={departamentoId} departamentoId={departamentoId} />
    </div>
  );
}
