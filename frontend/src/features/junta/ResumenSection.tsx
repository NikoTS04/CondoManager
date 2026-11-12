import { Building2, FileCheck2 } from "lucide-react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, CardFooter } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import type { DepartamentoRegistrado } from "@/lib/api";
import type { PresupuestoAprobado } from "@/features/junta/PresupuestoMensual";
import type { JuntaSection } from "@/features/junta/JuntaNav";

interface ResumenSectionProps {
  loading: boolean;
  departamentos: DepartamentoRegistrado[];
  comprobantesPendientes: number;
  presupuesto: PresupuestoAprobado | null;
  onNavigate: (section: JuntaSection) => void;
}

export function ResumenSection({ loading, departamentos, comprobantesPendientes, presupuesto, onNavigate }: ResumenSectionProps) {
  if (loading) return <SkeletonList rows={4} label="Cargando resumen" />;
  const activos = departamentos.filter((d) => d.activo);
  const enMora = activos.filter((d) => d.estado_financiero === "EN_MORA").length;

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader title="Pagos por revisar" icon={<FileCheck2 className="h-5 w-5" aria-hidden />} />
        <CardBody className="space-y-3">
          <p className="text-4xl font-semibold tracking-tight tabular-nums">{comprobantesPendientes}</p>
          <p className="max-w-prose text-sm text-muted">{comprobantesPendientes > 0 ? "Comprobantes en revisión. Contrasta cada voucher antes de actualizar la cuenta del departamento." : "No hay comprobantes en revisión en los registros recibidos."}</p>
        </CardBody>
        <CardFooter className="justify-start"><Button onClick={() => onNavigate("conciliacion")}>Revisar comprobantes</Button></CardFooter>
      </Card>
      <Card>
        <CardHeader title="Unidades del condominio" icon={<Building2 className="h-5 w-5" aria-hidden />} />
        <CardBody>
          {departamentos.length === 0 ? <EmptyState title="Sin unidades registradas" description="Revisa la estructura del condominio para empezar." /> : (
            <dl className="divide-y divide-line text-sm">
              <div className="flex justify-between gap-4 pb-3"><dt>Unidades activas</dt><dd className="font-semibold tabular-nums">{activos.length}</dd></div>
              <div className="flex justify-between gap-4 py-3"><dt>Activas en mora</dt><dd className="font-semibold tabular-nums">{enMora}</dd></div>
              <div className="flex justify-between gap-4 pt-3"><dt>Unidades inactivas</dt><dd className="font-semibold tabular-nums">{departamentos.length - activos.length}</dd></div>
            </dl>
          )}
        </CardBody>
        <CardFooter className="justify-start"><Button variant="secondary" onClick={() => onNavigate("estructura")}>Ver estructura</Button><Button variant="ghost" onClick={() => onNavigate("moras")}>Consultar moras</Button></CardFooter>
      </Card>
      <Card className="xl:col-span-2">
        <CardHeader title="Presupuesto y emisión" description={presupuesto ? `Presupuesto aprobado del periodo ${presupuesto.periodo}.` : "Consulta el presupuesto del periodo antes de emitir cuotas."} actions={<Button variant="secondary" onClick={() => onNavigate("presupuesto")}>Consultar presupuesto</Button>} />
        {presupuesto && <CardBody><MoneyAmount className="text-2xl font-semibold" value={presupuesto.montoTotal} moneda={presupuesto.moneda} /></CardBody>}
      </Card>
    </div>
  );
}
