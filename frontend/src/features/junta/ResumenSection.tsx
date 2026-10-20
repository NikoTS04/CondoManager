import { Building2, CheckCircle2, Coins, FileCheck2 } from "lucide-react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import type { PresupuestoAprobado } from "@/features/junta/PresupuestoMensual";
import type { JuntaSection } from "@/features/junta/JuntaNav";

interface ResumenSectionProps {
  loading: boolean;
  departamentos: number;
  comprobantesPendientes: number;
  presupuesto: PresupuestoAprobado | null;
  onNavigate: (section: JuntaSection) => void;
}

export function ResumenSection({
  loading,
  departamentos,
  comprobantesPendientes,
  presupuesto,
  onNavigate,
}: ResumenSectionProps) {
  if (loading) return <SkeletonList rows={4} label="Cargando indicadores" />;

  if (departamentos === 0) {
    return (
      <EmptyState
        title="Aún no hay unidades registradas"
        description="Completa la estructura del condominio para ver sus indicadores."
        action={
          <Button variant="secondary" onClick={() => onNavigate("estructura")}>
            Revisar estructura
          </Button>
        }
      />
    );
  }

  return (
    <section aria-label="Indicadores de Junta" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Indicador
        title="Unidades registradas"
        value={departamentos.toString()}
        detail="Departamentos"
        icon={<Building2 className="h-5 w-5" aria-hidden="true" />}
      />
      <Indicador
        title="Presupuesto aprobado"
        value={presupuesto
          ? <MoneyAmount value={presupuesto.montoTotal} moneda={presupuesto.moneda} />
          : "Sin aprobar"}
        detail={presupuesto?.periodo ?? "No hay periodo aprobado"}
        icon={<Coins className="h-5 w-5" aria-hidden="true" />}
      />
      <Indicador
        title="Comprobantes pendientes"
        value={comprobantesPendientes.toString()}
        detail="Por conciliar"
        icon={<FileCheck2 className="h-5 w-5" aria-hidden="true" />}
        action={() => onNavigate("conciliacion")}
      />
      <Indicador
        title="Estado financiero"
        value="En seguimiento"
        detail="Consulta de morosidad"
        icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
        action={() => onNavigate("moras")}
      />
      {!presupuesto && (
        <div className="sm:col-span-2 xl:col-span-4">
          <Alert tone="info" title="Sin presupuesto aprobado">
            Registra y aprueba el presupuesto del periodo para continuar con la emisión.
          </Alert>
        </div>
      )}
    </section>
  );
}

function Indicador({
  title,
  value,
  detail,
  icon,
  action,
}: {
  title: string;
  value: React.ReactNode;
  detail: string;
  icon: React.ReactNode;
  action?: () => void;
}) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-muted">{title}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
            <p className="mt-1 text-xs text-muted">{detail}</p>
          </div>
          <span className="text-info-600">{icon}</span>
        </div>
        {action && (
          <Button className="mt-3" variant="ghost" size="sm" onClick={action}>
            Ver detalle
          </Button>
        )}
      </CardBody>
    </Card>
  );
}
