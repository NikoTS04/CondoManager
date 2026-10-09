import type { FormEvent } from "react";
import { Coins } from "lucide-react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { calcularCuota, distribucionValida } from "@/features/junta/calculos";
import type { PresupuestoAprobado } from "@/features/junta/PresupuestoMensual";
import type { Departamento } from "@/lib/api";

interface CuotasSectionProps {
  departamentos: Departamento[];
  periodo: string;
  presupuesto: PresupuestoAprobado | null;
  isAuditor: boolean;
  busy: boolean;
  onEmit: (event: FormEvent) => void;
}

export function CuotasSection({
  departamentos,
  periodo,
  presupuesto,
  isAuditor,
  busy,
  onEmit,
}: CuotasSectionProps) {
  const coeficientes = departamentos.map((departamento) => departamento.coeficiente);
  const alicuotasValidas = distribucionValida(coeficientes);

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <Card>
        <CardHeader
          title="Distribución y emisión"
          description="La suma de alícuotas debe ser 100.0000 % antes de emitir."
        />
        <CardBody className="space-y-4">
          {presupuesto ? (
            <Alert tone="success" title="Presupuesto aprobado">
              {periodo} · <MoneyAmount value={presupuesto.montoTotal} moneda={presupuesto.moneda} />
            </Alert>
          ) : (
            <Alert tone="warning" title="Paso pendiente">
              Aprueba el presupuesto antes de emitir cuotas.
            </Alert>
          )}
          {alicuotasValidas ? (
            <Alert tone="success" title="Distribución validada">
              La suma de las alícuotas es 100.0000 %.
            </Alert>
          ) : (
            <Alert tone="warning" title="Distribución pendiente">
              La suma de alícuotas debe alcanzar 100.0000 % para continuar.
            </Alert>
          )}
          {!isAuditor && (
            <form onSubmit={onEmit} className="space-y-4">
              <Field label="Periodo a emitir">
                <Input value={periodo} readOnly />
              </Field>
              <div>
                <p className="text-sm font-medium text-ink">Total aprobado</p>
                <p className="mt-1">
                  {presupuesto
                    ? <MoneyAmount value={presupuesto.montoTotal} moneda={presupuesto.moneda} />
                    : "—"}
                </p>
              </div>
              <Button
                type="submit"
                loading={busy}
                disabled={!presupuesto || !alicuotasValidas}
                icon={<Coins className="h-4 w-4" aria-hidden="true" />}
              >
                Emitir cuotas
              </Button>
            </form>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Distribución por departamento" />
        <CardBody>
          {departamentos.length === 0 ? (
            <EmptyState
              title="No hay departamentos"
              description="Registra la estructura para consultar la distribución."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <caption className="sr-only">
                  Departamentos, alícuotas y cuotas estimadas del periodo
                </caption>
                <thead>
                  <tr className="border-b border-line text-left">
                    <th scope="col" className="p-3">Departamento</th>
                    <th scope="col" className="p-3 text-right">Alícuota</th>
                    <th scope="col" className="p-3 text-right">Cuota estimada</th>
                  </tr>
                </thead>
                <tbody>
                  {departamentos.map((departamento) => {
                    const cuota = presupuesto
                      ? calcularCuota(presupuesto.montoTotal, departamento.coeficiente)
                      : null;

                    return (
                      <tr key={departamento.numero} className="border-b border-line">
                        <th scope="row" className="p-3 text-left">
                          {departamento.numero}
                        </th>
                        <td className="p-3 text-right tabular-nums">
                          {departamento.coeficiente} %
                        </td>
                        <td className="p-3 text-right">
                          {cuota && presupuesto
                            ? <MoneyAmount value={cuota} moneda={presupuesto.moneda} />
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
