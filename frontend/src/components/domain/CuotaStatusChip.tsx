import { Badge, type Tone } from "@/components/ui/Badge";

export type CuotaStatus = "EMITIDA" | "PENDIENTE" | "PAGO_PARCIAL" | "PAGADA" | "VENCIDA" | "EN_MORA";

const STATUS: Record<CuotaStatus, { tone: Tone; label: string }> = {
  EMITIDA: { tone: "info", label: "Emitida" },
  PENDIENTE: { tone: "warning", label: "Pendiente" },
  PAGO_PARCIAL: { tone: "warning", label: "Pago parcial" },
  PAGADA: { tone: "success", label: "Pagada" },
  VENCIDA: { tone: "danger", label: "Vencida" },
  EN_MORA: { tone: "danger", label: "En mora" },
};

export function CuotaStatusChip({ status }: { status: CuotaStatus }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
