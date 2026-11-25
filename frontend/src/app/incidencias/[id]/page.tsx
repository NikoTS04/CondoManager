"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import RoleGuard from "@/components/RoleGuard";
import AccessDenied from "@/components/layout/AccessDenied";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Feedback";
import { useAuth } from "@/context/AuthContext";
import { RevisionIncidenciaForm } from "@/features/junta/RevisionIncidenciaForm";
import { consultarIncidencia, descargarFotoIncidencia, NIVELES_INCIDENCIA, type Incidencia } from "@/lib/api";

function DetalleIncidencia({ id }: { id: string }) {
  const { user } = useAuth();
  const [incidencia, setIncidencia] = useState<Incidencia>();
  const [error, setError] = useState("");
  const [errorFoto, setErrorFoto] = useState("");
  const [descargando, setDescargando] = useState(false);
  const [revisionConsulta, setRevisionConsulta] = useState(0);
  const [confirmacion, setConfirmacion] = useState("");
  const esJunta = user?.rol === "ADMIN_JUNTA";

  useEffect(() => {
    const solicitud = new AbortController();
    setIncidencia(undefined);
    setError("");
    consultarIncidencia(id, solicitud.signal)
      .then((detalle) => {
        if (!solicitud.signal.aborted) setIncidencia(detalle);
      })
      .catch(() => {
        if (!solicitud.signal.aborted) setError("El reporte no está disponible en tu cuenta.");
      });
    return () => solicitud.abort();
  }, [id, revisionConsulta]);

  async function descargar() {
    setErrorFoto("");
    setDescargando(true);
    try {
      await descargarFotoIncidencia(id);
    } catch {
      setErrorFoto("No pudimos descargar la foto. Inténtalo de nuevo.");
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link className="text-sm font-medium text-brand-700 underline" href={esJunta ? "/junta#incidencias" : "/residente"}>
        {esJunta ? "Volver a incidencias" : "Volver a mi portal"}
      </Link>
      {error ? <Alert tone="danger">{error}</Alert> : !incidencia ? (
        <Spinner label="Cargando reporte…" />
      ) : (
        <>
          {confirmacion && <Alert tone="success">{confirmacion}</Alert>}
          <Card>
            <CardHeader
              title="Detalle de la incidencia"
              actions={
                <Badge tone={incidencia.estado === "RECHAZADO" ? "warning" : "info"}>
                  {incidencia.estado === "RECHAZADO" ? "Rechazado" : "Registrado"}
                </Badge>
              }
            />
            <CardBody className="space-y-5">
              <dl className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted">Ubicación</dt>
                  <dd className="break-words font-medium">{incidencia.ubicacion}</dd>
                </div>
                <div>
                  <dt className="text-muted">Categoría reportada</dt>
                  <dd className="break-words font-medium">{incidencia.categoria}</dd>
                </div>
                <div>
                  <dt className="text-muted">Urgencia reportada</dt>
                  <dd className="font-medium">{NIVELES_INCIDENCIA[incidencia.urgencia]}</dd>
                </div>
                <div>
                  <dt className="text-muted">Código</dt>
                  <dd className="break-all font-medium">{incidencia.id}</dd>
                </div>
                {incidencia.prioridad && (
                  <>
                    <div>
                      <dt className="text-muted">Categoría confirmada</dt>
                      <dd className="break-words font-medium">{incidencia.categoria_confirmada}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Prioridad de Junta</dt>
                      <dd className="font-medium">{NIVELES_INCIDENCIA[incidencia.prioridad]}</dd>
                    </div>
                  </>
                )}
                <div className="sm:col-span-2">
                  <dt className="text-muted">Descripción</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words">{incidencia.descripcion}</dd>
                </div>
              </dl>
              {incidencia.motivo_rechazo && (
                <Alert tone="warning" title="Motivo del rechazo">
                  <p className="whitespace-pre-wrap break-words">{incidencia.motivo_rechazo}</p>
                </Alert>
              )}
              {incidencia.tiene_evidencia && (
                <Button variant="secondary" onClick={descargar} loading={descargando} loadingText="Descargando…">
                  Descargar foto
                </Button>
              )}
              {errorFoto && <Alert tone="danger">{errorFoto}</Alert>}
            </CardBody>
          </Card>
          {esJunta && incidencia.estado === "REGISTRADO" && (
            <RevisionIncidenciaForm
              key={incidencia.version}
              incidencia={incidencia}
              onActualizada={(detalle) => {
                setIncidencia(detalle);
                setConfirmacion(detalle.estado === "RECHAZADO" ? "Incidencia rechazada." : "Clasificación guardada.");
              }}
              onRecargar={() => {
                setConfirmacion("");
                setRevisionConsulta((actual) => actual + 1);
              }}
            />
          )}
        </>
      )}
    </div>
  );
}

export default function IncidenciaPage({ params }: { params: { id: string } }) {
  return (
    <RoleGuard
      allowedRoles={["RESIDENTE", "ADMIN_JUNTA"]}
      fallback={<AccessDenied loginHref={`/login?incidencia=${encodeURIComponent(params.id)}`} />}
    >
      <DetalleIncidencia key={params.id} id={params.id} />
    </RoleGuard>
  );
}
