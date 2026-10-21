"use client";

import { useEffect, useState } from "react";
import { fetchNotificaciones, type NotificacionLog } from "@/lib/api";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { formatDate } from "@/lib/format";

const ESTADOS: Record<NotificacionLog["estado"], string> = {
  EN_COLA: "En cola", ENVIADO: "Aceptado, entrega sin confirmar", ENTREGADO: "Entrega confirmada",
  REINTENTANDO: "Reintento programado", FALLIDO_PERMANENTE: "Envío fallido: la administración debe revisarlo",
};

export function AvisosList({ condominioId, departamentoId }: { condominioId: string; departamentoId: string }) {
  const [avisos, setAvisos] = useState<NotificacionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelado = false;
    setLoading(true);
    setError(null);
    setAvisos([]);
    void fetchNotificaciones(condominioId)
      .then((data) => { if (!cancelado) setAvisos(data.filter((n) => n.departamento_id === departamentoId)); })
      .catch((e) => { if (!cancelado) setError(e instanceof Error ? e.message : "No pudimos consultar tus avisos."); })
      .finally(() => { if (!cancelado) setLoading(false); });
    return () => { cancelado = true; };
  }, [condominioId, departamentoId, revision]);

  return <Card>
    <CardHeader title="Tus avisos" description="Comunicaciones de tu unidad y estado real del envío." />
    <CardBody>
      <Button variant="secondary" onClick={() => setRevision((r) => r + 1)} disabled={loading}>Actualizar avisos</Button>
      {loading ? <SkeletonList rows={3} label="Cargando avisos" /> : error ?
        <Alert tone="danger" action={<Button onClick={() => setRevision((r) => r + 1)}>Reintentar</Button>}>{error}</Alert> :
        avisos.length === 0 ? <EmptyState title="Sin avisos" description="Las comunicaciones confirmadas de tu unidad aparecerán aquí." /> :
        <ul className="divide-y divide-line">{avisos.map((n) => <li key={n.id} className="space-y-2 py-4">
          <h2 className="font-semibold">{n.asunto || "Aviso de la comunidad"}</h2>
          <p className="whitespace-pre-wrap text-sm">{n.cuerpo}</p>
          <p className="text-sm">{ESTADOS[n.estado]}{n.transporte === "SIMULADO" ? " · Transporte simulado" : ""}</p>
          <p className="text-xs text-muted">{formatDate(n.fecha_creacion)} · Intentos: {n.intentos}</p>
        </li>)}</ul>}
    </CardBody>
  </Card>;
}
