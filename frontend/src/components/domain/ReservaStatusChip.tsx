import { Badge, type Tone } from "@/components/ui/Badge";

export type ReservaStatus = "CONFIRMADA" | "SOLICITADA" | "CANCELADA";

const STATUS: Record<ReservaStatus, { tone: Tone; label: string }> = {
  CONFIRMADA: { tone: "success", label: "Confirmada" },
  SOLICITADA: { tone: "warning", label: "Solicitada" },
  CANCELADA: { tone: "neutral", label: "Cancelada" },
};

export function ReservaStatusChip({ status }: { status: ReservaStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
