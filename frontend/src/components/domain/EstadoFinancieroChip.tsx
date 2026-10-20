import { Badge, type Tone } from "@/components/ui/Badge";

export type EstadoFinanciero = "AL_DIA" | "OBSERVADO" | "EN_MORA";

const STATUS: Record<EstadoFinanciero, { tone: Tone; label: string }> = {
  AL_DIA: { tone: "success", label: "Al día" },
  OBSERVADO: { tone: "warning", label: "Observado" },
  EN_MORA: { tone: "danger", label: "En mora" },
};

export function EstadoFinancieroChip({ status }: { status: EstadoFinanciero }) {
  const { tone, label } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
