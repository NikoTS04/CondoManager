"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchResultadoPago, type ResultadoRevisionPago } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SkeletonList } from "@/components/ui/Feedback";
import { ComprobanteStatusChip } from "@/components/domain/ComprobanteStatusChip";

export function ResultadoPago({ resultado }: { resultado: ResultadoRevisionPago }) {
  const aprobado = resultado.estado_final === "APROBADO";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-all text-xs text-muted">Comprobante {resultado.comprobante_id}</p>
        <ComprobanteStatusChip status={resultado.estado_final} />
      </div>
      <dl className="grid gap-4 rounded-lg bg-canvas p-4 sm:grid-cols-3">
        {([
          ["Monto aplicado", resultado.monto_imputado],
          ["Deuda al revisar", resultado.nuevo_saldo_departamento],
          ["Crédito de este pago", resultado.saldo_a_favor_generado],
        ] as const).map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted">Importes en la moneda del condominio. Este recibo conserva el resultado de la revisión; los saldos y la solvencia actuales se consultan nuevamente.</p>
      {aprobado ? (
        <Alert tone="info" title="Solvencia al revisar">
          {resultado.departamento_habilitado_reservas
            ? "Sin deuda vencida en ese momento. Una nueva reserva vuelve a comprobar la solvencia actual."
            : "Quedó deuda vencida pendiente. El abono no elimina el bloqueo de reservas mientras esa deuda continúe."}
        </Alert>
      ) : (
        <Alert tone="warning" title={resultado.estado_final === "OBSERVADO" ? "Comprobante observado" : "Comprobante rechazado"}>
          <p className="whitespace-pre-wrap break-words">{resultado.motivo_rechazo}</p>
          <p className="mt-2">{resultado.estado_final === "OBSERVADO"
            ? "No se acreditó este comprobante. Usa Subsanar voucher para enviar una nueva evidencia y conservar su historial."
            : "No se acreditó este comprobante. La decisión es definitiva; contacta con la administración para aclararla."}</p>
          <p className="mt-2">La revisión puede regularizar cargos de mora que estaban pausados provisionalmente.</p>
        </Alert>
      )}
    </div>
  );
}

/** Montar con key de unidad/contexto y comprobante; nunca reintenta una decisión. */
export function ConsultaResultadoPago({ comprobanteId, inicial, onClose }: {
  comprobanteId: string;
  inicial?: ResultadoRevisionPago;
  onClose: () => void;
}) {
  const [resultado, setResultado] = useState<ResultadoRevisionPago | null>(inicial ?? null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [cargando, setCargando] = useState(!inicial);
  useEffect(() => {
    if (inicial && revision === 0) return;
    let vigente = true;
    const controller = new AbortController();
    setCargando(true);
    setError(null);
    setResultado(null);
    fetchResultadoPago(comprobanteId, controller.signal)
      .then((data) => { if (vigente) setResultado(data); })
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(e instanceof ApiError && e.status === 404
          ? "Todavía no hay un resultado disponible. Actualiza la bandeja y vuelve a consultar antes de decidir; esta consulta no confirma que una operación en curso haya fallado."
          : e instanceof Error ? e.message : "No se pudo consultar el resultado.");
      })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; controller.abort(); };
  }, [comprobanteId, inicial, revision]);

  return (
    <Card>
      <CardHeader title="Resultado de la revisión" description="Recibo persistido, sin volver a aplicar el pago."
        actions={<Button variant="ghost" size="sm" onClick={onClose}>Cerrar resultado</Button>} />
      <CardBody>
        <div aria-live="polite" aria-busy={cargando}>
          {cargando ? <SkeletonList rows={2} label="Consultando resultado del pago…" />
            : error ? <Alert tone="danger" title="Resultado no disponible" action={<Button variant="secondary" onClick={() => setRevision((r) => r + 1)}>Consultar de nuevo</Button>}>{error}</Alert>
              : resultado && <ResultadoPago resultado={resultado} />}
        </div>
      </CardBody>
    </Card>
  );
}
