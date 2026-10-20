import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { formatMoney, type Moneda } from "@/lib/money";

export interface SolvenciaBannerProps {
  solvente: boolean;
  deudaVencida?: string;
  moneda?: Moneda;
  onReportarPago?: () => void;
}

export function SolvenciaBanner({ solvente, deudaVencida, moneda = "PEN", onReportarPago }: SolvenciaBannerProps) {
  if (solvente) {
    return <Alert tone="success">Tu departamento está al día y puedes realizar reservas.</Alert>;
  }

  const monto = deudaVencida === undefined ? "cuotas vencidas" : `cuotas vencidas por ${formatMoney(deudaVencida, moneda)}`;
  return (
    <Alert
      tone="danger"
      title="No puedes reservar todavía"
      action={onReportarPago ? <Button onClick={onReportarPago}>Reportar pago</Button> : undefined}
    >
      Tienes {monto}. Reporta tu pago para desbloquear las reservas.
    </Alert>
  );
}
