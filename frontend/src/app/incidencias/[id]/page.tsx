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
import { AsignacionIncidenciaForm } from "@/features/junta/AsignacionIncidenciaForm";
import { RevisionIncidenciaForm } from "@/features/junta/RevisionIncidenciaForm";
import { SeguimientoIncidencia } from "@/features/junta/SeguimientoIncidencia";
import {
  consultarAvisosAsignacion,
  consultarIncidencia,
  descargarFotoIncidencia,
  NIVELES_INCIDENCIA,
  type AvisoAsignacion,
  type Incidencia,
} from "@/lib/api";

const ETIQUETAS_ESTADO: Record<Incidencia["estado"], string> = {
  REGISTRADO: "Registrado",
  RECHAZADO: "Rechazado",
  ASIGNADO: "Asignado",
  EN_PROCESO: "En proceso",
  RESUELTO: "Resuelto",
  CERRADO: "Cerrado",
};

function DetalleIncidencia({ id }: { id: string }) {
  const { user } = useAuth();
  const [incidencia, setIncidencia] = useState<Incidencia>();
  const [error, setError] = useState("");
  const [errorFoto, setErrorFoto] = useState("");
  const [descargando, setDescargando] = useState(false);
  const [revisionConsulta, setRevisionConsulta] = useState(0);
  const [confirmacion, setConfirmacion] = useState("");
  const [avisos, setAvisos] = useState<AvisoAsignacion[]>([]);
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

  useEffect(() => {
    if (!esJunta) return;
    const solicitud = new AbortController();
    consultarAvisosAsignacion(id, solicitud.signal)
      .then((lista) => {
        if (!solicitud.signal.aborted) setAvisos(lista.items);
      })
      .catch(() => undefined);
    return () => solicitud.abort();
  }, [id, esJunta, revisionConsulta]);

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
      <Link
        className="text-sm font-medium text-brand-700 underline"
        href={esJunta ? "/junta#incidencias" : "/residente?seccion=incidencias"}
      >
        {esJunta ? "Volver a incidencias" : "Volver a mis reportes"}
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
                  {ETIQUETAS_ESTADO[incidencia.estado]}
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
               {incidencia.responsable_usuario_id || incidencia.responsable_proveedor_id ? (
                 <div className="rounded-lg border border-line bg-surface p-4 text-sm">
                   <p className="font-semibold">Responsable asignado</p>
                   <p className="break-all text-muted">
                     {incidencia.responsable_usuario_id
                       ? incidencia.responsable_usuario_id
                       : "Proveedor externo"}
                   </p>
                   {incidencia.plazo && (
                     <p className="mt-2 text-muted">
                       Plazo: {new Date(incidencia.plazo).toLocaleString("es-PE")}
                     </p>
                   )}
                 </div>
               ) : null}
            </CardBody>
          </Card>
          {esJunta && avisos.length > 0 && (
            <Card>
              <CardHeader title="Avisos de la asignación" description="El estado ENVIADO no prueba entrega." />
              <CardBody>
                <ul className="space-y-2 text-sm">
                  {avisos.map((aviso, indice) => (
                    <li key={`${aviso.asignacion_id}-${aviso.destinatario_tipo}-${indice}`} className="flex flex-wrap justify-between gap-2 border-b border-line py-1 last:border-0">
                      <span className="font-medium">
                        {aviso.destinatario_tipo === "RESIDENTE" ? "Residente" : "Proveedor"}
                      </span>
                      <span className="text-muted">
                        {aviso.estado === "CONTACTO_FALTANTE" ? "Contacto faltante" : aviso.estado}
                        {aviso.alerta_abierta ? " · alerta abierta" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}
          {["ASIGNADO", "EN_PROCESO", "RESUELTO", "CERRADO"].includes(incidencia.estado) && (
            <SeguimientoIncidencia
              incidencia={incidencia}
              esJunta={esJunta}
              onActualizada={(detalle) => {
                setIncidencia(detalle);
                setConfirmacion(
                  detalle.estado === "RESUELTO" ? "Incidencia resuelta." : "Avance guardado.",
                );
                setRevisionConsulta((actual) => actual + 1);
              }}
            />
          )}
          {esJunta && ["REGISTRADO", "ASIGNADO"].includes(incidencia.estado) && (
            <AsignacionIncidenciaForm
              key={`${incidencia.id}-${incidencia.version}`}
              incidencia={incidencia}
              onAsignada={() => {
                setConfirmacion("Asignación guardada y avisos encolados.");
                setRevisionConsulta((actual) => actual + 1);
              }}
            />
          )}
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
