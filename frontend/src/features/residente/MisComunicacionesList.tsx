"use client";

import { Bell, Mail } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { formatDate } from "@/lib/format";
import type { EstadoNotificacion, NotificacionLog } from "@/lib/api";

export interface MisComunicacionesListProps {
  notificaciones: NotificacionLog[];
  departamentoId?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

const ESTADOS_RESIDENTE: Record<
  EstadoNotificacion,
  { label: string; tone: Tone }
> = {
  ENTREGADO: { label: "Entregado", tone: "success" },
  ACEPTADO: { label: "Enviado", tone: "info" },
  REINTENTANDO: { label: "En envío", tone: "warning" },
  FALLIDO_PERMANENTE: { label: "No entregado", tone: "danger" },
  EN_COLA: { label: "En cola", tone: "neutral" },
};

export function MisComunicacionesList({
  notificaciones,
  departamentoId,
  loading = false,
  error = null,
  onRetry,
}: MisComunicacionesListProps) {
  const filtradas = departamentoId
    ? notificaciones.filter(
        (n) => !n.departamento_id || n.departamento_id === departamentoId
      )
    : notificaciones;

  return (
    <Card>
      <CardHeader
        title="Mis Comunicaciones"
        description="Avisos comunitarios, confirmaciones de pago, emisión de cuotas y reservas enviadas a tu cuenta."
        icon={<Bell className="h-5 w-5 text-brand-600" aria-hidden />}
      />

      <CardBody>
        {loading ? (
          <SkeletonList rows={3} label="Cargando tus comunicaciones…" />
        ) : error ? (
          <Alert
            tone="danger"
            title="No pudimos cargar tus comunicaciones"
            action={
              onRetry ? (
                <Button variant="secondary" size="sm" onClick={onRetry}>
                  Reintentar
                </Button>
              ) : undefined
            }
          >
            {error}
          </Alert>
        ) : filtradas.length === 0 ? (
          <EmptyState
            icon={Mail}
            title="Aún no tienes comunicaciones registradas"
            description="Aquí aparecerán los avisos de la junta, confirmaciones de reservas, cuotas emitidas y conciliaciones de tus comprobantes."
          />
        ) : (
          <ul className="divide-y divide-line">
            {filtradas.map((item) => {
              const estado = ESTADOS_RESIDENTE[item.estado] ?? {
                label: item.estado,
                tone: "neutral" as Tone,
              };
              const fecha = item.creado_en;
              return (
                <li
                  key={item.id}
                  className="py-3.5 flex flex-col sm:flex-row sm:items-start justify-between gap-3 text-sm first:pt-0 last:pb-0"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-ink">
                        {item.asunto || item.tipo_evento}
                      </p>
                      {item.origen_tipo && (
                        <Badge tone="neutral">{item.origen_tipo}</Badge>
                      )}
                      {item.transporte_simulado && (
                        <Badge tone="warning">Transporte simulado</Badge>
                      )}
                    </div>
                    {item.cuerpo && (
                      <p className="text-sm text-ink/90 whitespace-pre-line">
                        {item.cuerpo}
                      </p>
                    )}
                    <p className="text-xs text-muted">
                      Canal: {item.canal} · Destino: {item.destinatario} ·{" "}
                      {formatDate(fecha)}
                    </p>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-2 shrink-0">
                    <Badge tone={estado.tone}>{estado.label}</Badge>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
