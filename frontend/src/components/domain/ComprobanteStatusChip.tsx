import { Badge, type Tone } from "@/components/ui/Badge";

export type ComprobanteStatus = "EN_REVISION" | "APROBADO" | "RECHAZADO" | "OBSERVADO";

const STATUS: Record<ComprobanteStatus, { tone: Tone; label: string }> = {
  EN_REVISION: { tone: "warning", label: "En revisión" },
  APROBADO: { tone: "success", label: "Aprobado" },
  RECHAZADO: { tone: "danger", label: "Rechazado" },
  OBSERVADO: { tone: "warning", label: "Observado" },
};

export function ComprobanteStatusChip({ status }: { status: ComprobanteStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
