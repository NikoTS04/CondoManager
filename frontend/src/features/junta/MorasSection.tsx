import { EstadoFinancieroChip } from "@/components/domain/EstadoFinancieroChip";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import type { DepartamentoRegistrado } from "@/lib/api";

export function MorasSection({ departamentos, loading }: { departamentos: DepartamentoRegistrado[]; loading: boolean }) {
  if (loading) return <SkeletonList rows={3} label="Cargando estado de unidades…" />;
  const enMora = departamentos.filter((d) => d.activo && d.estado_financiero === "EN_MORA");
  return (
    <Card>
      <CardHeader title="Unidades en mora" description="Estado financiero registrado de las unidades activas. Esta consulta no aplica recargos ni cambia saldos." />
      <CardBody>
        {enMora.length === 0 ? <EmptyState title="Sin unidades activas en mora" description="No hay unidades con estado En mora en los registros recibidos." /> : (
          <ul className="divide-y divide-line">
            {enMora.map((d) => <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0"><div><p className="font-medium">Departamento {d.numero}</p><p className="mt-1 break-all text-xs text-muted">Piso {d.piso} · ID {d.id}</p></div><EstadoFinancieroChip status={d.estado_financiero} /></li>)}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
