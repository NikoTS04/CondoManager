"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { descargarVoucher, type ComprobantePago } from "@/lib/api";

export function VoucherDownloadButton({ comprobante }: { comprobante: ComprobantePago }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function descargar() {
    setBusy(true);
    setError(null);
    try {
      await descargarVoucher(comprobante);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo recuperar la evidencia.");
    } finally {
      setBusy(false);
    }
  }
  return <div className="space-y-1">
    <Button size="sm" variant="secondary" disabled={busy} onClick={() => void descargar()}>
      {busy ? "Descargando…" : "Descargar voucher"}
    </Button>
    {error && <p role="alert" className="text-xs text-danger-700">{error}</p>}
  </div>;
}
