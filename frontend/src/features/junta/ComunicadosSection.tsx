import type { FormEvent } from "react";
import { Send } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { Field, Input, Textarea } from "@/components/ui/Field";
import type { NotificacionLog } from "@/lib/api";
import { formatDate } from "@/lib/format";

interface ComunicadosSectionProps {
  loading: boolean;
  notificaciones: NotificacionLog[];
  isAuditor: boolean;
  titulo: string;
  mensaje: string;
  onTituloChange: (value: string) => void;
  onMensajeChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}

const ESTADOS_NOTIFICACION: Record<
  NotificacionLog["estado"],
  { label: string; tone: "success" | "warning" | "danger" | "info" }
> = {
  ENTREGADO: { label: "Entregado", tone: "success" },
  REINTENTANDO: { label: "Reintentando", tone: "warning" },
  FALLIDO_PERMANENTE: { label: "Fallido", tone: "danger" },
  EN_COLA: { label: "En cola", tone: "info" },
};

export function ComunicadosSection({
  loading,
  notificaciones,
  isAuditor,
  titulo,
  mensaje,
  onTituloChange,
  onMensajeChange,
  onSubmit,
}: ComunicadosSectionProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader
          title="Comunicado a la comunidad"
          description="Redacta un aviso para los residentes del condominio."
        />
        <CardBody>
          {isAuditor ? (
            <div className="rounded-lg border border-audit-200 bg-audit-50 p-3">
              <Badge tone="audit">Solo lectura</Badge>
              <p className="mt-2 text-sm text-audit-800">
                El envío de comunicados no está disponible para auditoría.
              </p>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <Field label="Título" required>
                <Input
                  value={titulo}
                  onChange={(event) => onTituloChange(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label="Mensaje" required>
                <Textarea
                  value={mensaje}
                  onChange={(event) => onMensajeChange(event.target.value)}
                  rows={5}
                />
              </Field>
              <Button
                type="submit"
                icon={<Send className="h-4 w-4" aria-hidden="true" />}
              >
                Enviar comunicado
              </Button>
            </form>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Historial de envíos" />
        <CardBody>
          {loading ? (
            <SkeletonList rows={3} label="Cargando historial de comunicados" />
          ) : notificaciones.length === 0 ? (
            <EmptyState
              title="Sin envíos registrados"
              description="El historial aparecerá aquí después de enviar un comunicado."
            />
          ) : (
            <ul className="divide-y divide-line">
              {notificaciones.map((notificacion) => {
                const estado = ESTADOS_NOTIFICACION[notificacion.estado];
                return (
                  <li
                    key={notificacion.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <div>
                      <p className="font-medium">
                        {notificacion.asunto || notificacion.tipo_evento}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {notificacion.destinatario} · {notificacion.canal} ·{" "}
                        {formatDate(notificacion.fecha_creacion)}
                      </p>
                      <p className="text-xs text-muted">
                        Intentos: {notificacion.intentos}
                      </p>
                    </div>
                    <Badge tone={estado.tone}>{estado.label}</Badge>
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
