"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { descargarVoucher, listarEvidencias, visualizarVoucher, type ComprobantePago, type EvidenciaVoucher } from "@/lib/api";

export function VoucherDownloadButton({ comprobante }: { comprobante: ComprobantePago }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [evidencias, setEvidencias] = useState<EvidenciaVoucher[]>([]);
  const [evidenciaId, setEvidenciaId] = useState("");
  const [archivo, setArchivo] = useState<{ url: string; tipo: string } | null>(null);
  const [zoom, setZoom] = useState(100);
  const [rotacion, setRotacion] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [errorVisor, setErrorVisor] = useState<string | null>(null);
  const [errorHistorial, setErrorHistorial] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setErrorHistorial(null);
    setEvidencias([]);
    listarEvidencias(comprobante.id, controller.signal).then(setEvidencias).catch((cause) => {
      if (!controller.signal.aborted) setErrorHistorial(cause.message);
    });
    return () => controller.abort();
  }, [open, comprobante.id]);

  useEffect(() => {
    setArchivo(null);
    if (!open) return;
    const controller = new AbortController();
    let url: string | undefined;
    setCargando(true);
    setErrorVisor(null);
    setZoom(100);
    setRotacion(0);
    visualizarVoucher(comprobante.id, evidenciaId, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      setArchivo({ url, tipo: blob.type });
    }).catch((cause) => {
      if (!controller.signal.aborted) setErrorVisor(cause.message);
    }).finally(() => {
      if (!controller.signal.aborted) setCargando(false);
    });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [open, comprobante.id, evidenciaId]);
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
    <Button size="sm" variant="secondary" onClick={() => { setEvidenciaId(""); setOpen(true); }}>Ver comprobante</Button>
    <Button size="sm" variant="secondary" disabled={busy} onClick={() => void descargar()}>
      {busy ? "Descargando…" : "Descargar voucher"}
    </Button>
    {error && <p role="alert" className="text-xs text-danger-700">{error}</p>}
    <Dialog open={open} onClose={() => setOpen(false)} title="Comprobante de pago" className="max-w-5xl" description="Consulta privada. No es necesario guardar el archivo en su equipo.">
      <label className="block text-sm">Versión de evidencia
        <select value={evidenciaId} onChange={(event) => setEvidenciaId(event.target.value)} className="m-2 rounded border border-line p-2">
          <option value="">Vigente</option>
          {evidencias.map((e) => <option key={e.evidencia_id} value={e.evidencia_id}>Revisión {new Date(e.creado_en).toLocaleString("es-PE", { timeZone: "America/Lima" })} · {e.evidencia_id.slice(0, 8)}</option>)}
        </select>
      </label>
      {errorHistorial && <p role="alert" className="text-sm text-danger-700">{errorHistorial}</p>}
      {cargando && <p role="status">Cargando evidencia…</p>}
      {errorVisor && <p role="alert" className="text-sm text-danger-700">{errorVisor}</p>}
      {archivo?.tipo === "application/pdf" && <iframe src={archivo.url} title="Documento PDF del comprobante" className="h-[65vh] w-full" />}
      {archivo && archivo.tipo !== "application/pdf" && <>
        <div className="my-3 flex gap-2">
          <Button size="sm" variant="secondary" disabled={zoom <= 50} onClick={() => setZoom(zoom - 25)}>Alejar</Button>
          <Button size="sm" variant="secondary" disabled={zoom >= 300} onClick={() => setZoom(zoom + 25)}>Ampliar</Button>
          <Button size="sm" variant="secondary" onClick={() => setRotacion((rotacion + 90) % 360)}>Rotar</Button>
        </div>
        <div className="max-h-[65vh] overflow-auto p-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={archivo.url} alt="Captura del comprobante de pago" style={{ width: `${zoom}%`, maxWidth: "none", transform: `rotate(${rotacion}deg)` }} />
        </div>
      </>}
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => void descargar()}>Descargar evidencia vigente</Button>
      {error && <p role="alert" className="text-sm text-danger-700">{error}</p>}
    </Dialog>
  </div>;
}
