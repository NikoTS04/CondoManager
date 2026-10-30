"use client";

import { CreditCard, FileText } from "lucide-react";
import { useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { SkeletonList, EmptyState } from "@/components/ui/Feedback";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { ComprobanteStatusChip } from "@/components/domain/ComprobanteStatusChip";
import { VoucherDownloadButton } from "@/components/domain/VoucherDownloadButton";
import { formatDate } from "@/lib/format";
import { subsanarVoucher, type ComprobantePago } from "@/lib/api";
import { FileDropzone } from "@/components/ui/FileDropzone";

export interface ComprobantesListProps {
  comprobantes: ComprobantePago[];
  departamentoId: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function ComprobantesList({
  comprobantes,
  departamentoId,
  loading = false,
  error = null,
  onRetry,
}: ComprobantesListProps) {
  const filtrados = comprobantes.filter((c) => c.departamento_id === departamentoId);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<string | null>(null);

  async function subsanar() {
    if (!seleccion || !archivo) return;
    setEnviando(true);
    setFallo(null);
    try {
      await subsanarVoucher(seleccion, archivo);
      setSeleccion(null);
      setArchivo(null);
      onRetry?.();
    } catch (e) {
      setFallo(e instanceof Error ? e.message : "No pudimos subsanar el comprobante.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Tus comprobantes"
        description="Consulta la revisión de tus pagos y subsana los comprobantes observados."
        icon={<FileText className="h-5 w-5 text-brand-600" aria-hidden />}
      />

      <CardBody>
        {fallo && <Alert tone="danger">{fallo}</Alert>}
        {loading ? (
          <SkeletonList rows={3} label="Cargando historial de comprobantes…" />
        ) : error ? (
          <Alert
            tone="danger"
            title="No pudimos cargar tus comprobantes"
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
        ) : filtrados.length === 0 ? (
          <EmptyState
            icon={CreditCard}
            title="No has reportado comprobantes recientemente"
            description="Cuando realices un pago por Yape, Plin o transferencia bancaria, repórtalo aquí para que la junta concilie tus cuotas."
          />
        ) : (
          <div className="divide-y divide-line">
            {filtrados.map((comp) => (
              <div
                key={comp.id}
                className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm first:pt-0 last:pb-0"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink">
                      {comp.banco} · Op. {comp.numero_operacion}
                    </p>
                    <span className="text-muted">·</span>
                    <p className="font-semibold text-ink">
                      <MoneyAmount value={comp.monto} moneda="PEN" />
                    </p>
                  </div>
                  <p className="text-xs text-muted">
                    Fecha de pago: {formatDate(comp.fecha_operacion)}
                  </p>
                  {comp.motivo_rechazo && (
                    <p className="text-xs font-medium text-danger-700 bg-danger-50 rounded-md px-2 py-1 inline-block">
                      Motivo: {comp.motivo_rechazo}
                    </p>
                  )}
                  {comp.estado === "OBSERVADO" && (seleccion === comp.id ? (
                    <div className="space-y-2">
                      <FileDropzone label="Nuevo voucher para subsanar" file={archivo} onFileChange={setArchivo} />
                      <Button onClick={() => void subsanar()} disabled={!archivo || enviando} loading={enviando}>
                        Enviar subsanación
                      </Button>
                    </div>
                  ) : <Button variant="secondary" size="sm" disabled={enviando} onClick={() => {
                    setSeleccion(comp.id); setArchivo(null); setFallo(null);
                  }}>Subsanar voucher</Button>)}
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                  <ComprobanteStatusChip status={comp.estado} />
                  <VoucherDownloadButton comprobante={comp} />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
