import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { ComprobanteStatusChip } from "@/components/domain/ComprobanteStatusChip";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import type { ComprobantePago } from "@/lib/api";
import { formatDate } from "@/lib/format";

interface ConciliacionSectionProps {
  loading: boolean;
  comprobantes: ComprobantePago[];
  isAuditor: boolean;
  onDecide: (id: string, decision: "APROBADO" | "RECHAZADO") => void;
}

export function ConciliacionSection({
  loading,
  comprobantes,
  isAuditor,
  onDecide,
}: ConciliacionSectionProps) {
  if (loading) return <SkeletonList rows={5} label="Cargando comprobantes" />;

  if (comprobantes.length === 0) {
    return (
      <EmptyState
        title="No hay comprobantes"
        description="Los comprobantes recibidos aparecerán aquí para su conciliación."
      />
    );
  }

  return (
    <Card>
      <CardHeader
        title="Comprobantes recibidos"
        description="Revisa los datos del pago antes de aprobarlo o rechazarlo."
      />
      <CardBody>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <caption className="sr-only">
              Comprobantes de pago y estado de conciliación
            </caption>
            <thead>
              <tr className="border-b border-line text-left">
                <th scope="col" className="p-3">Departamento</th>
                <th scope="col" className="p-3">Banco / operación</th>
                <th scope="col" className="p-3">Fecha</th>
                <th scope="col" className="p-3 text-right">Monto</th>
                <th scope="col" className="p-3">Estado</th>
                <th scope="col" className="p-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {comprobantes.map((comprobante) => (
                <tr key={comprobante.id} className="border-b border-line">
                  <th scope="row" className="p-3 text-left">
                    {comprobante.departamento_id}
                  </th>
                  <td className="p-3">
                    {comprobante.banco} · {comprobante.numero_operacion}
                  </td>
                  <td className="p-3">{formatDate(comprobante.fecha_operacion)}</td>
                  <td className="p-3 text-right">
                    <MoneyAmount value={comprobante.monto} />
                  </td>
                  <td className="p-3">
                    <ComprobanteStatusChip status={comprobante.estado} />
                  </td>
                  <td className="p-3 text-right">
                    {!isAuditor && comprobante.estado === "EN_REVISION" && (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          onClick={() => onDecide(comprobante.id, "APROBADO")}
                        >
                          Aprobar
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => onDecide(comprobante.id, "RECHAZADO")}
                        >
                          Rechazar
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}
