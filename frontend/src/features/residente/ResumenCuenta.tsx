"use client";

import { Coins } from "lucide-react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { SkeletonList } from "@/components/ui/Feedback";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { EstadoFinancieroChip } from "@/components/domain/EstadoFinancieroChip";
import { formatPeriodo } from "@/lib/format";
import type { Departamento } from "@/lib/api";

export interface ResumenCuentaProps {
  depto: Departamento;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function ResumenCuenta({
  depto,
  loading = false,
  error = null,
  onRetry,
}: ResumenCuentaProps) {
  if (loading) {
    return <SkeletonList rows={3} label="Cargando estado de cuenta…" />;
  }

  if (error) {
    return (
      <Alert
        tone="danger"
        title="No pudimos cargar el estado de cuenta"
        action={
          onRetry ? (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Reintentar
            </Button>
          ) : undefined
        }
      >
        {error}
      </Alert>
    );
  }

  const estaEnMora = depto.estado_financiero === "EN_MORA";
  // Simulación referencial heredada de develop basada en el coeficiente de la unidad
  const cuotaBaseReferencial =
    depto.coeficiente === "0.6800" ? "141.78" : "154.29";

  return (
    <Card className="space-y-4">
      <CardHeader
        title="Resumen de Cuotas y Obligaciones"
        description="Estado financiero actual, saldo acumulado y obligaciones vigentes del departamento."
        icon={<Coins className="h-5 w-5 text-brand-600" aria-hidden />}
        actions={
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">Estado del depto:</span>
            <EstadoFinancieroChip status={depto.estado_financiero} />
          </div>
        }
      />

      <CardBody className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Tarjeta 1: Cuota Ordinaria Referencial */}
          <div className="rounded-xl border border-line bg-canvas p-4 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted">Cuota Ordinaria Base</span>
              <Badge tone="neutral">Referencial</Badge>
            </div>
            <p className="text-2xl font-bold text-ink">
              <MoneyAmount value={cuotaBaseReferencial} />
            </p>
            <p className="text-xs text-muted">
              Periodo referencial: {formatPeriodo("2026-10")}
            </p>
          </div>

          {/* Tarjeta 2: Saldo a Favor Real */}
          <div className="rounded-xl border border-line bg-canvas p-4 space-y-1.5">
            <span className="text-xs font-medium text-muted">Saldo a Favor Acumulado</span>
            <p className="text-2xl font-bold">
              {depto.saldo_a_favor ? (
                <MoneyAmount value={depto.saldo_a_favor} tone="success" />
              ) : (
                <span className="text-base font-normal text-muted">No disponible</span>
              )}
            </p>
            <p className="text-xs text-success-700">Amortización automática mensual</p>
          </div>

          {/* Tarjeta 3: Deuda Vencida o Penalidades por Mora */}
          <div className="rounded-xl border border-line bg-canvas p-4 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted">
                {estaEnMora ? "Deuda Vencida Exigible" : "Penalidades por Mora"}
              </span>
              {estaEnMora && !depto.deuda_vencida && (
                <Badge tone="neutral">Referencial</Badge>
              )}
            </div>
            <p className="text-2xl font-bold">
              {estaEnMora ? (
                depto.deuda_vencida ? (
                  <MoneyAmount value={depto.deuda_vencida} tone="danger" />
                ) : (
                  <span className="text-base font-normal text-muted">No disponible</span>
                )
              ) : (
                <MoneyAmount value="0.00" tone="neutral" />
              )}
            </p>
            <p className="text-xs text-muted">
              {estaEnMora
                ? "Recargo aplicado tras 2 días de gracia"
                : "Sin moras pendientes"}
            </p>
          </div>
        </div>

        {estaEnMora && (
          <Alert tone="danger" title="Atención: Departamento con deuda pendiente">
            {depto.deuda_vencida ? (
              <>
                Registras un saldo vencido de{" "}
                <MoneyAmount
                  value={depto.deuda_vencida}
                  tone="danger"
                  className="font-semibold"
                />
                .
              </>
            ) : (
              <>Registras cuotas vencidas pendientes de regularización.</>
            )}{" "}
            Para rehabilitar la reserva de áreas comunes y evitar mayores recargos,
            reporta tu comprobante de pago en la sección de Pagos.
          </Alert>
        )}

        <div className="rounded-lg border border-line p-4 text-xs text-muted space-y-1">
          <p>
            <strong className="text-ink">Información de la unidad:</strong> Departamento{" "}
            {depto.numero}, Piso {depto.piso}.
          </p>
          <p>
            <strong className="text-ink">Alícuota de participación:</strong>{" "}
            {depto.coeficiente ? `${depto.coeficiente}%` : "No disponible"} sobre el presupuesto
            general del condominio.
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
