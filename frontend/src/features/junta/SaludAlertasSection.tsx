"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import {
  consultarSaludOperativa, listarAlertasMonitoreo,
  type AlertaVisible, type EjecucionJob, type EstadoComponente, type SaludOperativa,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const COMPONENTES = { api: "API", postgresql: "PostgreSQL", redis: "Redis", correo: "Correo (Mailjet)" } as const;
const ESTADO_COMPONENTE: Record<EstadoComponente, { texto: string; tono: Tone }> = {
  ok: { texto: "Operativo", tono: "success" },
  error: { texto: "Con error", tono: "danger" },
  deshabilitado: { texto: "Deshabilitado en este perfil", tono: "neutral" },
};
const RESULTADO_JOB: Record<EjecucionJob["resultado"], { texto: string; tono: Tone }> = {
  COMPLETADO: { texto: "Completado", tono: "success" },
  EN_CURSO: { texto: "En curso", tono: "info" },
  INCOMPLETO: { texto: "Incompleto", tono: "danger" },
  SIN_REGISTRO: { texto: "Sin registro", tono: "neutral" },
};
const PAGINA = 25;

export function formatDuracion(segundos: number | null): string {
  if (segundos === null) return "—";
  if (segundos < 60) return `${Math.round(segundos * 10) / 10} s`;
  return `${Math.floor(segundos / 60)} min ${Math.round(segundos % 60)} s`;
}

export function PanelSalud({ salud, cargando, error }: { salud: SaludOperativa | null; cargando: boolean; error: string | null }) {
  return (
    <Card aria-label="Estado de componentes">
      <CardHeader
        title="Estado de componentes"
        description={salud ? `Perfil ${salud.perfil} · consultado ${formatDateTime(salud.generado_en)}` : "Servicios esenciales según el perfil del ambiente."}
      />
      <CardBody className="space-y-5">
        {error && <Alert tone="danger">{error}</Alert>}
        {cargando && !salud && <SkeletonList rows={3} label="Consultando salud" />}
        {salud && (
          <>
            {salud.estado_general === "degradado" && (
              <Alert tone="warning">Hay componentes con error. Revisa el detalle antes de operar.</Alert>
            )}
            <ul className="divide-y divide-line">
              {salud.componentes.map((c) => {
                const { texto, tono } = ESTADO_COMPONENTE[c.estado];
                return (
                  <li key={c.componente} className="flex items-center justify-between gap-3 py-2">
                    <span className="font-medium">{COMPONENTES[c.componente]}</span>
                    <Badge tone={tono}>{texto}</Badge>
                  </li>
                );
              })}
            </ul>
            <div className="space-y-2">
              <h3 className="font-semibold">Procesos programados</h3>
              <ul className="divide-y divide-line">
                {salud.jobs.map((j) => {
                  const { texto, tono } = RESULTADO_JOB[j.resultado];
                  return (
                    <li key={j.nombre} className="space-y-1 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{j.nombre}</span>
                        <Badge tone={tono}>{texto}</Badge>
                      </div>
                      <p className="text-sm text-muted">
                        Inicio {formatDateTime(j.inicio)} · Fin {formatDateTime(j.fin)} · Duración {formatDuracion(j.duracion_segundos)}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

export function ListaAlertas({
  alertas, cargando, error,
}: { alertas: AlertaVisible[] | null; cargando: boolean; error: string | null }) {
  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      {cargando && !alertas && <SkeletonList rows={2} label="Cargando alertas" />}
      {alertas && alertas.length === 0 && (
        <EmptyState title="Sin alertas" description="No hay alertas con este filtro." />
      )}
      {alertas && alertas.length > 0 && (
        <ul className="space-y-3">
          {alertas.map((a) => (
            <li key={a.id} className="space-y-2 rounded-lg border border-line p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={a.componente === "job" ? "danger" : "warning"}>
                  {a.componente === "job" ? "Proceso programado" : "Correo"}
                </Badge>
                <span className="font-medium">{a.operacion}</span>
                {a.departamento_numero && <span className="text-sm text-muted">Dpto. {a.departamento_numero}</span>}
                <span className="ml-auto text-sm text-muted">{formatDateTime(a.creada_en)}</span>
              </div>
              <p>{a.mensaje}</p>
              <dl className="grid gap-x-4 gap-y-1 text-sm text-muted sm:grid-cols-[auto_1fr]">
                <dt>Referencia de diagnóstico</dt>
                <dd className="break-all font-mono">{a.referencia_diagnostico.origen_tipo}:{a.referencia_diagnostico.origen_id}</dd>
                <dt>Correlación</dt>
                <dd className="break-all font-mono">{a.referencia_diagnostico.referencia_correlacion ?? "Sin correlación aún"}</dd>
                <dt>Estado</dt>
                <dd>{a.estado === "ATENDIDA" ? `Atendida ${formatDateTime(a.atendida_en)}` : "Abierta"}</dd>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface Props { esSuperAdmin: boolean; condominioId: string | null }

export function SaludAlertasSection({ esSuperAdmin, condominioId }: Props) {
  const [salud, setSalud] = useState<SaludOperativa | null>(null);
  const [errorSalud, setErrorSalud] = useState<string | null>(null);
  const [alertas, setAlertas] = useState<AlertaVisible[] | null>(null);
  const [errorAlertas, setErrorAlertas] = useState<string | null>(null);
  const [estado, setEstado] = useState<"ABIERTA" | "ATENDIDA">("ABIERTA");
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!esSuperAdmin) return;
    let vigente = true;
    consultarSaludOperativa()
      .then((d) => { if (vigente) { setSalud(d); setErrorSalud(null); } })
      .catch(() => { if (vigente) setErrorSalud("No pudimos consultar la salud del sistema."); });
    return () => { vigente = false; };
  }, [esSuperAdmin, revision]);

  useEffect(() => {
    let vigente = true;
    setCargando(true);
    // El rol global sin condominio seleccionado ve todas, incluidas las de procesos programados.
    listarAlertasMonitoreo(esSuperAdmin ? null : condominioId, estado, pagina * PAGINA, PAGINA)
      .then((d) => { if (vigente) { setAlertas(d); setErrorAlertas(null); } })
      .catch(() => { if (vigente) setErrorAlertas("No pudimos cargar las alertas."); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [esSuperAdmin, condominioId, estado, pagina, revision]);

  return (
    <section className="space-y-6" aria-label="Salud y alertas">
      <div className="flex justify-end">
        <Button variant="secondary" size="sm" onClick={() => setRevision((v) => v + 1)}>Actualizar</Button>
      </div>
      {esSuperAdmin && <PanelSalud salud={salud} cargando={cargando} error={errorSalud} />}
      <Card aria-label="Alertas visibles">
        <CardHeader
          title="Alertas"
          description="Fallos definitivos con su componente, operación y referencia de diagnóstico."
          actions={
            <div role="group" aria-label="Estado de las alertas" className="flex gap-2">
              {(["ABIERTA", "ATENDIDA"] as const).map((e) => (
                <Button key={e} size="sm" variant={estado === e ? "primary" : "secondary"}
                  aria-pressed={estado === e} onClick={() => { setEstado(e); setPagina(0); }}>
                  {e === "ABIERTA" ? "Abiertas" : "Atendidas"}
                </Button>
              ))}
            </div>
          }
        />
        <CardBody className="space-y-4">
          <ListaAlertas alertas={alertas} cargando={cargando} error={errorAlertas} />
          <div className="flex items-center justify-between">
            <Button size="sm" variant="secondary" disabled={pagina === 0} onClick={() => setPagina((p) => p - 1)}>Anterior</Button>
            <span className="text-sm text-muted">Página {pagina + 1}</span>
            <Button size="sm" variant="secondary" disabled={!alertas || alertas.length < PAGINA}
              onClick={() => setPagina((p) => p + 1)}>Siguiente</Button>
          </div>
        </CardBody>
      </Card>
    </section>
  );
}
