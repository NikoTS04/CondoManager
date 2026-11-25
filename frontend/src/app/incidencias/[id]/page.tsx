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
import { consultarIncidencia, descargarFotoIncidencia, type Incidencia } from "@/lib/api";

const URGENCIAS = { BAJA: "Baja", MEDIA: "Media", ALTA: "Alta", URGENTE: "Urgente" };

function DetalleIncidencia({ id }: { id: string }) {
  const { user } = useAuth();
  const [incidencia, setIncidencia] = useState<Incidencia>();
  const [error, setError] = useState("");
  const [errorFoto, setErrorFoto] = useState("");
  const [descargando, setDescargando] = useState(false);
  const esJunta = user?.rol === "ADMIN_JUNTA";

  useEffect(() => {
    const solicitud = new AbortController();
    consultarIncidencia(id, solicitud.signal)
      .then(setIncidencia)
      .catch(() => {
        if (!solicitud.signal.aborted) setError("El reporte no está disponible en tu cuenta.");
      });
    return () => solicitud.abort();
  }, [id]);

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
      <Link className="text-sm font-medium text-brand-700 underline" href={esJunta ? "/junta" : "/residente"}>
        Volver a {esJunta ? "Junta" : "mi portal"}
      </Link>
      {error ? <Alert tone="danger">{error}</Alert> : !incidencia ? (
        <Spinner label="Cargando reporte…" />
      ) : (
        <Card>
          <CardHeader title="Detalle de la incidencia" actions={<Badge>Registrado</Badge>} />
          <CardBody className="space-y-5">
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Ubicación</dt>
                <dd className="break-words font-medium">{incidencia.ubicacion}</dd>
              </div>
              <div>
                <dt className="text-muted">Categoría</dt>
                <dd className="break-words font-medium">{incidencia.categoria}</dd>
              </div>
              <div>
                <dt className="text-muted">Urgencia reportada</dt>
                <dd className="font-medium">{URGENCIAS[incidencia.urgencia]}</dd>
              </div>
              <div>
                <dt className="text-muted">Código</dt>
                <dd className="break-all font-medium">{incidencia.id}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-muted">Descripción</dt>
                <dd className="mt-1 whitespace-pre-wrap break-words">{incidencia.descripcion}</dd>
              </div>
            </dl>
            {incidencia.tiene_evidencia && (
              <Button variant="secondary" onClick={descargar} loading={descargando} loadingText="Descargando…">
                Descargar foto
              </Button>
            )}
            {errorFoto && <Alert tone="danger">{errorFoto}</Alert>}
          </CardBody>
        </Card>
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
