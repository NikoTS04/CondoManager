"use client";

import { Card, CardHeader, CardBody, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { SkeletonList } from "@/components/ui/Feedback";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { EstadoFinancieroChip } from "@/components/domain/EstadoFinancieroChip";
import type { Departamento } from "@/lib/api";

export interface ResumenCuentaProps {
  depto: Departamento;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onReportarPago?: () => void;
  onReservar?: () => void;
}

export function ResumenCuenta({ depto, loading, error, onRetry, onReportarPago, onReservar }: ResumenCuentaProps) {
  if (loading) return <SkeletonList rows={3} label="Cargando estado de cuenta…" />;
  if (error) return (
    <Alert tone="danger" title="No pudimos cargar tu cuenta" action={onRetry && <Button variant="secondary" onClick={onRetry}>Reintentar</Button>}>
      {error}
    </Alert>
  );

  return (
    <Card>
      <CardHeader title="Tu cuenta" description="Saldos registrados de tu departamento." actions={<EstadoFinancieroChip status={depto.estado_financiero} />} />
      <CardBody className="space-y-6">
        <dl className="grid gap-6 sm:grid-cols-2 sm:divide-x sm:divide-line">
          <div className="space-y-2">
            <dt className="text-sm text-muted">Deuda vencida</dt>
            <dd className="text-3xl font-semibold tracking-tight tabular-nums">
              {depto.deuda_vencida !== undefined
                ? <MoneyAmount value={depto.deuda_vencida} tone={depto.estado_financiero === "EN_MORA" ? "danger" : "neutral"} />
                : <span className="text-base font-normal text-muted">No disponible</span>}
            </dd>
            <dd className="text-sm text-muted">Importe pendiente después del vencimiento.</dd>
          </div>
          <div className="space-y-2 sm:pl-6">
            <dt className="text-sm text-muted">Saldo a favor</dt>
            <dd className="text-3xl font-semibold tracking-tight tabular-nums">
              {depto.saldo_a_favor != null
                ? <MoneyAmount value={depto.saldo_a_favor} />
                : <span className="text-base font-normal text-muted">No disponible</span>}
            </dd>
            <dd className="text-sm text-muted">Crédito registrado en tu cuenta.</dd>
          </div>
        </dl>
        {depto.estado_financiero === "EN_MORA" && <Alert tone="warning" title="Reservas bloqueadas por mora">Reporta tu pago. Las reservas se habilitan cuando la junta lo aprueba y se cancela la deuda vencida.</Alert>}
        <dl className="flex flex-wrap gap-x-8 gap-y-3 border-t border-line pt-5 text-sm">
          <div><dt className="text-muted">Departamento</dt><dd className="mt-1 font-medium">{depto.numero} · Piso {depto.piso}</dd></div>
          {depto.edificio_nombre && <div><dt className="text-muted">Edificio</dt><dd className="mt-1 font-medium">{depto.edificio_nombre}</dd></div>}
          <div><dt className="text-muted">Alícuota</dt><dd className="mt-1 font-medium tabular-nums">{depto.coeficiente}%</dd></div>
        </dl>
      </CardBody>
      <CardFooter className="justify-start bg-canvas/50">
        {onReportarPago && <Button onClick={onReportarPago}>Reportar pago</Button>}
        {onReservar && <Button variant="secondary" onClick={onReservar}>Ver reservas</Button>}
      </CardFooter>
    </Card>
  );
}
