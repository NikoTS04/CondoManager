import { Badge, type Tone } from "@/components/ui/Badge";

export type ComprobanteStatus = "EN_REVISION" | "CONCILIADO" | "APROBADO" | "RECHAZADO";

const STATUS: Record<ComprobanteStatus, { tone: Tone; label: string }> = {
  EN_REVISION: { tone: "warning", label: "En revisión" },
  CONCILIADO: { tone: "success", label: "Aprobado" },
  APROBADO: { tone: "success", label: "Aprobado" },
  RECHAZADO: { tone: "danger", label: "Rechazado" },
};

export function ComprobanteStatusChip({ status }: { status: ComprobanteStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
